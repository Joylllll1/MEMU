#include "memu/common.h"
#include "memu/batch.h"
#include "memu/cpu.h"
#include "memu/device.h"
#include "memu/fs.h"
#include "memu/loader.h"
#include "memu/memory.h"
#include "memu/monitor.h"
#include "memu/watchpoint.h"

#include <string.h>

typedef struct {
  const char *image_path;
  const char *elf_path;
  const char *ramdisk_path;
  const char *run_path;
  const char **batch_programs;
  int batch_program_count;
  const char *key_events_path;
  bool batch;
  bool self_test;
  bool dump_regs;
  bool trace;
  bool trace_device;
  bool trace_syscall;
  bool sdl;
  uint64_t max_instr;
} Options;

static void print_help(const char *argv0) {
  printf("Usage: %s [options]\n", argv0);
  puts("");
  puts("Options:");
  puts("  --help              Show this help");
  puts("  --version           Show MEMU version");
  puts("  --image PATH        Load raw binary image at MEMU_MEM_BASE");
  puts("  --elf PATH          Load ELF32 little-endian RISC-V executable");
  puts("  --ramdisk PATH      Load MEMU SFS ramdisk image");
  puts("  --run PATH          Load raw program from ramdisk file path");
  puts("  --batch-list A B    Run raw user programs sequentially through mini OS");
  puts("  --batch             Run without interactive monitor");
  puts("  --self-test         Run built-in Stage 1 smoke test");
  puts("  --dump-regs         Dump guest registers after execution");
  puts("  --trace             Print each executed guest instruction");
  puts("  --trace-device      Print MMIO device reads and writes");
  puts("  --trace-syscall     Print syscall number, arguments, and return value");
  puts("  --sdl               Show framebuffer in an SDL window and enable keyboard");
  puts("  --key-events PATH   Inject keyboard events; lines may include wait MS");
  puts("  --max-instr N       Stop after N guest instructions");
}

static uint64_t parse_u64(const char *s) {
  char *end = NULL;
  unsigned long long value = strtoull(s, &end, 0);
  MEMU_ASSERT(end != s && *end == '\0', "invalid integer: %s", s);
  return (uint64_t)value;
}

static Options parse_args(int argc, char **argv) {
  Options opt = {
    .image_path = NULL,
    .elf_path = NULL,
    .ramdisk_path = NULL,
    .run_path = NULL,
    .batch_programs = NULL,
    .batch_program_count = 0,
    .key_events_path = NULL,
    .batch = false,
    .self_test = false,
    .dump_regs = false,
    .trace = false,
    .trace_device = false,
    .trace_syscall = false,
    .sdl = false,
    .max_instr = 1000000,
  };

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--help") == 0) {
      print_help(argv[0]);
      exit(0);
    } else if (strcmp(argv[i], "--version") == 0) {
      puts(MEMU_VERSION);
      exit(0);
    } else if (strcmp(argv[i], "--image") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--image requires PATH");
      opt.image_path = argv[++i];
    } else if (strcmp(argv[i], "--elf") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--elf requires PATH");
      opt.elf_path = argv[++i];
    } else if (strcmp(argv[i], "--ramdisk") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--ramdisk requires PATH");
      opt.ramdisk_path = argv[++i];
    } else if (strcmp(argv[i], "--run") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--run requires PATH");
      opt.run_path = argv[++i];
    } else if (strcmp(argv[i], "--batch-list") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--batch-list requires at least one program");
      opt.batch_programs = (const char **)&argv[i + 1];
      opt.batch_program_count = argc - i - 1;
      opt.batch = true;
      break;
    } else if (strcmp(argv[i], "--batch") == 0) {
      opt.batch = true;
    } else if (strcmp(argv[i], "--self-test") == 0) {
      opt.self_test = true;
    } else if (strcmp(argv[i], "--dump-regs") == 0) {
      opt.dump_regs = true;
    } else if (strcmp(argv[i], "--trace") == 0) {
      opt.trace = true;
    } else if (strcmp(argv[i], "--trace-device") == 0) {
      opt.trace_device = true;
    } else if (strcmp(argv[i], "--trace-syscall") == 0) {
      opt.trace_syscall = true;
    } else if (strcmp(argv[i], "--sdl") == 0) {
      opt.sdl = true;
    } else if (strcmp(argv[i], "--key-events") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--key-events requires PATH");
      opt.key_events_path = argv[++i];
    } else if (strcmp(argv[i], "--max-instr") == 0) {
      MEMU_ASSERT(i + 1 < argc, "--max-instr requires N");
      opt.max_instr = parse_u64(argv[++i]);
    } else {
      MEMU_PANIC("unknown option: %s", argv[i]);
    }
  }

  return opt;
}

static void load_builtin_self_test(void) {
  const uint32_t program[] = {
    UINT32_C(0x02a00593), /* addi a1, zero, 42 */
    UINT32_C(0x00100073), /* ebreak */
  };

  for (size_t i = 0; i < MEMU_ARRAY_LEN(program); i++) {
    mem_write(MEMU_MEM_BASE + (uint32_t)(i * 4), 4, program[i]);
  }
}

