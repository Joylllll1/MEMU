#!/usr/bin/env python3
import sys
from pathlib import Path


def patch_audio(am_home: Path) -> None:
    audio = am_home / "am/src/platform/nemu/ioe/audio.c"
    audio.write_text(
        r'''#include "riscv/riscv.h"
#include <am.h>
#include <nemu.h>

#define AUDIO_FREQ_ADDR      (AUDIO_ADDR + 0x00)
#define AUDIO_CHANNELS_ADDR  (AUDIO_ADDR + 0x04)
#define AUDIO_SAMPLES_ADDR   (AUDIO_ADDR + 0x08)
#define AUDIO_SBUF_SIZE_ADDR (AUDIO_ADDR + 0x0c)
#define AUDIO_INIT_ADDR      (AUDIO_ADDR + 0x10)
#define AUDIO_COUNT_ADDR     (AUDIO_ADDR + 0x14)

void __am_audio_init() {
}

void __am_audio_config(AM_AUDIO_CONFIG_T *cfg) {
  cfg->present = true;
  cfg->bufsize = inl(AUDIO_SBUF_SIZE_ADDR);
}

void __am_audio_ctrl(AM_AUDIO_CTRL_T *ctrl) {
  outl(AUDIO_FREQ_ADDR, ctrl->freq);
  outl(AUDIO_CHANNELS_ADDR, ctrl->channels);
  outl(AUDIO_SAMPLES_ADDR, ctrl->samples);
  outl(AUDIO_INIT_ADDR, 1);
}

void __am_audio_status(AM_AUDIO_STATUS_T *stat) {
  stat->count = inl(AUDIO_COUNT_ADDR);
}

void __am_audio_play(AM_AUDIO_PLAY_T *ctl) {
  uint8_t *src = ctl->buf.start;
  int len = (uint8_t *)ctl->buf.end - src;
  int bufsize = inl(AUDIO_SBUF_SIZE_ADDR);
  while (len > 0) {
    int count = inl(AUDIO_COUNT_ADDR);
    int space = bufsize - count;
    if (space <= 0) {
      continue;
    }
    int n = len < space ? len : space;
    for (int i = 0; i < n; i++) {
      outb(AUDIO_SBUF_ADDR + count + i, src[i]);
    }
    outl(AUDIO_COUNT_ADDR, count + n);
    src += n;
    len -= n;
  }
}
''',
        encoding="ascii",
    )


def patch_devscan(am_home: Path) -> None:
    ioe = am_home / "am/src/platform/nemu/ioe/ioe.c"
    gpu = am_home / "am/src/platform/nemu/ioe/gpu.c"
    disk = am_home / "am/src/platform/nemu/ioe/disk.c"

    text = ioe.read_text(encoding="ascii")
    if "__am_gpu_memcpy" not in text:
        text = text.replace(
            "void __am_gpu_fbdraw(AM_GPU_FBDRAW_T *);\n",
            "void __am_gpu_fbdraw(AM_GPU_FBDRAW_T *);\n"
            "void __am_gpu_memcpy(AM_GPU_MEMCPY_T *);\n"
            "void __am_gpu_render(AM_GPU_RENDER_T *);\n",
        )
        text = text.replace(
            "  [AM_GPU_STATUS  ] = __am_gpu_status,\n",
            "  [AM_GPU_STATUS  ] = __am_gpu_status,\n"
            "  [AM_GPU_MEMCPY  ] = __am_gpu_memcpy,\n"
            "  [AM_GPU_RENDER  ] = __am_gpu_render,\n",
        )
        ioe.write_text(text, encoding="ascii")

    text = gpu.read_text(encoding="ascii")
    if "__am_gpu_memcpy" not in text:
        text += r'''

void __am_gpu_memcpy(AM_GPU_MEMCPY_T *ctl) {
  (void)ctl;
}

void __am_gpu_render(AM_GPU_RENDER_T *ctl) {
  (void)ctl;
  outl(SYNC_ADDR, 1);
}
'''
        gpu.write_text(text, encoding="ascii")

    disk.write_text(
        r'''#include <am.h>
#include <klib.h>

#define BLKSZ 512
#define BLKCNT 128

static uint8_t disk[BLKSZ * BLKCNT];

void __am_disk_config(AM_DISK_CONFIG_T *cfg) {
  cfg->present = true;
  cfg->blksz = BLKSZ;
  cfg->blkcnt = BLKCNT;
}

void __am_disk_status(AM_DISK_STATUS_T *stat) {
  stat->ready = true;
}

void __am_disk_blkio(AM_DISK_BLKIO_T *io) {
  uint32_t off = io->blkno * BLKSZ;
  uint32_t len = io->blkcnt * BLKSZ;
  if (off + len > sizeof(disk)) {
    return;
  }
  if (io->write) {
    memcpy(disk + off, io->buf, len);
  } else {
    memcpy(io->buf, disk + off, len);
  }
}
''',
        encoding="ascii",
    )


