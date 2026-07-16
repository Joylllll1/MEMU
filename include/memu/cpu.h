#ifndef MEMU_CPU_H
#define MEMU_CPU_H

#include "memu/common.h"

typedef enum {
  MEMU_STATE_RUNNING,
  MEMU_STATE_GOOD_TRAP,
  MEMU_STATE_BAD_TRAP,
  MEMU_STATE_ABORT,
} MEMUState;

typedef struct {
  uint32_t gpr[32];
  uint32_t pc;
  uint32_t mstatus;
  uint32_t mtvec;
  uint32_t mscratch;
  uint32_t mepc;
  uint32_t mcause;
} CPUState;

typedef struct {
  uint32_t pc;
  uint32_t inst;
} InstrTrace;

#define MEMU_IRINGBUF_SIZE 32

typedef struct MEMUBatch MEMUBatch;
typedef struct MEMUFS MEMUFS;

typedef struct {
  CPUState cpu;
  MEMUState state;
  uint64_t instr_count;
  bool limit_reached;
  bool dump_regs;
  bool trace;
  bool trace_syscall;
  uint32_t program_break;
  uint32_t heap_base;
  uint32_t heap_limit;
  MEMUBatch *batch;
  MEMUFS *fs;
  InstrTrace iringbuf[MEMU_IRINGBUF_SIZE];
  size_t iringbuf_pos;
  size_t iringbuf_count;
} MEMU;

void memu_init(MEMU *memu);
void cpu_exec(MEMU *memu, uint64_t max_instr);
void cpu_dump_regs(const CPUState *cpu);
void cpu_record_inst(MEMU *memu, uint32_t pc, uint32_t inst);
void cpu_dump_iringbuf(const MEMU *memu);
const char *cpu_reg_name(int idx);
uint32_t cpu_reg_str2val(const CPUState *cpu, const char *name, bool *success);

void rv32i_exec_once(MEMU *memu);

static inline uint32_t cpu_reg(const CPUState *cpu, int idx) {
  return cpu->gpr[idx];
}

static inline void cpu_set_reg(CPUState *cpu, int idx, uint32_t value) {
  if (idx != 0) {
    cpu->gpr[idx] = value;
  }
}

#endif
