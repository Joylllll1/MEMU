#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def patch_common(nanos: Path, vme: bool = False) -> None:
    common = nanos / "include/common.h"
    text = common.read_text(encoding="ascii")
    text = text.replace("//#define HAS_CTE", "#define HAS_CTE")
    if vme:
        text = text.replace("//#define HAS_VME", "#define HAS_VME")
    common.write_text(text, encoding="ascii")


def patch_nanos(nanos: Path, app_path: str = "/bin/hello", vme: bool = False) -> None:
    patch_common(nanos, vme=vme)

    (nanos / "src/main.c").write_text(
        r'''#include <common.h>

void init_mm(void);
void init_device(void);
void init_ramdisk(void);
void init_irq(void);
void init_fs(void);
void init_proc(void);

int main() {
  putstr("Nanos-lite boot\n");
  init_mm();
  init_device();
  init_ramdisk();
#ifdef HAS_CTE
  init_irq();
#endif
  init_fs();
  init_proc();
  panic("Should not reach here");
}
''',
        encoding="ascii",
    )

    (nanos / "src/proc.c").write_text(
        r'''#include <proc.h>
#include <string.h>

#define MAX_NR_PROC 16

static PCB pcb[MAX_NR_PROC] __attribute__((used)) = {};
static PCB pcb_boot = {};
PCB *current = NULL;
static enum {
  PROC_UNUSED,
  PROC_RUNNABLE,
  PROC_RUNNING,
  PROC_BLOCKED,
  PROC_EXITED,
} proc_state[MAX_NR_PROC];
static PCB *wait_parent[MAX_NR_PROC];
static int proc_pid[MAX_NR_PROC];
static uintptr_t proc_exit_status[MAX_NR_PROC];
static bool wait_pending[MAX_NR_PROC];
static uintptr_t wait_status[MAX_NR_PROC];
static int next_pid = 1;

void switch_boot_pcb() {
  current = &pcb_boot;
}

static int proc_index(PCB *p) {
  for (int i = 0; i < MAX_NR_PROC; i++) {
    if (&pcb[i] == p) return i;
  }
  return -1;
}

static Context *context_slot(PCB *p) {
  uintptr_t end = (uintptr_t)p->stack + STACK_SIZE;
  return (Context *)((end & ~(uintptr_t)0xf) - sizeof(Context));
}

void process_register(PCB *p) {
  int index = proc_index(p);
  if (index < 0) return;
  proc_state[index] = PROC_RUNNING;
  if (proc_pid[index] == 0) proc_pid[index] = next_pid++;
  current = p;
}

bool process_is_managed(void) {
  int index = proc_index(current);
  return index >= 0 && proc_state[index] != PROC_UNUSED &&
         proc_state[index] != PROC_EXITED;
}

static PCB *next_runnable(void) {
  int current_index = proc_index(current);
  for (int step = 1; step <= MAX_NR_PROC; step++) {
    int index = (current_index + step) % MAX_NR_PROC;
    if (proc_state[index] == PROC_RUNNABLE) return &pcb[index];
  }
  return NULL;
}

int process_slot(void) {
  return proc_index(current);
}

void process_clone_fds(int parent_index, int child_index);
void process_release_fds(int process_index);

typedef uint32_t ProcessPte;
#define PROCESS_PTE_V 0x01u
#define PROCESS_PTE_W 0x04u
#define PROCESS_USER_VA_START 0x40000000u
#define PROCESS_USER_VA_END 0x80000000u

static void process_clone_as(PCB *parent, PCB *child) {
  if (parent->as.ptr == NULL) {
    child->as = parent->as;
    child->max_brk = parent->max_brk;
    return;
  }
  protect(&child->as);
  ProcessPte *parent_root = (ProcessPte *)parent->as.ptr;
  for (uintptr_t vpn1 = PROCESS_USER_VA_START >> 22;
       vpn1 < PROCESS_USER_VA_END >> 22; vpn1++) {
    ProcessPte root_entry = parent_root[vpn1];
    if ((root_entry & PROCESS_PTE_V) == 0) continue;
    ProcessPte *parent_table =
        (ProcessPte *)((root_entry >> 10) << 12);
    for (uintptr_t vpn0 = 0; vpn0 < 1024; vpn0++) {
      ProcessPte leaf = parent_table[vpn0];
      if ((leaf & PROCESS_PTE_V) == 0) continue;
      void *copy = new_page(1);
      void *source = (void *)((leaf >> 10) << 12);
      memcpy(copy, source, PGSIZE);
      uintptr_t va = (vpn1 << 22) | (vpn0 << 12);
      map(&child->as, (void *)va, copy,
          (leaf & PROCESS_PTE_W) ? MMAP_READ | MMAP_WRITE : MMAP_READ);
    }
  }
  child->max_brk = parent->max_brk;
}

static bool process_copy_to_user(PCB *process, uintptr_t va,
                                 const void *src, size_t len) {
  if (process->as.ptr == NULL) {
    memcpy((void *)va, src, len);
    return true;
  }
  ProcessPte *root = (ProcessPte *)process->as.ptr;
  const uint8_t *bytes = (const uint8_t *)src;
  while (len > 0) {
    if (va < PROCESS_USER_VA_START || va >= PROCESS_USER_VA_END) return false;
    ProcessPte root_entry = root[(va >> 22) & 0x3ff];
    if ((root_entry & PROCESS_PTE_V) == 0) return false;
    ProcessPte *table = (ProcessPte *)((root_entry >> 10) << 12);
    ProcessPte leaf = table[(va >> 12) & 0x3ff];
    if ((leaf & PROCESS_PTE_V) == 0) return false;
    uintptr_t offset = va & (PGSIZE - 1);
    size_t chunk = PGSIZE - offset;
    if (chunk > len) chunk = len;
    memcpy((uint8_t *)((leaf >> 10) << 12) + offset, bytes, chunk);
    va += chunk;
    bytes += chunk;
    len -= chunk;
  }
  return true;
}

static int process_reap(int parent_index, int *status) {
  for (int i = 0; i < MAX_NR_PROC; i++) {
    if (proc_state[i] != PROC_EXITED || proc_index(wait_parent[i]) != parent_index) {
      continue;
    }
    if (status != NULL) *status = (int)proc_exit_status[i];
    int pid = proc_pid[i];
    wait_parent[i] = NULL;
    proc_pid[i] = 0;
    proc_exit_status[i] = 0;
    proc_state[i] = PROC_UNUSED;
    return pid;
  }
  return -1;
}

Context *process_wait(Context *prev, int *status) {
  if (!process_is_managed()) {
    prev->GPRx = (uintptr_t)-1;
    return prev;
  }
  int parent_index = proc_index(current);
  int pid = process_reap(parent_index, status);
  if (pid >= 0) {
    prev->GPRx = (uintptr_t)pid;
    return prev;
  }

  bool has_child = false;
  for (int i = 0; i < MAX_NR_PROC; i++) {
    if (proc_state[i] != PROC_UNUSED && wait_parent[i] == current) {
      has_child = true;
      break;
    }
  }
  if (!has_child) {
    prev->GPRx = (uintptr_t)-1;
    return prev;
  }

  current->cp = context_slot(current);
  *current->cp = *prev;
  wait_pending[parent_index] = true;
  wait_status[parent_index] = (uintptr_t)status;
  proc_state[parent_index] = PROC_BLOCKED;
  PCB *next = next_runnable();
  if (next == NULL) {
    wait_pending[parent_index] = false;
    wait_status[parent_index] = 0;
    proc_state[parent_index] = PROC_RUNNING;
    prev->GPRx = (uintptr_t)-1;
    return prev;
  }
  current = next;
  int next_index = proc_index(next);
  proc_state[next_index] = PROC_RUNNING;
  return next->cp;
}

Context *process_schedule(Context *prev) {
  if (!process_is_managed()) return prev;
  int current_index = proc_index(current);
  current->cp = context_slot(current);
  *current->cp = *prev;
  if (proc_state[current_index] == PROC_RUNNING) {
    proc_state[current_index] = PROC_RUNNABLE;
  }
  PCB *next = next_runnable();
  if (next == NULL) {
    proc_state[current_index] = PROC_RUNNING;
    return prev;
  }
  int next_index = proc_index(next);
  current = next;
  proc_state[next_index] = PROC_RUNNING;
  return next->cp;
}

/* PA's current Nanos-lite syscall surface exposes one fork number. Clone the
 * user address space so parent and child can run independently before execve. */
Context *process_fork(Context *parent_ctx) {
  if (!process_is_managed()) return parent_ctx;
  int parent_index = proc_index(current);
  int child_index = -1;
  for (int i = 0; i < MAX_NR_PROC; i++) {
    if (proc_state[i] == PROC_UNUSED || proc_state[i] == PROC_EXITED) {
      child_index = i;
      break;
    }
  }
  if (child_index < 0) {
    parent_ctx->GPRx = (uintptr_t)-1;
    return parent_ctx;
  }

  PCB *parent = current;
  PCB *child = &pcb[child_index];
  process_clone_fds(parent_index, child_index);
  process_clone_as(parent, child);
  parent->cp = context_slot(parent);
  *parent->cp = *parent_ctx;
  proc_pid[child_index] = next_pid++;
  proc_exit_status[child_index] = 0;
  wait_pending[child_index] = false;
  wait_status[child_index] = 0;
  child->cp = context_slot(child);
  *child->cp = *parent_ctx;
  parent->cp->GPRx = (uintptr_t)proc_pid[child_index];
  child->cp->GPRx = 0;
  proc_state[child_index] = PROC_RUNNABLE;
  wait_parent[child_index] = parent;
  child->cp->pdir = child->as.ptr;
  proc_state[parent_index] = PROC_RUNNING;
  return parent->cp;
}

Context *process_exit(Context *prev, uintptr_t status) {
  if (!process_is_managed()) return NULL;
  int index = proc_index(current);
  process_release_fds(index);
  proc_exit_status[index] = status;
  proc_state[index] = PROC_EXITED;
  PCB *parent = wait_parent[index];
  int parent_index = proc_index(parent);
  if (parent_index >= 0 && proc_state[parent_index] == PROC_BLOCKED &&
      wait_pending[parent_index]) {
    int child_status = (int)proc_exit_status[index];
    if (wait_status[parent_index] != 0) {
      process_copy_to_user(parent, wait_status[parent_index], &child_status,
                           sizeof(child_status));
    }
    parent->cp->GPRx = (uintptr_t)proc_pid[index];
    wait_pending[parent_index] = false;
    wait_status[parent_index] = 0;
    wait_parent[index] = NULL;
    proc_pid[index] = 0;
    proc_exit_status[index] = 0;
    proc_state[index] = PROC_UNUSED;
    proc_state[parent_index] = PROC_RUNNABLE;
  }
  PCB *next = next_runnable();
  if (next == NULL) return NULL;
  current = next;
  int next_index = proc_index(next);
  proc_state[next_index] = PROC_RUNNING;
  return next->cp;
}

void naive_uload(PCB *pcb, const char *filename);

void init_proc() {
  switch_boot_pcb();
  Log("Initializing processes...");
  process_register(&pcb[0]);
  naive_uload(&pcb[0], "/bin/hello");
}

Context* schedule(Context *prev) {
  return process_schedule(prev);
}
'''.replace("/bin/hello", app_path),
        encoding="ascii",
    )

    (nanos / "src/irq.c").write_text(
        r'''#include <common.h>

Context *do_syscall(Context *c);
Context *process_schedule(Context *prev);

static Context* do_event(Event e, Context* c) {
  switch (e.event) {
    case EVENT_YIELD:
      c = process_schedule(c);
      break;
    case EVENT_SYSCALL:
      c = do_syscall(c);
      break;
    case EVENT_IRQ_TIMER:
      c = process_schedule(c);
      break;
    default:
      panic("Unhandled event ID = %d", e.event);
  }

  return c;
}

void init_irq(void) {
  Log("Initializing interrupt/exception handler...");
  cte_init(do_event);
}
''',
        encoding="ascii",
    )

    (nanos / "src/mm.c").write_text(
        r'''#include <memory.h>
#include <proc.h>

static void *pf = NULL;

void* new_page(size_t nr_page) {
  void *p = pf;
  pf += nr_page * PGSIZE;
  memset(p, 0, nr_page * PGSIZE);
  return p;
}

#ifdef HAS_VME
static void* pg_alloc(int n) {
  return new_page(((size_t)n + PGSIZE - 1) / PGSIZE);
}
#endif

void free_page(void *p) {
  panic("not implement yet");
}

int mm_brk(uintptr_t brk) {
#ifdef HAS_VME
  if (current->max_brk == 0) {
    return 0;
  }
  while (current->max_brk < brk) {
    void *pa = new_page(1);
    map(&current->as, (void *)current->max_brk, pa, MMAP_READ | MMAP_WRITE);
    current->max_brk += PGSIZE;
  }
#else
  (void)brk;
#endif
  return 0;
}

void init_mm() {
  pf = (void *)ROUNDUP(heap.start, PGSIZE);
  Log("free physical pages starting from %p", pf);

#ifdef HAS_VME
  vme_init(pg_alloc, free_page);
#endif
}
''',
        encoding="ascii",
    )

    (nanos / "src/device.c").write_text(
        r'''#include <common.h>

#if defined(MULTIPROGRAM) && !defined(TIME_SHARING)
# define MULTIPROGRAM_YIELD() yield()
#else
# define MULTIPROGRAM_YIELD()
#endif

#define NAME(key) \
  [AM_KEY_##key] = #key,

static const char *keyname[256] __attribute__((used)) = {
  [AM_KEY_NONE] = "NONE",
  AM_KEYS(NAME)
};

size_t serial_write(const void *buf, size_t offset, size_t len) {
  (void)offset;
  const char *s = (const char *)buf;
  for (size_t i = 0; i < len; i++) {
    putch(s[i]);
  }
  return len;
}

size_t events_read(void *buf, size_t offset, size_t len) {
  (void)offset;
  if (len == 0) {
    return 0;
  }
  AM_INPUT_KEYBRD_T ev = io_read(AM_INPUT_KEYBRD);
  if (ev.keycode == AM_KEY_NONE) {
    return 0;
  }
  const char *state = ev.keydown ? "kd" : "ku";
  const char *name = keyname[ev.keycode];
  int n = snprintf(buf, len, "%s %s\n", state, name);
  return n < 0 ? 0 : (n < (int)len ? (size_t)n : len);
}

size_t dispinfo_read(void *buf, size_t offset, size_t len) {
  char info[32];
  AM_GPU_CONFIG_T cfg = io_read(AM_GPU_CONFIG);
  int n = snprintf(info, sizeof(info), "WIDTH:%d\nHEIGHT:%d\n", cfg.width, cfg.height);
  if (n < 0 || offset >= (size_t)n) {
    return 0;
  }
  size_t avail = (size_t)n - offset;
  size_t actual = len < avail ? len : avail;
  memcpy(buf, info + offset, actual);
  return actual;
}

size_t audio_status_read(void *buf, size_t offset, size_t len) {
  (void)offset;
  AM_AUDIO_CONFIG_T config = io_read(AM_AUDIO_CONFIG);
  AM_AUDIO_STATUS_T status = io_read(AM_AUDIO_STATUS);
  int available = config.bufsize - status.count;
  if (available < 0) available = 0;
  uint32_t value = (uint32_t)available;
  if (len < sizeof(value)) return 0;
  memcpy(buf, &value, sizeof(value));
  return sizeof(value);
}

size_t audio_control_write(const void *buf, size_t offset, size_t len) {
  if (offset != 0 || len < 12) return 0;
  const uint8_t *bytes = (const uint8_t *)buf;
  AM_AUDIO_CTRL_T control = {
    .freq = (int)(bytes[0] | ((uint32_t)bytes[1] << 8) |
                  ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24)),
    .channels = (int)(bytes[4] | ((uint32_t)bytes[5] << 8) |
                      ((uint32_t)bytes[6] << 16) | ((uint32_t)bytes[7] << 24)),
    .samples = (int)(bytes[8] | ((uint32_t)bytes[9] << 8) |
                     ((uint32_t)bytes[10] << 16) | ((uint32_t)bytes[11] << 24)),
  };
  ioe_write(AM_AUDIO_CTRL, &control);
  return 12;
}

size_t audio_play_write(const void *buf, size_t offset, size_t len) {
  (void)offset;
  AM_AUDIO_PLAY_T play = {
    .buf = RANGE((void *)buf, (uint8_t *)buf + len),
  };
  ioe_write(AM_AUDIO_PLAY, &play);
  return len;
}

size_t fb_write(const void *buf, size_t offset, size_t len) {
  AM_GPU_CONFIG_T cfg = io_read(AM_GPU_CONFIG);
  const uint32_t *pixels = (const uint32_t *)buf;
  size_t pixel_offset = offset / sizeof(uint32_t);
  size_t nr_pixels = len / sizeof(uint32_t);
  while (nr_pixels > 0) {
    int x = pixel_offset % cfg.width;
    int y = pixel_offset / cfg.width;
    int room = cfg.width - x;
    int n = nr_pixels < (size_t)room ? (int)nr_pixels : room;
    io_write(AM_GPU_FBDRAW, x, y, (void *)pixels, n, 1, false);
    pixels += n;
    pixel_offset += n;
    nr_pixels -= n;
  }
  return len;
}

void init_device() {
  Log("Initializing devices...");
  ioe_init();
}
''',
        encoding="ascii",
    )

    (nanos / "src/fs.c").write_text(
        r'''#include <fs.h>

typedef size_t (*ReadFn) (void *buf, size_t offset, size_t len);
typedef size_t (*WriteFn) (const void *buf, size_t offset, size_t len);

typedef struct {
  char *name;
  size_t size;
  size_t disk_offset;
  ReadFn read;
  WriteFn write;
} Finfo;

enum {FD_STDIN, FD_STDOUT, FD_STDERR, FD_FB, FD_EVENTS, FD_DISPINFO, FD_SBCTL, FD_SB};

size_t ramdisk_read(void *buf, size_t offset, size_t len);
size_t ramdisk_write(const void *buf, size_t offset, size_t len);
size_t get_ramdisk_size();
size_t serial_write(const void *buf, size_t offset, size_t len);
size_t events_read(void *buf, size_t offset, size_t len);
size_t dispinfo_read(void *buf, size_t offset, size_t len);
size_t fb_write(const void *buf, size_t offset, size_t len);
size_t audio_status_read(void *buf, size_t offset, size_t len);
size_t audio_control_write(const void *buf, size_t offset, size_t len);
size_t audio_play_write(const void *buf, size_t offset, size_t len);

size_t invalid_read(void *buf, size_t offset, size_t len) {
  panic("should not reach here");
  return 0;
}

size_t invalid_write(const void *buf, size_t offset, size_t len) {
  panic("should not reach here");
  return 0;
}

static Finfo file_table[] __attribute__((used)) = {
  [FD_STDIN]    = {"stdin", 0, 0, invalid_read, invalid_write},
  [FD_STDOUT]   = {"stdout", 0, 0, invalid_read, serial_write},
  [FD_STDERR]   = {"stderr", 0, 0, invalid_read, serial_write},
  [FD_FB]       = {"/dev/fb", 0, 0, invalid_read, fb_write},
  [FD_EVENTS]   = {"/dev/events", 0, 0, events_read, invalid_write},
  [FD_DISPINFO] = {"/proc/dispinfo", 0, 0, dispinfo_read, invalid_write},
  [FD_SBCTL]    = {"/dev/sbctl", 4, 0, audio_status_read, audio_control_write},
  [FD_SB]       = {"/dev/sb", 0, 0, invalid_read, audio_play_write},
#include "files.h"
};

#define NR_FILES LENGTH(file_table)
static size_t open_offset[NR_FILES];

void init_fs() {
  AM_GPU_CONFIG_T cfg = io_read(AM_GPU_CONFIG);
  file_table[FD_FB].size = cfg.width * cfg.height * sizeof(uint32_t);
}

static int find_file(const char *pathname) {
  for (int i = 0; i < NR_FILES; i++) {
    if (strcmp(pathname, file_table[i].name) == 0) {
      return i;
    }
  }
  return -1;
}

int fs_open(const char *pathname, int flags, int mode) {
  (void)flags;
  (void)mode;
  int fd = find_file(pathname);
  if (fd >= 0) {
    open_offset[fd] = 0;
  }
  return fd;
}

size_t fs_read(int fd, void *buf, size_t len) {
  if (fd < 0 || fd >= NR_FILES) {
    return -1;
  }
  Finfo *f = &file_table[fd];
  size_t actual = len;
  if (f->read == NULL) {
    if (open_offset[fd] >= f->size) {
      return 0;
    }
    size_t avail = f->size - open_offset[fd];
    actual = len < avail ? len : avail;
    ramdisk_read(buf, f->disk_offset + open_offset[fd], actual);
  } else {
    actual = f->read(buf, open_offset[fd], len);
  }
  open_offset[fd] += actual;
  return actual;
}

size_t fs_write(int fd, const void *buf, size_t len) {
  if (fd < 0 || fd >= NR_FILES) {
    return -1;
  }
  Finfo *f = &file_table[fd];
  size_t actual = len;
  if (f->write == NULL) {
    if (open_offset[fd] >= f->size) {
      return 0;
    }
    size_t avail = f->size - open_offset[fd];
    actual = len < avail ? len : avail;
    ramdisk_write(buf, f->disk_offset + open_offset[fd], actual);
  } else {
    actual = f->write(buf, open_offset[fd], len);
  }
  open_offset[fd] += actual;
  return actual;
}

size_t fs_lseek(int fd, size_t offset, int whence) {
  if (fd < 0 || fd >= NR_FILES) {
    return -1;
  }
  Finfo *f = &file_table[fd];
  size_t next = 0;
  if (whence == SEEK_SET) {
    next = offset;
  } else if (whence == SEEK_CUR) {
    next = open_offset[fd] + offset;
  } else if (whence == SEEK_END) {
    next = f->size + offset;
  } else {
    return -1;
  }
  if (next > f->size) {
    return -1;
  }
  open_offset[fd] = next;
  return next;
}

int fs_close(int fd) {
  if (fd < 0 || fd >= NR_FILES) {
    return -1;
  }
  return 0;
}
''',
        encoding="ascii",
    )

    if vme:
        (nanos / "src/loader.c").write_text(
            r'''#include <proc.h>
#include <memory.h>
#include <elf.h>
#include <fs.h>
#include <string.h>

#ifdef __LP64__
# define Elf_Ehdr Elf64_Ehdr
# define Elf_Phdr Elf64_Phdr
#else
# define Elf_Ehdr Elf32_Ehdr
# define Elf_Phdr Elf32_Phdr
#endif

int fs_open(const char *pathname, int flags, int mode);
size_t fs_read(int fd, void *buf, size_t len);
size_t fs_lseek(int fd, size_t offset, int whence);
int fs_close(int fd);

#define USTACK_PAGES 8
#define USER_STACK_TOP 0x80000000u
#define EXEC_MAX_ARGS 16
#define EXEC_STRING_MAX 128

typedef struct {
  int argc;
  int envc;
  char args[EXEC_MAX_ARGS][EXEC_STRING_MAX];
  char envs[EXEC_MAX_ARGS][EXEC_STRING_MAX];
} ExecArgs;

static ExecArgs exec_args;
static uintptr_t exec_argv_guest;
static uintptr_t exec_envp_guest;

static void copy_string(char *dst, const char *src) {
  int i = 0;
  if (src != NULL) {
    for (; i < EXEC_STRING_MAX - 1 && src[i] != '\0'; i++) {
      dst[i] = src[i];
    }
  }
  dst[i] = '\0';
}

static int copy_vector(uintptr_t vector, char dst[][EXEC_STRING_MAX]) {
  int count = 0;
  if (vector == 0) return 0;
  while (count < EXEC_MAX_ARGS) {
    const char *src = ((const char **)vector)[count];
    if (src == NULL) break;
    copy_string(dst[count], src);
    count++;
  }
  return count;
}

static void capture_exec_args(const char *filename, const char **argv,
                              const char **envp) {
  memset(&exec_args, 0, sizeof(exec_args));
  exec_args.argc = copy_vector((uintptr_t)argv, exec_args.args);
  if (exec_args.argc == 0) {
    copy_string(exec_args.args[0], filename);
    exec_args.argc = 1;
  }
  exec_args.envc = copy_vector((uintptr_t)envp, exec_args.envs);
}

static uintptr_t build_stack(uint8_t *stack_pa) {
  const uintptr_t stack_base = USER_STACK_TOP - USTACK_PAGES * PGSIZE;
  uintptr_t argv_guest[EXEC_MAX_ARGS];
  uintptr_t envp_guest[EXEC_MAX_ARGS];
  uintptr_t sp = USER_STACK_TOP;

  for (int i = exec_args.argc - 1; i >= 0; i--) {
    size_t len = strlen(exec_args.args[i]) + 1;
    sp = (sp - (uintptr_t)len) & ~(uintptr_t)3;
    memcpy(stack_pa + sp - stack_base, exec_args.args[i], len);
    argv_guest[i] = sp;
  }
  for (int i = exec_args.envc - 1; i >= 0; i--) {
    size_t len = strlen(exec_args.envs[i]) + 1;
    sp = (sp - (uintptr_t)len) & ~(uintptr_t)3;
    memcpy(stack_pa + sp - stack_base, exec_args.envs[i], len);
    envp_guest[i] = sp;
  }

  sp = (sp - (uintptr_t)(exec_args.envc + 1) * sizeof(uintptr_t)) & ~(uintptr_t)15;
  uintptr_t envp = sp;
  uintptr_t *env_words = (uintptr_t *)(stack_pa + sp - stack_base);
  for (int i = 0; i < exec_args.envc; i++) env_words[i] = envp_guest[i];
  env_words[exec_args.envc] = 0;

  sp -= (uintptr_t)(exec_args.argc + 1) * sizeof(uintptr_t);
  uintptr_t argv = sp;
  uintptr_t *arg_words = (uintptr_t *)(stack_pa + sp - stack_base);
  for (int i = 0; i < exec_args.argc; i++) arg_words[i] = argv_guest[i];
  arg_words[exec_args.argc] = 0;

  exec_argv_guest = argv;
  exec_envp_guest = envp;
  sp &= ~(uintptr_t)15;
  return sp;
}

static uintptr_t loader(PCB *pcb, const char *filename, uintptr_t *args_ptr) {
  int fd = fs_open(filename, 0, 0);
  assert(fd >= 0);

  Elf_Ehdr eh;
  assert(fs_read(fd, &eh, sizeof(eh)) == sizeof(eh));
  assert(*(uint32_t *)eh.e_ident == 0x464c457f);

  uintptr_t min_va = (uintptr_t)-1;
  uintptr_t max_va = 0;
  for (int i = 0; i < eh.e_phnum; i++) {
    Elf_Phdr ph;
    fs_lseek(fd, eh.e_phoff + i * sizeof(ph), SEEK_SET);
    assert(fs_read(fd, &ph, sizeof(ph)) == sizeof(ph));
    if (ph.p_type != PT_LOAD) {
      continue;
    }
    uintptr_t start = ROUNDDOWN(ph.p_vaddr, PGSIZE);
    uintptr_t end = ph.p_vaddr + ph.p_memsz;
    if (start < min_va) min_va = start;
    if (end > max_va) max_va = end;
  }
  assert(min_va < max_va);

  size_t nr_pages = (ROUNDUP(max_va, PGSIZE) - min_va) / PGSIZE;
  uint8_t *pa_base = new_page(nr_pages);
  for (size_t i = 0; i < nr_pages; i++) {
    map(&pcb->as, (void *)(min_va + i * PGSIZE), pa_base + i * PGSIZE,
        MMAP_READ | MMAP_WRITE);
  }

  for (int i = 0; i < eh.e_phnum; i++) {
    Elf_Phdr ph;
    fs_lseek(fd, eh.e_phoff + i * sizeof(ph), SEEK_SET);
    assert(fs_read(fd, &ph, sizeof(ph)) == sizeof(ph));
    if (ph.p_type != PT_LOAD) {
      continue;
    }
    fs_lseek(fd, ph.p_offset, SEEK_SET);
    assert(fs_read(fd, pa_base + (ph.p_vaddr - min_va), ph.p_filesz) == ph.p_filesz);
  }
  fs_close(fd);

  uint8_t *stack_pa = new_page(USTACK_PAGES);
  for (int i = 0; i < USTACK_PAGES; i++) {
    map(&pcb->as,
        (void *)(USER_STACK_TOP - (uintptr_t)(USTACK_PAGES - i) * PGSIZE),
        stack_pa + (uintptr_t)i * PGSIZE, MMAP_READ | MMAP_WRITE);
  }

  *args_ptr = build_stack(stack_pa);

  pcb->max_brk = ROUNDUP(max_va, PGSIZE);
  return eh.e_entry;
}

static void load_and_jump(PCB *pcb, const char *filename) {
  protect(&pcb->as);
  uintptr_t args = 0;
  uintptr_t entry = loader(pcb, filename, &args);
  current = pcb;
  Log("Jump to entry = %p", entry);
  uintptr_t satp_value = (uintptr_t)1u << 31 | ((uintptr_t)pcb->as.ptr >> 12);
  asm volatile(
      "csrw satp, %0\n\t"
      "sfence.vma\n\t"
      "mv sp, %1\n\t"
      "mv a0, %3\n\t"
      "mv a1, %4\n\t"
      "mv a2, %5\n\t"
      "jr %2"
      : : "r"(satp_value), "r"(args), "r"(entry),
          "r"(exec_args.argc), "r"(exec_argv_guest), "r"(exec_envp_guest));
  while (1);
}

void naive_uload(PCB *pcb, const char *filename) {
  static const char *initial_env[] = {"NAVY_HOME=/", NULL};
  capture_exec_args(filename, NULL, initial_env);
  load_and_jump(pcb, filename);
}

bool process_is_managed(void);

void naive_execve(const char *filename, const char **argv, const char **envp) {
  static PCB execve_pcb;
  PCB *target = process_is_managed() ? current : &execve_pcb;
  if (target == &execve_pcb) memset(target, 0, sizeof(*target));
  capture_exec_args(filename, argv, envp);
  Log("execve: %s", filename);
  load_and_jump(target, filename);
}
''',
            encoding="ascii",
        )
    else:
        (nanos / "src/loader.c").write_text(
            r'''#include <proc.h>
#include <elf.h>
#include <fs.h>
#include <string.h>

#ifdef __LP64__
# define Elf_Ehdr Elf64_Ehdr
# define Elf_Phdr Elf64_Phdr
#else
# define Elf_Ehdr Elf32_Ehdr
# define Elf_Phdr Elf32_Phdr
#endif

int fs_open(const char *pathname, int flags, int mode);
size_t fs_read(int fd, void *buf, size_t len);
size_t fs_lseek(int fd, size_t offset, int whence);
int fs_close(int fd);

#define EXEC_MAX_ARGS 16
#define EXEC_STRING_MAX 128
#define EXEC_STACK_TOP 0x87fff000u
#define EXEC_STACK_SIZE (8 * PGSIZE)

typedef struct {
  int argc;
  int envc;
  char args[EXEC_MAX_ARGS][EXEC_STRING_MAX];
  char envs[EXEC_MAX_ARGS][EXEC_STRING_MAX];
} ExecArgs;

static ExecArgs exec_args;
static uintptr_t exec_argv_guest;
static uintptr_t exec_envp_guest;

static void copy_string(char *dst, const char *src) {
  int i = 0;
  if (src != NULL) {
    for (; i < EXEC_STRING_MAX - 1 && src[i] != '\0'; i++) {
      dst[i] = src[i];
    }
  }
  dst[i] = '\0';
}

static int copy_vector(uintptr_t vector, char dst[][EXEC_STRING_MAX]) {
  int count = 0;
  if (vector == 0) return 0;
  while (count < EXEC_MAX_ARGS) {
    const char *src = ((const char **)vector)[count];
    if (src == NULL) break;
    copy_string(dst[count], src);
    count++;
  }
  return count;
}

static void capture_exec_args(const char *filename, const char **argv,
                              const char **envp) {
  memset(&exec_args, 0, sizeof(exec_args));
  exec_args.argc = copy_vector((uintptr_t)argv, exec_args.args);
  if (exec_args.argc == 0) {
    copy_string(exec_args.args[0], filename);
    exec_args.argc = 1;
  }
  exec_args.envc = copy_vector((uintptr_t)envp, exec_args.envs);
}

static uintptr_t build_stack(void) {
  const uintptr_t stack_base = EXEC_STACK_TOP - EXEC_STACK_SIZE;
  uintptr_t argv_guest[EXEC_MAX_ARGS];
  uintptr_t envp_guest[EXEC_MAX_ARGS];
  uintptr_t sp = EXEC_STACK_TOP;

  for (int i = exec_args.argc - 1; i >= 0; i--) {
    size_t len = strlen(exec_args.args[i]) + 1;
    sp = (sp - (uintptr_t)len) & ~(uintptr_t)3;
    memcpy((void *)sp, exec_args.args[i], len);
    argv_guest[i] = sp;
  }
  for (int i = exec_args.envc - 1; i >= 0; i--) {
    size_t len = strlen(exec_args.envs[i]) + 1;
    sp = (sp - (uintptr_t)len) & ~(uintptr_t)3;
    memcpy((void *)sp, exec_args.envs[i], len);
    envp_guest[i] = sp;
  }

  sp = (sp - (uintptr_t)(exec_args.envc + 1) * sizeof(uintptr_t)) & ~(uintptr_t)15;
  uintptr_t envp = sp;
  uintptr_t *env_words = (uintptr_t *)envp;
  for (int i = 0; i < exec_args.envc; i++) env_words[i] = envp_guest[i];
  env_words[exec_args.envc] = 0;

  sp -= (uintptr_t)(exec_args.argc + 1) * sizeof(uintptr_t);
  uintptr_t argv = sp;
  uintptr_t *arg_words = (uintptr_t *)argv;
  for (int i = 0; i < exec_args.argc; i++) arg_words[i] = argv_guest[i];
  arg_words[exec_args.argc] = 0;

  exec_argv_guest = argv;
  exec_envp_guest = envp;
  sp &= ~(uintptr_t)15;
  (void)stack_base;
  return sp;
}

static uintptr_t loader(PCB *pcb, const char *filename, uintptr_t *args_ptr) {
  (void)pcb;
  int fd = fs_open(filename, 0, 0);
  assert(fd >= 0);

  Elf_Ehdr eh;
  assert(fs_read(fd, &eh, sizeof(eh)) == sizeof(eh));
  assert(*(uint32_t *)eh.e_ident == 0x464c457f);

  for (int i = 0; i < eh.e_phnum; i++) {
    Elf_Phdr ph;
    fs_lseek(fd, eh.e_phoff + i * sizeof(ph), SEEK_SET);
    assert(fs_read(fd, &ph, sizeof(ph)) == sizeof(ph));
    if (ph.p_type != PT_LOAD) {
      continue;
    }
    fs_lseek(fd, ph.p_offset, SEEK_SET);
    assert(fs_read(fd, (void *)ph.p_vaddr, ph.p_filesz) == ph.p_filesz);
    memset((void *)(ph.p_vaddr + ph.p_filesz), 0, ph.p_memsz - ph.p_filesz);
  }
  fs_close(fd);
  *args_ptr = build_stack();
  return eh.e_entry;
}

static void load_and_jump(PCB *pcb, const char *filename) {
  uintptr_t args = 0;
  uintptr_t entry = loader(pcb, filename, &args);
  current = pcb;
  Log("Jump to entry = %p", entry);
  asm volatile(
      "mv sp, %0\n\t"
      "mv a0, %1\n\t"
      "mv a1, %2\n\t"
      "mv a2, %3\n\t"
      "jr %4"
      : : "r"(args), "r"(exec_args.argc), "r"(exec_argv_guest),
          "r"(exec_envp_guest), "r"(entry));
  while (1);
}

void naive_uload(PCB *pcb, const char *filename) {
  static const char *initial_env[] = {"NAVY_HOME=/", NULL};
  capture_exec_args(filename, NULL, initial_env);
  load_and_jump(pcb, filename);
}

bool process_is_managed(void);

void naive_execve(const char *filename, const char **argv, const char **envp) {
  static PCB execve_pcb;
  PCB *target = process_is_managed() ? current : &execve_pcb;
  if (target == &execve_pcb) memset(target, 0, sizeof(*target));
  capture_exec_args(filename, argv, envp);
  Log("execve: %s -> entry", filename);
  load_and_jump(target, filename);
}
''',
        encoding="ascii",
    )

    (nanos / "src/syscall.c").write_text(
        r'''#include <common.h>
#include <proc.h>
#include "syscall.h"

#define SYS_pipe 20
#define SYS_dup 21
#define SYS_dup2 22
#define SYS_ftruncate 23
#define SYS_mmap 24
#define SYS_munmap 25
#define SYS_memfd_create 26
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

int fs_open(const char *pathname, int flags, int mode);
size_t fs_read(int fd, void *buf, size_t len);
size_t fs_write(int fd, const void *buf, size_t len);
size_t fs_lseek(int fd, size_t offset, int whence);
int fs_close(int fd);
int mm_brk(uintptr_t brk);
void naive_uload(PCB *pcb, const char *filename);
void naive_execve(const char *filename, const char **argv, const char **envp);
bool process_is_managed(void);
int process_slot(void);
void *new_page(size_t nr_page);
void map(AddrSpace *as, void *vaddr, void *paddr, int prot);
Context *process_schedule(Context *prev);
Context *process_fork(Context *parent_ctx);
Context *process_exit(Context *prev, uintptr_t status);
Context *process_wait(Context *prev, int *status);

#define FD_TABLES 17
#define MAX_PROCESS_FDS 32
#define MAX_PIPES 8
#define PIPE_CAPACITY 4096
#define MAX_MEMFDS 8

typedef long ssize_t;

enum {
  FD_NONE,
  FD_SERIAL,
  FD_FILE,
  FD_PIPE_READ,
  FD_PIPE_WRITE,
  FD_MEMFD,
};

typedef struct {
  int kind;
  int target;
} FdEntry;

typedef struct {
  int used;
  int nonblock;
  size_t read_pos;
  size_t size;
  int readers;
  int writers;
  uint8_t data[PIPE_CAPACITY];
} Pipe;

typedef struct {
  int used;
  size_t size;
  size_t capacity;
  uint8_t *data;
} MemFd;

static FdEntry fd_table[FD_TABLES][MAX_PROCESS_FDS];
static size_t fd_offset[FD_TABLES][MAX_PROCESS_FDS];
static int fd_initialized[FD_TABLES];
static Pipe pipes[MAX_PIPES];
static MemFd memfds[MAX_MEMFDS];
static uintptr_t mmap_next[FD_TABLES];
static uintptr_t mmap_addr[FD_TABLES][MAX_PROCESS_FDS];
static size_t mmap_length[FD_TABLES][MAX_PROCESS_FDS];

static int fd_owner(void) {
  int slot = process_slot();
  return slot >= 0 && slot < FD_TABLES - 1 ? slot : FD_TABLES - 1;
}

static void fd_init(int slot) {
  if (fd_initialized[slot]) return;
  fd_initialized[slot] = 1;
  fd_table[slot][0] = (FdEntry){FD_SERIAL, 0};
  fd_table[slot][1] = (FdEntry){FD_SERIAL, 1};
  fd_table[slot][2] = (FdEntry){FD_SERIAL, 2};
}

static void pipe_release(int pipe_id, int kind) {
  if (pipe_id < 0 || pipe_id >= MAX_PIPES || !pipes[pipe_id].used) return;
  if (kind == FD_PIPE_READ && pipes[pipe_id].readers > 0) {
    pipes[pipe_id].readers--;
  }
  if (kind == FD_PIPE_WRITE && pipes[pipe_id].writers > 0) {
    pipes[pipe_id].writers--;
  }
  if (pipes[pipe_id].readers == 0 && pipes[pipe_id].writers == 0) {
    memset(&pipes[pipe_id], 0, sizeof(pipes[pipe_id]));
  }
}

static void fd_drop(FdEntry *entry) {
  if (entry->kind == FD_PIPE_READ || entry->kind == FD_PIPE_WRITE) {
    pipe_release(entry->target, entry->kind);
  }
  entry->kind = FD_NONE;
  entry->target = -1;
}

static void fd_release_table(int slot) {
  fd_init(slot);
  for (int fd = 0; fd < MAX_PROCESS_FDS; fd++) {
    fd_drop(&fd_table[slot][fd]);
    fd_offset[slot][fd] = 0;
    mmap_addr[slot][fd] = 0;
    mmap_length[slot][fd] = 0;
  }
  mmap_next[slot] = 0;
  fd_initialized[slot] = 0;
}

static void fd_retain(FdEntry entry) {
  if (entry.kind == FD_PIPE_READ) pipes[entry.target].readers++;
  if (entry.kind == FD_PIPE_WRITE) pipes[entry.target].writers++;
}

static int fd_assign(int slot, int fd, FdEntry entry) {
  if (fd < 0 || fd >= MAX_PROCESS_FDS || entry.kind == FD_NONE) return -1;
  fd_drop(&fd_table[slot][fd]);
  fd_table[slot][fd] = entry;
  fd_retain(entry);
  return fd;
}

static int fd_alloc(int slot) {
  fd_init(slot);
  for (int fd = 3; fd < MAX_PROCESS_FDS; fd++) {
    if (fd_table[slot][fd].kind == FD_NONE) return fd;
  }
  return -1;
}

void process_clone_fds(int parent_index, int child_index) {
  int parent = parent_index >= 0 && parent_index < FD_TABLES - 1
                   ? parent_index : FD_TABLES - 1;
  if (child_index < 0 || child_index >= FD_TABLES - 1) return;
  fd_init(parent);
  fd_release_table(child_index);
  fd_init(child_index);
  for (int fd = 0; fd < MAX_PROCESS_FDS; fd++) {
    fd_table[child_index][fd] = fd_table[parent][fd];
    fd_offset[child_index][fd] = fd_offset[parent][fd];
    fd_retain(fd_table[child_index][fd]);
  }
}

void process_release_fds(int process_index) {
  if (process_index >= 0 && process_index < FD_TABLES - 1) {
    fd_release_table(process_index);
  }
}

static int pipe_create(int slot, int pipefd[2], int flags) {
  if (pipefd == NULL) return -1;
  int pipe_id = -1;
  for (int i = 0; i < MAX_PIPES; i++) {
    if (!pipes[i].used) {
      pipe_id = i;
      break;
    }
  }
  int read_fd = fd_alloc(slot);
  if (pipe_id < 0 || read_fd < 0) return -1;
  pipes[pipe_id].used = 1;
  pipes[pipe_id].nonblock = flags != 0;
  pipes[pipe_id].readers = 1;
  pipes[pipe_id].writers = 1;
  fd_table[slot][read_fd] = (FdEntry){FD_PIPE_READ, pipe_id};
  int write_fd = fd_alloc(slot);
  if (write_fd < 0) {
    fd_drop(&fd_table[slot][read_fd]);
    memset(&pipes[pipe_id], 0, sizeof(pipes[pipe_id]));
    return -1;
  }
  fd_table[slot][write_fd] = (FdEntry){FD_PIPE_WRITE, pipe_id};
  pipefd[0] = read_fd;
  pipefd[1] = write_fd;
  return 0;
}

static ssize_t pipe_read(Pipe *pipe, void *buf, size_t len) {
  if (len == 0) return 0;
  if (pipe->size == 0) return pipe->writers == 0 ? 0 : -1;
  size_t actual = len < pipe->size ? len : pipe->size;
  uint8_t *out = (uint8_t *)buf;
  for (size_t i = 0; i < actual; i++) {
    out[i] = pipe->data[(pipe->read_pos + i) % PIPE_CAPACITY];
  }
  pipe->read_pos = (pipe->read_pos + actual) % PIPE_CAPACITY;
  pipe->size -= actual;
  return (ssize_t)actual;
}

static ssize_t pipe_write(Pipe *pipe, const void *buf, size_t len) {
  if (pipe->readers == 0) return -1;
  size_t room = PIPE_CAPACITY - pipe->size;
  if (room == 0) return -1;
  size_t actual = len < room ? len : room;
  const uint8_t *in = (const uint8_t *)buf;
  size_t write_pos = (pipe->read_pos + pipe->size) % PIPE_CAPACITY;
  for (size_t i = 0; i < actual; i++) {
    pipe->data[(write_pos + i) % PIPE_CAPACITY] = in[i];
  }
  pipe->size += actual;
  return (ssize_t)actual;
}

static int memfd_create_slot(void) {
  for (int i = 0; i < MAX_MEMFDS; i++) {
    if (!memfds[i].used) {
      memfds[i] = (MemFd){.used = 1};
      return i;
    }
  }
  return -1;
}

static int memfd_resize(int memfd, size_t size) {
  if (memfd < 0 || memfd >= MAX_MEMFDS || !memfds[memfd].used) return -1;
  size_t capacity = (size + PGSIZE - 1) & ~(size_t)(PGSIZE - 1);
  if (capacity > memfds[memfd].capacity) {
    uint8_t *data = (uint8_t *)new_page(capacity / PGSIZE);
    if (memfds[memfd].data != NULL && memfds[memfd].size != 0) {
      memcpy(data, memfds[memfd].data, memfds[memfd].size);
    }
    memfds[memfd].data = data;
    memfds[memfd].capacity = capacity;
  }
  memfds[memfd].size = size;
  return 0;
}

static int fd_memfd(int slot, int fd) {
  fd_init(slot);
  if (fd < 0 || fd >= MAX_PROCESS_FDS ||
      fd_table[slot][fd].kind != FD_MEMFD) return -1;
  return fd_table[slot][fd].target;
}

static int fd_ftruncate(int slot, int fd, size_t size) {
  return memfd_resize(fd_memfd(slot, fd), size);
}

static void *fd_mmap(int slot, size_t length, int prot, int fd, size_t offset) {
  int memfd = fd_memfd(slot, fd);
  if (memfd < 0 || length == 0 || offset > memfds[memfd].size ||
      length > memfds[memfd].size - offset) return (void *)-1;
  size_t mapped = (length + PGSIZE - 1) & ~(size_t)(PGSIZE - 1);
  uintptr_t base = mmap_addr[slot][fd];
  if (base == 0) {
    base = mmap_next[slot];
    if (base == 0) base = (current->max_brk + PGSIZE - 1) & ~(uintptr_t)(PGSIZE - 1);
  }
  if (base < 0x40000000u || base + mapped > 0x80000000u) return (void *)-1;
  for (size_t page = 0; page < mapped; page += PGSIZE) {
    map(&current->as, (void *)(base + page),
        memfds[memfd].data + offset + page, prot);
  }
  mmap_addr[slot][fd] = base;
  if (mmap_length[slot][fd] < mapped) mmap_length[slot][fd] = mapped;
  if (mmap_next[slot] < base + mapped) mmap_next[slot] = base + mapped;
  return (void *)base;
}

static int fd_munmap(int slot, uintptr_t addr, size_t length) {
  (void)length;
  fd_init(slot);
  for (int fd = 0; fd < MAX_PROCESS_FDS; fd++) {
    if (mmap_addr[slot][fd] == addr && length <= mmap_length[slot][fd]) {
      mmap_addr[slot][fd] = 0;
      mmap_length[slot][fd] = 0;
      return 0;
    }
  }
  return -1;
}

static ssize_t fd_read(int slot, int fd, void *buf, size_t len) {
  fd_init(slot);
  if (fd < 0 || fd >= MAX_PROCESS_FDS) return -1;
  FdEntry entry = fd_table[slot][fd];
  if (entry.kind == FD_PIPE_READ) return pipe_read(&pipes[entry.target], buf, len);
  if (entry.kind == FD_SERIAL) {
    return entry.target == 0 ? (ssize_t)fs_read(0, buf, len) : -1;
  }
  if (entry.kind == FD_FILE) return (ssize_t)fs_read(entry.target, buf, len);
  if (entry.kind == FD_MEMFD) {
    MemFd *memfd = &memfds[entry.target];
    if (fd_offset[slot][fd] >= memfd->size) return 0;
    size_t avail = memfd->size - fd_offset[slot][fd];
    size_t actual = len < avail ? len : avail;
    memcpy(buf, memfd->data + fd_offset[slot][fd], actual);
    fd_offset[slot][fd] += actual;
    return (ssize_t)actual;
  }
  return -1;
}

static ssize_t fd_write(int slot, int fd, const void *buf, size_t len) {
  fd_init(slot);
  if (fd < 0 || fd >= MAX_PROCESS_FDS) return -1;
  FdEntry entry = fd_table[slot][fd];
  if (entry.kind == FD_PIPE_WRITE) return pipe_write(&pipes[entry.target], buf, len);
  if (entry.kind == FD_SERIAL) {
    return (entry.target == 1 || entry.target == 2) ?
      (ssize_t)fs_write(entry.target, buf, len) : -1;
  }
  if (entry.kind == FD_FILE) return (ssize_t)fs_write(entry.target, buf, len);
  if (entry.kind == FD_MEMFD) {
    MemFd *memfd = &memfds[entry.target];
    if (fd_offset[slot][fd] >= memfd->size) return 0;
    size_t avail = memfd->size - fd_offset[slot][fd];
    size_t actual = len < avail ? len : avail;
    memcpy(memfd->data + fd_offset[slot][fd], buf, actual);
    fd_offset[slot][fd] += actual;
    return (ssize_t)actual;
  }
  return -1;
}

static int fd_open(int slot, const char *pathname, int flags, int mode) {
  int raw_fd = fs_open(pathname, flags, mode);
  if (raw_fd < 0) return raw_fd;
  fd_init(slot);
  int guest_fd = raw_fd;
  if (guest_fd < 0 || guest_fd >= MAX_PROCESS_FDS ||
      fd_table[slot][guest_fd].kind != FD_NONE) {
    guest_fd = fd_alloc(slot);
  }
  if (guest_fd < 0) {
    fs_close(raw_fd);
    return -1;
  }
  fd_table[slot][guest_fd] = (FdEntry){FD_FILE, raw_fd};
  fd_offset[slot][guest_fd] = 0;
  return guest_fd;
}

static int fd_close(int slot, int fd) {
  fd_init(slot);
  if (fd < 0 || fd >= MAX_PROCESS_FDS) return -1;
  FdEntry entry = fd_table[slot][fd];
  if (entry.kind == FD_NONE) return -1;
  if (entry.kind == FD_FILE) fs_close(entry.target);
  fd_drop(&fd_table[slot][fd]);
  fd_offset[slot][fd] = 0;
  return 0;
}

static int fd_lseek(int slot, int fd, size_t offset, int whence) {
  fd_init(slot);
  if (fd < 0 || fd >= MAX_PROCESS_FDS) return -1;
  FdEntry entry = fd_table[slot][fd];
  if (entry.kind == FD_FILE) return fs_lseek(entry.target, offset, whence);
  if (entry.kind != FD_MEMFD) return -1;
  MemFd *memfd = &memfds[entry.target];
  size_t next = 0;
  if (whence == SEEK_SET) next = offset;
  else if (whence == SEEK_CUR) next = fd_offset[slot][fd] + offset;
  else if (whence == SEEK_END) next = memfd->size + offset;
  else return -1;
  if (next > memfd->size) return -1;
  fd_offset[slot][fd] = next;
  return (int)next;
}

static PCB batch_pcb;
static const char *batch_programs[] = {
  "/bin/dummy",
};
static size_t next_batch_program = 0;

static void exit_current(uintptr_t status) {
  if (next_batch_program < LENGTH(batch_programs)) {
    const char *next = batch_programs[next_batch_program++];
    Log("Loading next program: %s", next);
    naive_uload(&batch_pcb, next);
  }
  halt(status);
}

Context *do_syscall(Context *c) {
  uintptr_t a[4];
  a[0] = c->GPR1;
  a[1] = c->GPR2;
  a[2] = c->GPR3;
  a[3] = c->GPR4;

  switch (a[0]) {
    case SYS_exit:
    {
      Context *next = process_exit(c, a[1]);
      if (next != NULL) return next;
      exit_current(a[1]);
      break;
    }
    case SYS_yield:
      c->GPRx = 0;
      return process_schedule(c);
    case SYS_fork:
      return process_fork(c);
    case SYS_open:
      c->GPRx = fd_open(fd_owner(), (const char *)a[1], a[2], a[3]);
      break;
    case SYS_read:
      c->GPRx = fd_read(fd_owner(), a[1], (void *)a[2], a[3]);
      break;
    case SYS_write:
      c->GPRx = fd_write(fd_owner(), a[1], (const void *)a[2], a[3]);
      break;
    case SYS_close:
      c->GPRx = fd_close(fd_owner(), a[1]);
      break;
    case SYS_lseek:
      c->GPRx = fd_lseek(fd_owner(), a[1], a[2], a[3]);
      break;
    case SYS_pipe:
      c->GPRx = pipe_create(fd_owner(), (int *)a[1], a[2]);
      break;
    case SYS_dup:
    {
      int slot = fd_owner();
      fd_init(slot);
      int new_fd = fd_alloc(slot);
      if (new_fd < 0 || a[1] < 0 || a[1] >= MAX_PROCESS_FDS ||
          fd_table[slot][a[1]].kind == FD_NONE) {
        c->GPRx = -1;
      } else {
        c->GPRx = fd_assign(slot, new_fd, fd_table[slot][a[1]]);
      }
      break;
    }
    case SYS_dup2:
    {
      int slot = fd_owner();
      fd_init(slot);
      if (a[1] < 0 || a[1] >= MAX_PROCESS_FDS || a[2] < 0 ||
          a[2] >= MAX_PROCESS_FDS || fd_table[slot][a[1]].kind == FD_NONE) {
        c->GPRx = -1;
      } else if (a[1] == a[2]) {
        c->GPRx = a[2];
      } else {
        c->GPRx = fd_assign(slot, a[2], fd_table[slot][a[1]]);
      }
      break;
    }
    case SYS_ftruncate:
      c->GPRx = fd_ftruncate(fd_owner(), a[1], a[2]);
      break;
    case SYS_mmap:
      c->GPRx = (uintptr_t)fd_mmap(fd_owner(), a[1], MMAP_READ | MMAP_WRITE,
                                   a[2], a[3]);
      break;
    case SYS_munmap:
      c->GPRx = fd_munmap(fd_owner(), a[1], a[2]);
      break;
    case SYS_memfd_create:
    {
      int slot = fd_owner();
      int memfd = memfd_create_slot();
      int fd = fd_alloc(slot);
      if (memfd < 0 || fd < 0) {
        if (memfd >= 0) memfds[memfd].used = 0;
        c->GPRx = -1;
      } else {
        fd_table[slot][fd] = (FdEntry){FD_MEMFD, memfd};
        fd_offset[slot][fd] = 0;
        c->GPRx = fd;
      }
      break;
    }
    case SYS_wait:
      return process_wait(c, (int *)a[1]);
    case SYS_brk:
      c->GPRx = mm_brk(a[1]);
      break;
    case SYS_gettimeofday:
    {
      struct timeval {
        long tv_sec;
        long tv_usec;
      } *tv = (void *)a[1];
      AM_TIMER_UPTIME_T uptime = io_read(AM_TIMER_UPTIME);
      tv->tv_sec = uptime.us / 1000000;
      tv->tv_usec = uptime.us % 1000000;
      c->GPRx = 0;
      break;
    }
    case SYS_execve:
      naive_execve((const char *)a[1], (const char **)a[2],
                   (const char **)a[3]);
      break;
    default:
      panic("Unhandled syscall ID = %d", a[0]);
  }
  return c;
}
''',
        encoding="ascii",
    )