static int state_to_exit_code(MEMUState state) {
  switch (state) {
    case MEMU_STATE_GOOD_TRAP:
    case MEMU_STATE_QUIT:
      return 0;
    case MEMU_STATE_BAD_TRAP:
    case MEMU_STATE_ABORT:
    case MEMU_STATE_RUNNING:
      return 1;
  }
  return 1;
}

static void print_final_state(const MEMU *memu) {
  switch (memu->state) {
    case MEMU_STATE_GOOD_TRAP:
      printf("MEMU: HIT GOOD TRAP at pc=0x%08x after %llu instructions\n",
             memu->cpu.pc, (unsigned long long)memu->instr_count);
      break;
    case MEMU_STATE_BAD_TRAP:
      printf("MEMU: HIT BAD TRAP at pc=0x%08x after %llu instructions, a0=0x%08x\n",
             memu->cpu.pc, (unsigned long long)memu->instr_count, memu->cpu.gpr[10]);
      break;
    case MEMU_STATE_ABORT:
      printf("MEMU ABORT after %llu instructions\n",
             (unsigned long long)memu->instr_count);
      break;
    case MEMU_STATE_QUIT:
      printf("MEMU: window closed, bye\n");
      return;
    case MEMU_STATE_RUNNING:
      printf("MEMU stopped while still running\n");
      break;
  }

  printf("pc  0x%08x\n", memu->cpu.pc);
  printf("a0  0x%08x\n", memu->cpu.gpr[10]);
  printf("a1  0x%08x\n", memu->cpu.gpr[11]);
}

int main(int argc, char **argv) {
  Options opt = parse_args(argc, argv);

  MEMU memu;
  memu_init(&memu);
  MEMUFS fs;
  fs_init(&fs);
  watchpoint_init();
  memu.dump_regs = opt.dump_regs;
  memu.trace = opt.trace;
  memu.trace_syscall = opt.trace_syscall;
  device_set_trace(opt.trace_device);
  device_set_sdl(opt.sdl);
  if (opt.key_events_path != NULL) {
    device_inject_key_events_from_file(opt.key_events_path);
  }

  if (opt.ramdisk_path != NULL) {
    fs_load_ramdisk(&fs, opt.ramdisk_path);
    fs_attach(&memu, &fs);
  }

  int load_modes = 0;
  load_modes += opt.image_path != NULL;
  load_modes += opt.elf_path != NULL;
  load_modes += opt.batch_program_count > 0;
  load_modes += opt.self_test;
  load_modes += opt.run_path != NULL;
  MEMU_ASSERT(load_modes == 1, "choose exactly one load mode");

  if (opt.self_test) {
    load_builtin_self_test();
  } else if (opt.run_path != NULL) {
    MEMU_ASSERT(opt.ramdisk_path != NULL, "--run requires --ramdisk");
    MEMU_ASSERT(fs_load_program(&memu, opt.run_path),
                "failed to load fs program: %s", opt.run_path);
  } else if (opt.batch_program_count > 0) {
    MEMUBatch batch_state;
    batch_init(&batch_state, opt.batch_programs, opt.batch_program_count);
    batch_attach(&memu, &batch_state);
    batch_load_current(&memu);
  } else if (opt.image_path != NULL) {
    uint32_t entry = 0;
    load_image(opt.image_path, MEMU_MEM_BASE, &entry);
    memu.cpu.pc = entry;
  } else if (opt.elf_path != NULL) {
    uint32_t entry = 0;
    load_elf(opt.elf_path, &entry);
    memu.cpu.pc = entry;
  } else {
    print_help(argv[0]);
    return 1;
  }

  if (opt.batch) {
    cpu_exec(&memu, opt.max_instr);
    if (memu.state == MEMU_STATE_RUNNING) {
      memu.limit_reached = true;
      memu.state = MEMU_STATE_ABORT;
      printf("MEMU abort: instruction limit reached: %llu\n",
             (unsigned long long)opt.max_instr);
      cpu_dump_iringbuf(&memu);
    }
  } else {
    monitor_mainloop(&memu);
  }

  if (memu.dump_regs) {
    cpu_dump_regs(&memu.cpu);
  }

  if (opt.batch || opt.self_test || memu.state != MEMU_STATE_RUNNING) {
    print_final_state(&memu);
  }

  if (opt.self_test) {
    MEMU_ASSERT(memu.state == MEMU_STATE_GOOD_TRAP, "self-test did not hit good trap");
    MEMU_ASSERT(memu.cpu.gpr[11] == 42, "self-test expected a1=42, got %u", memu.cpu.gpr[11]);
  }

  if (!opt.batch && memu.state == MEMU_STATE_RUNNING) {
    fs_free(&fs);
    return 0;
  }
  int exit_code = state_to_exit_code(memu.state);
  fs_free(&fs);
  return exit_code;
}