def patch_cte(am_home: Path) -> None:
    arch = am_home / "am/include/arch/riscv.h"
    cte = am_home / "am/src/riscv/nemu/cte.c"
    trap = am_home / "am/src/riscv/nemu/trap.S"
    mpe = am_home / "am/src/platform/nemu/mpe.c"

    arch.write_text(
        r'''#ifndef ARCH_H__
#define ARCH_H__

#ifdef __riscv_e
#define NR_REGS 16
#else
#define NR_REGS 32
#endif

struct Context {
  uintptr_t gpr[NR_REGS], mcause, mstatus, mepc;
  void *pdir;
};

#ifdef __riscv_e
#define GPR1 gpr[15] // a5
#else
#define GPR1 gpr[17] // a7
#endif

#define GPR2 gpr[10] // a0
#define GPR3 gpr[11] // a1
#define GPR4 gpr[12] // a2
#define GPRx gpr[10] // a0

#endif
''',
        encoding="ascii",
    )

    cte.write_text(
        r'''#include <am.h>
#include <riscv/riscv.h>
#include <klib.h>

static Context* (*user_handler)(Event, Context*) = NULL;

void __am_get_cur_as(Context *c);

Context* __am_irq_handle(Context *c) {
  __am_get_cur_as(c);

  if (user_handler) {
    Event ev = {0};
    switch (c->mcause) {
      case 0x80000007u:
        ev.event = EVENT_IRQ_TIMER;
        break;
      case 11:
        ev.event = (c->GPR1 == (uintptr_t)-1) ? EVENT_YIELD : EVENT_SYSCALL;
        c->mepc += 4;
        break;
      default:
        ev.event = EVENT_ERROR;
        break;
    }

    c = user_handler(ev, c);
    assert(c != NULL);
  }

  return c;
}

extern void __am_asm_trap(void);

bool cte_init(Context*(*handler)(Event, Context*)) {
  asm volatile("csrw mtvec, %0" : : "r"(__am_asm_trap));
  user_handler = handler;
  return true;
}

Context *kcontext(Area kstack, void (*entry)(void *), void *arg) {
  uintptr_t end = (uintptr_t)kstack.end & ~(uintptr_t)0xf;
  Context *c = (Context *)(end - sizeof(Context));
  assert((uintptr_t)c >= (uintptr_t)kstack.start);
  memset(c, 0, sizeof(*c));
  c->mepc = (uintptr_t)entry;
  c->mstatus = 0x1808;
  c->gpr[10] = (uintptr_t)arg;
  return c;
}

void yield() {
#ifdef __riscv_e
  asm volatile("li a5, -1; ecall");
#else
  asm volatile("li a7, -1; ecall");
#endif
}

bool ienabled() {
  uintptr_t mstatus = 0;
  asm volatile("csrr %0, mstatus" : "=r"(mstatus));
  return (mstatus & 0x8) != 0;
}

void iset(bool enable) {
  if (enable) {
    asm volatile("csrsi mstatus, 0x8" ::: "memory");
  } else {
    asm volatile("csrci mstatus, 0x8" ::: "memory");
  }
}
''',
        encoding="ascii",
    )

    trap.write_text(
        r'''#define concat_temp(x, y) x ## y
#define concat(x, y) concat_temp(x, y)
#define MAP(c, f) c(f)

#if __riscv_xlen == 32
#define LOAD  lw
#define STORE sw
#define XLEN  4
#else
#define LOAD  ld
#define STORE sd
#define XLEN  8
#endif

#define REGS_LO16(f) \
      f( 1)       f( 3) f( 4) f( 5) f( 6) f( 7) f( 8) f( 9) \
f(10) f(11) f(12) f(13) f(14) f(15)
#define REGS_LO16_NO_T0(f) \
      f( 1)       f( 3) f( 4)       f( 6) f( 7) f( 8) f( 9) \
f(10) f(11) f(12) f(13) f(14) f(15)
#ifndef __riscv_e
#define REGS_HI16(f) \
                                    f(16) f(17) f(18) f(19) \
f(20) f(21) f(22) f(23) f(24) f(25) f(26) f(27) f(28) f(29) \
f(30) f(31)
#define NR_REGS 32
#else
#define REGS_HI16(f)
#define NR_REGS 16
#endif

#define REGS(f) REGS_LO16(f) REGS_HI16(f)
#define REGS_NO_T0(f) REGS_LO16_NO_T0(f) REGS_HI16(f)

#define PUSH(n) STORE concat(x, n), (n * XLEN)(sp);
#define POP_FROM(n) LOAD concat(x, n), (n * XLEN)(t0);
#define CONTEXT_SIZE  ((NR_REGS + 4) * XLEN)
#define OFFSET_SP     ( 2 * XLEN)
#define OFFSET_CAUSE  ((NR_REGS + 0) * XLEN)
#define OFFSET_STATUS ((NR_REGS + 1) * XLEN)
#define OFFSET_EPC    ((NR_REGS + 2) * XLEN)
#define OFFSET_PDIR   ((NR_REGS + 3) * XLEN)
#define SATP_MODE     (1 << (__riscv_xlen - 1))

.align 3
.globl __am_asm_trap
__am_asm_trap:
  addi sp, sp, -CONTEXT_SIZE
  MAP(REGS, PUSH)

  # x2 is not pushed because sp now points at the frame. Save the interrupted
  # user stack pointer in the Context so a process switch can restore it.
  addi t0, sp, CONTEXT_SIZE
  STORE t0, OFFSET_SP(sp)

  csrr t0, mcause
  csrr t1, mstatus
  csrr t2, mepc
  STORE t0, OFFSET_CAUSE(sp)
  STORE t1, OFFSET_STATUS(sp)
  STORE t2, OFFSET_EPC(sp)

  li a0, (1 << 17)
  or t1, t1, a0
  csrw mstatus, t1

  mv a0, sp
  call __am_irq_handle
  mv t0, a0

  # Switch address spaces only after the C handler has returned. The handler
  # runs on the interrupted user stack, which is not safe to use after a
  # different process page table is installed.
  LOAD t1, OFFSET_PDIR(t0)
  beqz t1, 1f
  srli t1, t1, 12
  li t2, SATP_MODE
  or t1, t1, t2
  csrw satp, t1
  sfence.vma
1:

  LOAD t1, OFFSET_STATUS(t0)
  LOAD t2, OFFSET_EPC(t0)
  csrw mstatus, t1
  csrw mepc, t2

  MAP(REGS_NO_T0, POP_FROM)
  LOAD sp, OFFSET_SP(t0)
  LOAD t0, (5 * XLEN)(t0)
  mret
''',
        encoding="ascii",
    )

    mpe.write_text(
        r'''#include <am.h>
#include <klib-macros.h>

bool mpe_init(void (*entry)()) {
  entry();
  panic("MPE entry returns");
}

int cpu_count() {
  return 1;
}

int cpu_current() {
  return 0;
}

int atomic_xchg(int *addr, int newval) {
  int old = *addr;
  *addr = newval;
  return old;
}
''',
        encoding="ascii",
    )


