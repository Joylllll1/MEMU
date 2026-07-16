#include "memu/syscall.h"

#include "memu/batch.h"
#include "memu/fs.h"
#include "memu/memory.h"

static const char *syscall_name(uint32_t no) {
  switch (no) {
    case MEMU_SYS_WRITE:
      return "write";
    case MEMU_SYS_OPENAT:
      return "openat";
    case MEMU_SYS_CLOSE:
      return "close";
    case MEMU_SYS_LSEEK:
      return "lseek";
    case MEMU_SYS_READ:
      return "read";
    case MEMU_SYS_EXIT:
      return "exit";
    case MEMU_SYS_BRK:
      return "brk";
    case MEMU_SYS_OPEN:
      return "open";
    default:
      return "unknown";
  }
}

static void trace_syscall(const MEMU *memu, uint32_t pc, uint32_t no,
                          uint32_t a0, uint32_t a1, uint32_t a2,
                          uint32_t result) {
  if (memu->trace_syscall) {
    printf("[syscall] pc=0x%08x no=%s(%u) a0=0x%08x a1=0x%08x "
           "a2=0x%08x -> 0x%08x\n",
           pc, syscall_name(no), no, a0, a1, a2, result);
  }
}

void syscall_reset_program(MEMU *memu) {
  memu->heap_base = MEMU_MEM_BASE + UINT32_C(0x02000000);
  memu->heap_limit = MEMU_MEM_BASE + MEMU_MEM_SIZE;
  memu->program_break = memu->heap_base;
}

static uint32_t sys_write(uint32_t fd, uint32_t buf, uint32_t len) {
  FILE *out = NULL;
  if (fd == 1) {
    out = stdout;
  } else if (fd == 2) {
    out = stderr;
  } else {
    return UINT32_MAX;
  }

  for (uint32_t i = 0; i < len; i++) {
    fputc((int)mem_read(buf + i, 1), out);
  }
  fflush(out);
  return len;
}

static bool guest_read_cstr(uint32_t addr, char *buf, size_t buflen) {
  MEMU_ASSERT(buflen > 0, "guest_read_cstr needs a non-empty buffer");
  for (size_t i = 0; i < buflen - 1; i++) {
    uint8_t ch = (uint8_t)mem_read(addr + (uint32_t)i, 1);
    buf[i] = (char)ch;
    if (ch == 0) {
      return true;
    }
  }
  buf[buflen - 1] = '\0';
  return false;
}

static uint32_t sys_open_path(MEMU *memu, uint32_t path_addr) {
  if (memu->fs == NULL) {
    return UINT32_MAX;
  }

  char path[MEMU_FS_NAME_MAX];
  if (!guest_read_cstr(path_addr, path, sizeof(path))) {
    return UINT32_MAX;
  }
  return fs_open(memu->fs, path);
}

static uint32_t sys_brk(MEMU *memu, uint32_t requested) {
  if (requested == 0) {
    return memu->program_break;
  }

  if (requested < memu->heap_base || requested > memu->heap_limit) {
    return UINT32_MAX;
  }

  memu->program_break = requested;
  return 0;
}

void syscall_handle_ecall(MEMU *memu, uint32_t pc, uint32_t snpc) {
  CPUState *cpu = &memu->cpu;
  uint32_t no = cpu_reg(cpu, 17);
  uint32_t a0 = cpu_reg(cpu, 10);
  uint32_t a1 = cpu_reg(cpu, 11);
  uint32_t a2 = cpu_reg(cpu, 12);
  uint32_t result = 0;

  switch (no) {
    case MEMU_SYS_OPEN:
      result = sys_open_path(memu, a0);
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_OPENAT:
      result = sys_open_path(memu, a1);
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_READ:
      result = (memu->fs != NULL) ? fs_read(memu->fs, a0, a1, a2) : UINT32_MAX;
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_WRITE:
      if (a0 == 1 || a0 == 2) {
        result = sys_write(a0, a1, a2);
      } else {
        result = (memu->fs != NULL) ? fs_write(memu->fs, a0, a1, a2) : UINT32_MAX;
      }
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_LSEEK:
      result = (memu->fs != NULL) ? fs_lseek(memu->fs, a0, (int32_t)a1, a2) : UINT32_MAX;
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_CLOSE:
      result = (memu->fs != NULL) ? fs_close(memu->fs, a0) : UINT32_MAX;
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    case MEMU_SYS_EXIT:
      result = 0;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      if (memu->batch != NULL) {
        batch_handle_exit(memu, (int)a0);
      } else {
        memu->state = (a0 == 0) ? MEMU_STATE_GOOD_TRAP : MEMU_STATE_BAD_TRAP;
        cpu->pc = pc;
      }
      break;

    case MEMU_SYS_BRK:
      result = sys_brk(memu, a0);
      cpu_set_reg(cpu, 10, result);
      cpu->pc = snpc;
      trace_syscall(memu, pc, no, a0, a1, a2, result);
      break;

    default:
      fprintf(stderr, "unknown syscall: %u at pc=0x%08x\n", no, pc);
      cpu_dump_iringbuf(memu);
      memu->state = MEMU_STATE_ABORT;
      cpu->pc = pc;
      break;
  }
}