def patch_libos(navy: Path, with_libc: bool = False, vme: bool = False) -> None:
    makefile = navy / "Makefile"
    text = makefile.read_text(encoding="ascii")
    if not with_libc:
        text = text.replace("LIBS += libc libos", "LIBS += libos")
        text = text.replace(
            "ifneq ($(findstring $(ISA), x86|mips32|riscv32|riscv32e|loongarch32r),)\nLIBS += compiler-rt\nendif\n",
            "",
        )
    makefile.write_text(text, encoding="ascii")

    if not with_libc:
        (navy / "tests/hello/hello.c").write_text(
        r'''#include <stdint.h>

#define SYS_yield 1
#define SYS_write 4
#define SYS_exit 0

extern int _syscall_(int, uintptr_t, uintptr_t, uintptr_t);

static void putstr(const char *s) {
  const char *p = s;
  while (*p) {
    p++;
  }
  _syscall_(SYS_write, 1, (uintptr_t)s, (uintptr_t)(p - s));
}

int main() {
  putstr("Hello World!\n");
  for (int i = 0; i < 3; i++) {
    putstr("Hello World from Navy-apps\n");
    for (volatile int j = 0; j < 100000; j++) {
    }
    _syscall_(SYS_yield, 0, 0, 0);
  }
  _syscall_(SYS_exit, 0, 0, 0);
  return 0;
}
''',
            encoding="ascii",
        )

        (navy / "tests/dummy/dummy.c").write_text(
        r'''#include <stdint.h>

#define SYS_write 4
#define SYS_exit 0

extern int _syscall_(int, uintptr_t, uintptr_t, uintptr_t);

static void putstr(const char *s) {
  const char *p = s;
  while (*p) {
    p++;
  }
  _syscall_(SYS_write, 1, (uintptr_t)s, (uintptr_t)(p - s));
}

int main() {
  putstr("Dummy from Navy-apps\n");
  _syscall_(SYS_exit, 0, 0, 0);
  return 0;
}
''',
            encoding="ascii",
        )

    (navy / "libs/libos/src/crt0/crt0.c").write_text(
        r'''#include <stdint.h>

int main(int argc, char *argv[], char *envp[]);
void _exit(int status);

extern char **environ;

void call_main(int argc, char **argv, char **envp) {
  environ = envp;
  _exit(main(argc, argv, envp));
  while (1) {
  }
}
''',
        encoding="ascii",
    )

    syscall_common = r'''#include <stdint.h>
#include <stddef.h>
#include "syscall.h"

#define SYS_pipe 20
#define SYS_dup 21
#define SYS_dup2 22
#define SYS_ftruncate 23
#define SYS_mmap 24
#define SYS_munmap 25
#define SYS_memfd_create 26

typedef long ssize_t;
typedef long off_t;
typedef int mode_t;
typedef int pid_t;
typedef long clock_t;

struct timezone;
struct stat {
  unsigned int st_mode;
};

#define S_IFCHR 0020000

#define _concat(x, y) x ## y
#define concat(x, y) _concat(x, y)
#define _args(n, list) concat(_arg, n) list
#define _arg0(a0, ...) a0
#define _arg1(a0, a1, ...) a1
#define _arg2(a0, a1, a2, ...) a2
#define _arg3(a0, a1, a2, a3, ...) a3
#define _arg4(a0, a1, a2, a3, a4, ...) a4
#define _arg5(a0, a1, a2, a3, a4, a5, ...) a5

#define SYSCALL  _args(0, ARGS_ARRAY)
#define GPR1 _args(1, ARGS_ARRAY)
#define GPR2 _args(2, ARGS_ARRAY)
#define GPR3 _args(3, ARGS_ARRAY)
#define GPR4 _args(4, ARGS_ARRAY)
#define GPRx _args(5, ARGS_ARRAY)

#if defined(__ISA_X86__)
# define ARGS_ARRAY ("int $0x80", "eax", "ebx", "ecx", "edx", "eax")
#elif defined(__ISA_MIPS32__)
# define ARGS_ARRAY ("syscall", "v0", "a0", "a1", "a2", "v0")
#elif defined(__riscv)
#ifdef __riscv_e
# define ARGS_ARRAY ("ecall", "a5", "a0", "a1", "a2", "a0")
#else
# define ARGS_ARRAY ("ecall", "a7", "a0", "a1", "a2", "a0")
#endif
#elif defined(__ISA_AM_NATIVE__)
# define ARGS_ARRAY ("call *0x100000", "rdi", "rsi", "rdx", "rcx", "rax")
#elif defined(__ISA_X86_64__)
# define ARGS_ARRAY ("int $0x80", "rdi", "rsi", "rdx", "rcx", "rax")
#elif defined(__ISA_LOONGARCH32R__)
# define ARGS_ARRAY ("syscall 0", "a7", "a0", "a1", "a2", "a0")
#else
#error _syscall_ is not implemented
#endif

intptr_t _syscall_(intptr_t type, intptr_t a0, intptr_t a1, intptr_t a2) {
  register intptr_t _gpr1 asm (GPR1) = type;
  register intptr_t _gpr2 asm (GPR2) = a0;
  register intptr_t _gpr3 asm (GPR3) = a1;
  register intptr_t _gpr4 asm (GPR4) = a2;
  register intptr_t ret asm (GPRx);
  asm volatile (SYSCALL : "=r" (ret) : "r"(_gpr1), "r"(_gpr2), "r"(_gpr3), "r"(_gpr4));
  return ret;
}

void _exit(int status) {
  _syscall_(SYS_exit, status, 0, 0);
  while (1);
}

int _open(const char *path, int flags, mode_t mode) {
  return _syscall_(SYS_open, (intptr_t)path, flags, mode);
}

int _write(int fd, void *buf, size_t count) {
  return _syscall_(SYS_write, fd, (intptr_t)buf, count);
}

static uintptr_t program_break = 0;
void *_sbrk(intptr_t increment) {
  if (program_break == 0) {
    program_break = 0x84000000;
  }
  uintptr_t old = program_break;
  uintptr_t next = old + increment;
  if (_syscall_(SYS_brk, next, 0, 0) != 0) {
    return (void *)-1;
  }
  program_break = next;
  return (void *)old;
}

int _read(int fd, void *buf, size_t count) {
  return _syscall_(SYS_read, fd, (intptr_t)buf, count);
}

int _close(int fd) {
  return _syscall_(SYS_close, fd, 0, 0);
}

off_t _lseek(int fd, off_t offset, int whence) {
  return _syscall_(SYS_lseek, fd, offset, whence);
}

int _gettimeofday(struct timeval *tv, struct timezone *tz) {
  (void)tz;
  return _syscall_(SYS_gettimeofday, (intptr_t)tv, 0, 0);
}

int _ftruncate(int fd, off_t length) {
  return _syscall_(SYS_ftruncate, fd, length, 0);
}

int ftruncate(int fd, off_t length) {
  return _ftruncate(fd, length);
}

void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
  (void)addr; (void)prot; (void)flags;
  return (void *)_syscall_(SYS_mmap, length, fd, offset);
}

int munmap(void *addr, size_t length) {
  return (int)_syscall_(SYS_munmap, (intptr_t)addr, length, 0);
}

int memfd_create(const char *name, unsigned int flags) {
  (void)name;
  return (int)_syscall_(SYS_memfd_create, flags, 0, 0);
}
'''

    snprintf_stub = r'''
#include <stdarg.h>
int vsnprintf(char *out, size_t n, const char *fmt, va_list ap);
int snprintf(char *out, size_t n, const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  int ret = vsnprintf(out, n, fmt, ap);
  va_end(ap);
  return ret;
}
'''

    syscall_suffix = r'''
int _execve(const char *fname, char * const argv[], char *const envp[]) {
  _syscall_(SYS_execve, (intptr_t)fname, (intptr_t)argv, (intptr_t)envp);
  return -1;
}

int _fstat(int fd, struct stat *buf) {
  (void)fd;
  if (buf != NULL) {
    buf->st_mode = S_IFCHR;
  }
  return 0;
}

int _stat(const char *fname, struct stat *buf) {
  (void)fname; (void)buf;
  return -1;
}

int _kill(int pid, int sig) {
  (void)pid; (void)sig;
  return -1;
}

pid_t _getpid() {
  return 1;
}

pid_t _fork() {
  return _syscall_(SYS_fork, 0, 0, 0);
}

pid_t vfork() {
  return _syscall_(SYS_fork, 0, 0, 0);
}

int _link(const char *d, const char *n) {
  (void)d; (void)n;
  return -1;
}

int _unlink(const char *n) {
  (void)n;
  return -1;
}

pid_t _wait(int *status) {
  return _syscall_(SYS_wait, (intptr_t)status, 0, 0);
}

clock_t _times(void *buf) {
  (void)buf;
  return 0;
}

int pipe(int pipefd[2]) {
  return _syscall_(SYS_pipe, (intptr_t)pipefd, 0, 0);
}

int pipe2(int pipefd[2], int flags) {
  return _syscall_(SYS_pipe, (intptr_t)pipefd, flags, 0);
}

int dup(int oldfd) {
  return _syscall_(SYS_dup, oldfd, 0, 0);
}

int dup2(int oldfd, int newfd) {
  return _syscall_(SYS_dup2, oldfd, newfd, 0);
}

unsigned int sleep(unsigned int seconds) {
  (void)seconds;
  return 0;
}
'''

    syscall_text = syscall_common
    if vme:
        # under VME the user image links at 0x40000000; start the heap at the
        # linker-provided end symbol instead of a fixed physical address
        syscall_text = syscall_text.replace(
            "    program_break = 0x84000000;",
            "    extern char end;\n    program_break = (uintptr_t)&end;",
        )
    # Full libc already provides snprintf; defining the wrapper in libos too
    # creates a duplicate symbol for applications such as PAL.
    if not with_libc:
        syscall_text += snprintf_stub
    syscall_text += syscall_suffix

    (navy / "libs/libos/src/syscall.c").write_text(syscall_text, encoding="ascii")