def patch_klib(am_home: Path) -> None:
    stdio = am_home / "klib/src/stdio.c"
    text = stdio.read_text(encoding="ascii")

    old_snprintf = '''int snprintf(char *out, size_t n, const char *fmt, ...) {
  panic("Not implemented");
}

int vsnprintf(char *out, size_t n, const char *fmt, va_list ap) {
  panic("Not implemented");
}'''

    new_snprintf = r'''static int vsnprintf_impl(char *out, size_t n, const char *fmt, va_list ap) {
  const char *p = fmt;
  char *res = out;
  char *end = out + n;
  bool flag = false;
  while (*p != '\0') {
    if (flag) {
      int width = 0;
      if (*p == '0') {
        p++;
        while (*p >= '0' && *p <= '9') {
          width = width * 10 + (*p - '0');
          p++;
        }
      }
      switch (*p) {
        case 'd': {
          int d = va_arg(ap, int);
          int isneg = 0;
          if (d < 0) {
            isneg = 1;
            if (d == -2147483648) {
              if (out < end) { *out = '-'; out++; }
              int digit = 11;
              int pad = width - digit;
              while (pad > 0 && out < end) { *out = '0'; out++; pad--; }
              const char *s = "2147483648";
              while (*s && out < end) { *out = *s; out++; s++; }
              break;
            }
            d = -d;
          }
          int v = d, digit = (v == 0) ? 1 : 0;
          while (v > 0) { v /= 10; digit++; }
          int pad = width - digit - isneg;
          if (isneg && out < end) { *out = '-'; out++; }
          while (pad > 0 && out < end) { *out = '0'; out++; pad--; }
          char tmp[12]; int ti = 0;
          do { tmp[ti++] = '0' + (d % 10); d /= 10; } while (d > 0);
          while (ti > 0 && out < end) { out++; ti--; *((out - 1)) = tmp[ti]; }
          break;
        }
        case 's': {
          char *s = va_arg(ap, char *);
          if (s == NULL) s = (char *)"(null)";
          while (*s != '\0' && out < end) { *out = *s; out++; s++; }
          break;
        }
        case 'c': {
          int c = va_arg(ap, int);
          if (out < end) { *out = (char)c; out++; }
          break;
        }
        case 'x':
        case 'p': {
          unsigned u = va_arg(ap, unsigned);
          char hex[16]; int hi = 0;
          do { int v = u & 0xf; hex[hi++] = (char)(v < 10 ? '0' + v : 'a' + v - 10); u >>= 4; } while (u > 0);
          int pad = width - hi;
          while (pad > 0 && out < end) { *out = '0'; out++; pad--; }
          while (hi > 0 && out < end) { hi--; *out = hex[hi]; out++; }
          break;
        }
        case 'l':
          if (*(p + 1) == 'd' || *(p + 1) == 'u' || *(p + 1) == 'x') {
            p++;
            goto default_case;
          }
          goto default_case;
        default: default_case:
          if (out < end) { *out = *p; out++; }
          break;
      }
      flag = false;
      p++;
      continue;
    }
    if (*p == '%') { flag = true; p++; continue; }
    if (out < end) { *out = *p; out++; }
    p++;
  }
  if (out < end) *out = '\0';
  else if (n > 0) *(end - 1) = '\0';
  return (int)(out - res);
}

int snprintf(char *out, size_t n, const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  int ret = vsnprintf_impl(out, n, fmt, ap);
  va_end(ap);
  return ret;
}

int vsnprintf(char *out, size_t n, const char *fmt, va_list ap) {
  return vsnprintf_impl(out, n, fmt, ap);
}'''

    if old_snprintf not in text:
        raise SystemExit("missing snprintf/vsnprintf stubs in AM klib stdio.c")
    text = text.replace(old_snprintf, new_snprintf)
    stdio.write_text(text, encoding="ascii")


