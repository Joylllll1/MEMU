#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def patch_common(nanos: Path) -> None:
    common = nanos / "include/common.h"
    text = common.read_text(encoding="ascii")
    text = text.replace("//#define HAS_CTE", "#define HAS_CTE")
    common.write_text(text, encoding="ascii")


def patch_nanos(nanos: Path, app_path: str = "/bin/hello") -> None:
    patch_common(nanos)

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

#define MAX_NR_PROC 4

static PCB pcb[MAX_NR_PROC] __attribute__((used)) = {};
static PCB pcb_boot = {};
PCB *current = NULL;

void switch_boot_pcb() {
  current = &pcb_boot;
}

void naive_uload(PCB *pcb, const char *filename);

void init_proc() {
  switch_boot_pcb();
  Log("Initializing processes...");
  naive_uload(&pcb[0], "/bin/hello");
}

Context* schedule(Context *prev) {
  return prev;
}
'''.replace("/bin/hello", app_path),
        encoding="ascii",
    )

    (nanos / "src/irq.c").write_text(
        r'''#include <common.h>

void do_syscall(Context *c);

static Context* do_event(Event e, Context* c) {
  switch (e.event) {
    case EVENT_YIELD:
      break;
    case EVENT_SYSCALL:
      do_syscall(c);
      break;
    case EVENT_IRQ_TIMER:
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

static void *pf = NULL;

void* new_page(size_t nr_page) {
  void *p = pf;
  pf += nr_page * PGSIZE;
  return p;
}

#ifdef HAS_VME
static void* pg_alloc(int n) {
  return new_page(n);
}
#endif

void free_page(void *p) {
  panic("not implement yet");
}

int mm_brk(uintptr_t brk) {
  (void)brk;
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
  io_write(AM_GPU_FBDRAW, 0, 0, NULL, 0, 0, true);
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

enum {FD_STDIN, FD_STDOUT, FD_STDERR, FD_FB, FD_EVENTS, FD_DISPINFO};

size_t ramdisk_read(void *buf, size_t offset, size_t len);
size_t ramdisk_write(const void *buf, size_t offset, size_t len);
size_t get_ramdisk_size();
size_t serial_write(const void *buf, size_t offset, size_t len);
size_t events_read(void *buf, size_t offset, size_t len);
size_t dispinfo_read(void *buf, size_t offset, size_t len);
size_t fb_write(const void *buf, size_t offset, size_t len);

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

    (nanos / "src/loader.c").write_text(
        r'''#include <proc.h>
#include <elf.h>
#include <fs.h>

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

static uintptr_t loader(PCB *pcb, const char *filename) {
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
  return eh.e_entry;
}

void naive_uload(PCB *pcb, const char *filename) {
  uintptr_t entry = loader(pcb, filename);
  Log("Jump to entry = %p", entry);
  ((void(*)())entry) ();
}
''',
        encoding="ascii",
    )

    (nanos / "src/syscall.c").write_text(
        r'''#include <common.h>
#include <proc.h>
#include "syscall.h"

int fs_open(const char *pathname, int flags, int mode);
size_t fs_read(int fd, void *buf, size_t len);
size_t fs_write(int fd, const void *buf, size_t len);
size_t fs_lseek(int fd, size_t offset, int whence);
int fs_close(int fd);
int mm_brk(uintptr_t brk);
void naive_uload(PCB *pcb, const char *filename);

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

void do_syscall(Context *c) {
  uintptr_t a[4];
  a[0] = c->GPR1;
  a[1] = c->GPR2;
  a[2] = c->GPR3;
  a[3] = c->GPR4;

  switch (a[0]) {
    case SYS_exit:
      exit_current(a[1]);
      break;
    case SYS_yield:
      yield();
      c->GPRx = 0;
      break;
    case SYS_open:
      c->GPRx = fs_open((const char *)a[1], a[2], a[3]);
      break;
    case SYS_read:
      c->GPRx = fs_read(a[1], (void *)a[2], a[3]);
      break;
    case SYS_write:
      c->GPRx = fs_write(a[1], (const void *)a[2], a[3]);
      break;
    case SYS_close:
      c->GPRx = fs_close(a[1]);
      break;
    case SYS_lseek:
      c->GPRx = fs_lseek(a[1], a[2], a[3]);
      break;
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
    default:
      panic("Unhandled syscall ID = %d", a[0]);
  }
}
''',
        encoding="ascii",
    )


def patch_libos(navy: Path, with_libc: bool = False) -> None:
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

char **environ;

void call_main(uintptr_t *args) {
  (void)args;
  char *empty[] = { 0 };
  environ = empty;
  _exit(main(0, empty, empty));
  while (1) {
  }
}
''',
        encoding="ascii",
    )

    (navy / "libs/libos/src/syscall.c").write_text(
        r'''#include <stdint.h>
#include <stddef.h>
#include "syscall.h"

typedef long ssize_t;
typedef long off_t;
typedef int mode_t;
typedef int pid_t;
typedef long clock_t;

struct timeval {
  long tv_sec;
  long tv_usec;
};

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

int _execve(const char *fname, char * const argv[], char *const envp[]) {
  (void)fname; (void)argv; (void)envp;
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
  return -1;
}

pid_t vfork() {
  return -1;
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
  (void)status;
  return -1;
}

clock_t _times(void *buf) {
  (void)buf;
  return 0;
}

int pipe(int pipefd[2]) {
  (void)pipefd;
  return -1;
}

int dup(int oldfd) {
  (void)oldfd;
  return -1;
}

int dup2(int oldfd, int newfd) {
  (void)oldfd; (void)newfd;
  return -1;
}

unsigned int sleep(unsigned int seconds) {
  (void)seconds;
  return 0;
}
''',
        encoding="ascii",
    )


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
    patch_nanos(Path(sys.argv[1]), os.environ.get("MEMU_NANOS_APP", "/bin/hello"))
    patch_libos(Path(sys.argv[2]), with_libc=with_libc)
    if with_libc:
        patch_libc(Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