def patch_libc(navy: Path) -> None:
    libc_makefile = navy / "libs/libc/Makefile"
    text = libc_makefile.read_text(encoding="ascii")
    if "-D_COMPILING_NEWLIB" not in text:
        text = text.replace(
            "CFLAGS = -DNO_FLOATING_POINT",
            "CFLAGS = -DNO_FLOATING_POINT -D_COMPILING_NEWLIB -D_DEFAULT_SOURCE -D_GNU_SOURCE -D_POSIX_PRIORITY_SCHEDULING=1",
        )
    if "-Wno-implicit-function-declaration" not in text:
        text = text.replace(
            "CFLAGS += -U_FORTIFY_SOURCE",
            "CFLAGS += -U_FORTIFY_SOURCE -Wno-implicit-function-declaration",
        )
    if "src/reent/stat64r.c" not in text:
        text = "\n".join(
            "SRCS = $(filter-out src/unix/getpass.c src/reent/stat64r.c src/string/wcwidth.c,$(shell find src/ -name \"*.c\" -o -name \"*.S\" -o -name \"*.cpp\"))"
            if line.startswith("SRCS = ")
            else line
            for line in text.splitlines()
        ) + "\n"
    libc_makefile.write_text(text, encoding="ascii")

    (navy / "libs/libc/include/sys/mman.h").write_text(
        r'''#ifndef MEMU_SYS_MMAN_H
#define MEMU_SYS_MMAN_H

#include <stddef.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PROT_NONE 0
#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4
#define MAP_SHARED 1
#define MAP_PRIVATE 2
#define MAP_FAILED ((void *)-1)

void *mmap(void *, size_t, int, int, int, off_t);
int munmap(void *, size_t);
int memfd_create(const char *, unsigned int);

#ifdef __cplusplus
}
#endif

#endif
''',
        encoding="ascii",
    )

    sysexits = navy / "libs/libc/include/sysexits.h"
    if not sysexits.exists() and not sysexits.is_symlink():
        sysexits.symlink_to("../src/posix/sysexits.h")


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("usage: patch-pa-nanos-lite.py /path/to/nanos-lite /path/to/navy-apps [full-libc]", file=sys.stderr)
        return 2
    with_libc = len(sys.argv) == 4
    if with_libc and sys.argv[3] != "full-libc":
        print("third argument must be full-libc", file=sys.stderr)
        return 2
    vme = os.environ.get("MEMU_NANOS_VME", "0") == "1"
    patch_nanos(Path(sys.argv[1]), os.environ.get("MEMU_NANOS_APP", "/bin/hello"), vme=vme)
    patch_libos(Path(sys.argv[2]), with_libc=with_libc, vme=vme)
    if with_libc:
        patch_libc(Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