def patch_vme(am_home: Path) -> None:
    vme = am_home / "am/src/riscv/nemu/vme.c"
    vme.write_text(
        r'''#include <am.h>
#include <nemu.h>
#include <klib.h>

static AddrSpace kas = {};
static void* (*pgalloc_usr)(int) = NULL;
static void (*pgfree_usr)(void*) = NULL;
static int vme_enable = 0;

static Area segments[] = {      // Kernel memory mappings
  NEMU_PADDR_SPACE
};

#define USER_SPACE RANGE(0x40000000, 0x80000000)

#define PTE_V 0x01
#define PTE_R 0x02
#define PTE_W 0x04
#define PTE_X 0x08

static inline void set_satp(void *pdir) {
  uintptr_t mode = 1ul << (__riscv_xlen - 1);
  asm volatile("csrw satp, %0" : : "r"(mode | ((uintptr_t)pdir >> 12)));
}

static inline uintptr_t get_satp() {
  uintptr_t satp;
  asm volatile("csrr %0, satp" : "=r"(satp));
  return satp << 12;
}

bool vme_init(void* (*pgalloc_f)(int), void (*pgfree_f)(void*)) {
  pgalloc_usr = pgalloc_f;
  pgfree_usr = pgfree_f;

  kas.ptr = pgalloc_f(PGSIZE);

  int i;
  for (i = 0; i < LENGTH(segments); i ++) {
    void *va = segments[i].start;
    for (; va < segments[i].end; va += PGSIZE) {
      map(&kas, va, va, 0);
    }
  }

  set_satp(kas.ptr);
  vme_enable = 1;

  return true;
}

void protect(AddrSpace *as) {
  PTE *updir = (PTE*)(pgalloc_usr(PGSIZE));
  as->ptr = updir;
  as->area = USER_SPACE;
  as->pgsize = PGSIZE;
  // map kernel space
  memcpy(updir, kas.ptr, PGSIZE);
}

void unprotect(AddrSpace *as) {
}

void __am_get_cur_as(Context *c) {
  c->pdir = (vme_enable ? (void *)get_satp() : NULL);
}

void __am_switch(Context *c) {
  if (vme_enable && c->pdir != NULL) {
    set_satp(c->pdir);
  }
}

void map(AddrSpace *as, void *va, void *pa, int prot) {
  uintptr_t vaddr = (uintptr_t)va & ~(uintptr_t)(PGSIZE - 1);
  uintptr_t paddr = (uintptr_t)pa & ~(uintptr_t)(PGSIZE - 1);
  PTE *root = (PTE *)as->ptr;
  uintptr_t vpn1 = (vaddr >> 22) & 0x3ff;
  uintptr_t vpn0 = (vaddr >> 12) & 0x3ff;
  if ((root[vpn1] & PTE_V) == 0) {
    PTE *table = (PTE *)pgalloc_usr(PGSIZE);
    memset(table, 0, PGSIZE);
    root[vpn1] = ((((uintptr_t)table) >> 12) << 10) | PTE_V;
  }
  PTE *table = (PTE *)((root[vpn1] >> 10) << 12);
  uintptr_t flags;
  if (prot == 0) {
    flags = PTE_R | PTE_W | PTE_X;  // kernel identity mapping from vme_init
  } else {
    flags = PTE_R | PTE_X;
    if (prot & MMAP_WRITE) flags |= PTE_W;
  }
  table[vpn0] = ((paddr >> 12) << 10) | flags | PTE_V;
}

Context *ucontext(AddrSpace *as, Area kstack, void *entry) {
  uintptr_t end = (uintptr_t)kstack.end & ~(uintptr_t)0xf;
  Context *c = (Context *)(end - sizeof(Context));
  memset(c, 0, sizeof(*c));
  c->mepc = (uintptr_t)entry;
  c->mstatus = 0x1808;
  c->pdir = as->ptr;
  return c;
}
''',
        encoding="ascii",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch-pa-nemu-ioe.py /path/to/abstract-machine", file=sys.stderr)
        return 2
    am_home = Path(sys.argv[1])
    patch_audio(am_home)
    patch_devscan(am_home)
    patch_cte(am_home)
    patch_vme(am_home)
    patch_klib(am_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
