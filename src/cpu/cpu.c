#include "memu/cpu.h"

#include "memu/device.h"
#include "memu/memory.h"
#include "memu/mmu.h"
#include "memu/watchpoint.h"

#include <string.h>

#define MSTATUS_MIE UINT32_C(0x00000008)
#define MSTATUS_MIE_NEMU UINT32_C(0x00020000)
#define MCAUSE_MACHINE_TIMER_INTERRUPT UINT32_C(0x80000007)
#define TIMER_INTERRUPT_INTERVAL UINT64_C(200000)

static const char *const reg_names[32] = {
  "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
  "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
  "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
  "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
};

void memu_init(MEMU *memu) {
  memory_init();
  device_init();
  *memu = (MEMU){
    .cpu = {
      .pc = MEMU_MEM_BASE,
    },
    .state = MEMU_STATE_RUNNING,
    .instr_count = 0,
    .limit_reached = false,
    .dump_regs = false,
    .trace = false,
    .trace_syscall = false,
    .program_break = MEMU_MEM_BASE + UINT32_C(0x02000000),
    .heap_base = MEMU_MEM_BASE + UINT32_C(0x02000000),
    .heap_limit = MEMU_MEM_BASE + MEMU_MEM_SIZE,
    .batch = NULL,
    .fs = NULL,
    .iringbuf_pos = 0,
    .iringbuf_count = 0,
  };
  mmu_set_cpu(&memu->cpu);
}

static bool maybe_timer_interrupt(MEMU *memu) {
  CPUState *cpu = &memu->cpu;
  if (cpu->mtvec == 0 ||
      ((cpu->mstatus & (MSTATUS_MIE | MSTATUS_MIE_NEMU)) == 0)) {
    return false;
  }
  if (cpu->trap_depth > 0) {
    return false;
  }
  if (memu->instr_count == 0 ||
      (memu->instr_count % TIMER_INTERRUPT_INTERVAL) != 0) {
    return false;
  }
  cpu->mepc = cpu->pc;
  cpu->mcause = MCAUSE_MACHINE_TIMER_INTERRUPT;
  cpu->pc = cpu->mtvec;
  cpu->trap_depth++;
  return true;
}

void cpu_exec(MEMU *memu, uint64_t max_instr) {
  mmu_set_cpu(&memu->cpu);
  uint64_t executed = 0;
  while (memu->state == MEMU_STATE_RUNNING && executed < max_instr) {
    if (!maybe_timer_interrupt(memu)) {
      rv32i_exec_once(memu);
    }
    memu->cpu.gpr[0] = 0;
    memu->instr_count++;
    executed++;
    if ((executed & UINT64_C(0x3fff)) == 0 && !device_poll()) {
      memu->state = MEMU_STATE_QUIT;
      break;
    }
#ifndef MEMU_FAST_RUN
    if (watchpoint_check(memu)) {
      break;
    }
#endif
  }

}

const char *cpu_reg_name(int idx) {
  MEMU_ASSERT(idx >= 0 && idx < 32, "invalid register index: %d", idx);
  return reg_names[idx];
}

void cpu_record_inst(MEMU *memu, uint32_t pc, uint32_t inst) {
#ifdef MEMU_FAST_RUN
  if (!memu->trace) {
    return;
  }
#endif
  memu->iringbuf[memu->iringbuf_pos] = (InstrTrace){
    .pc = pc,
    .inst = inst,
  };
  memu->iringbuf_pos = (memu->iringbuf_pos + 1) % MEMU_IRINGBUF_SIZE;
  if (memu->iringbuf_count < MEMU_IRINGBUF_SIZE) {
    memu->iringbuf_count++;
  }

  if (memu->trace) {
    printf("0x%08x: 0x%08x\n", pc, inst);
  }
}

void cpu_dump_iringbuf(const MEMU *memu) {
  if (memu->iringbuf_count == 0) {
    return;
  }

  puts("Recent guest instructions:");
  size_t start = (memu->iringbuf_pos + MEMU_IRINGBUF_SIZE - memu->iringbuf_count) %
                 MEMU_IRINGBUF_SIZE;
  for (size_t i = 0; i < memu->iringbuf_count; i++) {
    size_t idx = (start + i) % MEMU_IRINGBUF_SIZE;
    printf("  0x%08x: 0x%08x\n", memu->iringbuf[idx].pc, memu->iringbuf[idx].inst);
  }
}

uint32_t cpu_reg_str2val(const CPUState *cpu, const char *name, bool *success) {
  if (strcmp(name, "pc") == 0) {
    *success = true;
    return cpu->pc;
  }

  if (name[0] == 'x' && name[1] != '\0') {
    char *end = NULL;
    unsigned long idx = strtoul(name + 1, &end, 10);
    if (*end == '\0' && idx < 32) {
      *success = true;
      return cpu->gpr[idx];
    }
  }

  for (int i = 0; i < 32; i++) {
    if (strcmp(name, reg_names[i]) == 0) {
      *success = true;
      return cpu->gpr[i];
    }
  }

  *success = false;
  return 0;
}

void cpu_dump_regs(const CPUState *cpu) {
  printf("pc   0x%08x\n", cpu->pc);
  for (int i = 0; i < 32; i++) {
    printf("%-4s 0x%08x\n", reg_names[i], cpu->gpr[i]);
  }
}
