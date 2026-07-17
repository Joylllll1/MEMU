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

Context* __am_irq_handle(Context *c) {
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

    text = trap.read_text(encoding="ascii")
    if "call __am_irq_handle\n\n  LOAD" in text:
        text = text.replace("call __am_irq_handle\n\n  LOAD",
                            "call __am_irq_handle\n\n  mv sp, a0\n\n  LOAD")
        trap.write_text(text, encoding="ascii")

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


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch-pa-nemu-ioe.py /path/to/abstract-machine", file=sys.stderr)
        return 2
    am_home = Path(sys.argv[1])
    patch_audio(am_home)
    patch_devscan(am_home)
    patch_cte(am_home)
    patch_klib(am_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
