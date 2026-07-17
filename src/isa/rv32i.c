#include "memu/cpu.h"

#include "memu/memory.h"
#include "memu/syscall.h"

static inline uint32_t bits(uint32_t x, int hi, int lo) {
  return (x >> lo) & ((UINT32_C(1) << (hi - lo + 1)) - 1u);
}

static inline uint32_t opcode(uint32_t inst) {
  return bits(inst, 6, 0);
}

static inline uint32_t rd(uint32_t inst) {
  return bits(inst, 11, 7);
}

static inline uint32_t funct3(uint32_t inst) {
  return bits(inst, 14, 12);
}

static inline uint32_t rs1(uint32_t inst) {
  return bits(inst, 19, 15);
}

static inline uint32_t rs2(uint32_t inst) {
  return bits(inst, 24, 20);
}

static inline uint32_t funct7(uint32_t inst) {
  return bits(inst, 31, 25);
}

static inline int32_t sign_extend(uint32_t x, int width) {
  uint32_t mask = UINT32_C(1) << (width - 1);
  return (int32_t)((x ^ mask) - mask);
}

static inline int32_t imm_i(uint32_t inst) {
  return sign_extend(bits(inst, 31, 20), 12);
}

static inline uint32_t csr_addr(uint32_t inst) {
  return bits(inst, 31, 20);
}

static inline int32_t imm_s(uint32_t inst) {
  uint32_t value = (bits(inst, 31, 25) << 5) | bits(inst, 11, 7);
  return sign_extend(value, 12);
}

static inline int32_t imm_b(uint32_t inst) {
  uint32_t value = 0;
  value |= bits(inst, 31, 31) << 12;
  value |= bits(inst, 7, 7) << 11;
  value |= bits(inst, 30, 25) << 5;
  value |= bits(inst, 11, 8) << 1;
  return sign_extend(value, 13);
}

static inline uint32_t imm_u(uint32_t inst) {
  return inst & UINT32_C(0xfffff000);
}

static inline int32_t imm_j(uint32_t inst) {
  uint32_t value = 0;
  value |= bits(inst, 31, 31) << 20;
  value |= bits(inst, 19, 12) << 12;
  value |= bits(inst, 20, 20) << 11;
  value |= bits(inst, 30, 21) << 1;
  return sign_extend(value, 21);
}

static inline uint32_t load_signed(uint32_t addr, int len, int width) {
  return (uint32_t)sign_extend(mem_read(addr, len), width);
}

static void invalid_inst(MEMU *memu, uint32_t pc, uint32_t inst, const char *reason);

static uint32_t div32(int32_t lhs, int32_t rhs) {
  if (rhs == 0) {
    return UINT32_MAX;
  }
  if (lhs == INT32_MIN && rhs == -1) {
    return (uint32_t)lhs;
  }
  return (uint32_t)(lhs / rhs);
}

static uint32_t rem32(int32_t lhs, int32_t rhs) {
  if (rhs == 0) {
    return (uint32_t)lhs;
  }
  if (lhs == INT32_MIN && rhs == -1) {
    return 0;
  }
  return (uint32_t)(lhs % rhs);
}

static const char *csr_name(uint32_t csr) {
  switch (csr) {
    case 0x180:
      return "satp";
    case 0x300:
      return "mstatus";
    case 0x305:
      return "mtvec";
    case 0x340:
      return "mscratch";
    case 0x341:
      return "mepc";
    case 0x342:
      return "mcause";
    case 0xf14:
      return "mhartid";
    case 0xb00:
      return "mcycle";
    case 0xb02:
      return "minstret";
    default:
      return NULL;
  }
}

static bool csr_read(const MEMU *memu, uint32_t csr, uint32_t *value) {
  const CPUState *cpu = &memu->cpu;
  switch (csr) {
    case 0x180:
      *value = cpu->satp;
      return true;
    case 0x300:
      *value = cpu->mstatus;
      return true;
    case 0x305:
      *value = cpu->mtvec;
      return true;
    case 0x340:
      *value = cpu->mscratch;
      return true;
    case 0x341:
      *value = cpu->mepc;
      return true;
    case 0x342:
      *value = cpu->mcause;
      return true;
    case 0xf14:
      *value = 0;
      return true;
    case 0xb00:
    case 0xb02:
      *value = (uint32_t)memu->instr_count;
      return true;
    default:
      return false;
  }
}

static bool csr_write(MEMU *memu, uint32_t csr, uint32_t value) {
  CPUState *cpu = &memu->cpu;
  switch (csr) {
    case 0x180:
      cpu->satp = value;
      return true;
    case 0x300:
      cpu->mstatus = value;
      return true;
    case 0x305:
      cpu->mtvec = value;
      return true;
    case 0x340:
      cpu->mscratch = value;
      return true;
    case 0x341:
      cpu->mepc = value;
      return true;
    case 0x342:
      cpu->mcause = value;
      return true;
    case 0xf14:
    case 0xb00:
    case 0xb02:
      return true;
    default:
      return false;
  }
}

static void exec_csr(MEMU *memu, uint32_t inst, uint32_t this_pc,
                     uint32_t f3, uint32_t rd_idx, uint32_t rs1_idx) {
  CPUState *cpu = &memu->cpu;
  uint32_t csr = csr_addr(inst);
  uint32_t old = 0;
  if (!csr_read(memu, csr, &old)) {
    const char *name = csr_name(csr);
    invalid_inst(memu, this_pc, inst, name != NULL ? name : "unsupported csr read");
    return;
  }

  uint32_t zimm = rs1_idx;
  uint32_t src = cpu_reg(cpu, (int)rs1_idx);
  uint32_t write_value = old;
  bool do_write = true;

  switch (f3) {
    case 0x1:
      write_value = src;
      break;
    case 0x2:
      do_write = rs1_idx != 0;
      write_value = old | src;
      break;
    case 0x3:
      do_write = rs1_idx != 0;
      write_value = old & ~src;
      break;
    case 0x5:
      write_value = zimm;
      break;
    case 0x6:
      do_write = zimm != 0;
      write_value = old | zimm;
      break;
    case 0x7:
      do_write = zimm != 0;
      write_value = old & ~zimm;
      break;
    default:
      invalid_inst(memu, this_pc, inst, "unsupported csr funct3");
      return;
  }

  if (do_write && !csr_write(memu, csr, write_value)) {
    invalid_inst(memu, this_pc, inst, "unsupported csr write");
    return;
  }
  cpu_set_reg(cpu, (int)rd_idx, old);
}

static void invalid_inst(MEMU *memu, uint32_t pc, uint32_t inst, const char *reason) {
  fprintf(stderr, "invalid instruction at pc=0x%08x, inst=0x%08x", pc, inst);
  if (reason != NULL) {
    fprintf(stderr, " (%s)", reason);
  }
  fputc('\n', stderr);
  cpu_dump_iringbuf(memu);
  memu->state = MEMU_STATE_ABORT;
}

void rv32i_exec_once(MEMU *memu) {
  CPUState *cpu = &memu->cpu;
  uint32_t this_pc = cpu->pc;
  uint32_t inst = inst_fetch(this_pc);
  uint32_t snpc = this_pc + 4;
  uint32_t dnpc = snpc;

  cpu_record_inst(memu, this_pc, inst);

  uint32_t op = opcode(inst);
  uint32_t rd_idx = rd(inst);
  uint32_t rs1_idx = rs1(inst);
  uint32_t rs2_idx = rs2(inst);
  uint32_t f3 = funct3(inst);
  uint32_t f7 = funct7(inst);
  uint32_t src1 = cpu_reg(cpu, (int)rs1_idx);
  uint32_t src2 = cpu_reg(cpu, (int)rs2_idx);

  switch (op) {
    case 0x0f:
      if (f3 != 0x0 && f3 != 0x1) {
        invalid_inst(memu, this_pc, inst, "unsupported fence funct3");
      }
      break;

    case 0x03: {
      uint32_t addr = src1 + (uint32_t)imm_i(inst);
      switch (f3) {
        case 0x0:
          cpu_set_reg(cpu, (int)rd_idx, load_signed(addr, 1, 8));
          break;
        case 0x1:
          cpu_set_reg(cpu, (int)rd_idx, load_signed(addr, 2, 16));
          break;
        case 0x2:
          cpu_set_reg(cpu, (int)rd_idx, mem_read(addr, 4));
          break;
        case 0x4:
          cpu_set_reg(cpu, (int)rd_idx, mem_read(addr, 1));
          break;
        case 0x5:
          cpu_set_reg(cpu, (int)rd_idx, mem_read(addr, 2));
          break;
        default:
          invalid_inst(memu, this_pc, inst, "unsupported load funct3");
          break;
      }
      break;
    }

    case 0x13:
      switch (f3) {
        case 0x0:
          cpu_set_reg(cpu, (int)rd_idx, src1 + (uint32_t)imm_i(inst));
          break;
        case 0x2:
          cpu_set_reg(cpu, (int)rd_idx, (int32_t)src1 < imm_i(inst));
          break;
        case 0x3:
          cpu_set_reg(cpu, (int)rd_idx, src1 < (uint32_t)imm_i(inst));
          break;
        case 0x4:
          cpu_set_reg(cpu, (int)rd_idx, src1 ^ (uint32_t)imm_i(inst));
          break;
        case 0x6:
          cpu_set_reg(cpu, (int)rd_idx, src1 | (uint32_t)imm_i(inst));
          break;
        case 0x7:
          cpu_set_reg(cpu, (int)rd_idx, src1 & (uint32_t)imm_i(inst));
          break;
        case 0x1:
          if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 << bits(inst, 24, 20));
          } else {
            invalid_inst(memu, this_pc, inst, "invalid slli funct7");
          }
          break;
        case 0x5:
          if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 >> bits(inst, 24, 20));
          } else if (f7 == 0x20) {
            cpu_set_reg(cpu, (int)rd_idx, (uint32_t)((int32_t)src1 >> bits(inst, 24, 20)));
          } else {
            invalid_inst(memu, this_pc, inst, "invalid shift-immediate funct7");
          }
          break;
        default:
          invalid_inst(memu, this_pc, inst, "unsupported OP-IMM funct3");
          break;
      }
      break;

    case 0x17:
      cpu_set_reg(cpu, (int)rd_idx, this_pc + imm_u(inst));
      break;

    case 0x23: {
      uint32_t addr = src1 + (uint32_t)imm_s(inst);
      switch (f3) {
        case 0x0:
          mem_write(addr, 1, src2);
          break;
        case 0x1:
          mem_write(addr, 2, src2);
          break;
        case 0x2:
          mem_write(addr, 4, src2);
          break;
        default:
          invalid_inst(memu, this_pc, inst, "unsupported store funct3");
          break;
      }
      break;
    }

    case 0x33:
      switch (f3) {
        case 0x0:
          if (f7 == 0x01) {
            cpu_set_reg(cpu, (int)rd_idx,
                        (uint32_t)((int64_t)(int32_t)src1 * (int64_t)(int32_t)src2));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 + src2);
          } else if (f7 == 0x20) {
            cpu_set_reg(cpu, (int)rd_idx, src1 - src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid add/sub funct7");
          }
          break;
        case 0x1:
          if (f7 == 0x01) {
            uint64_t product = (uint64_t)((int64_t)(int32_t)src1 * (int64_t)(int32_t)src2);
            cpu_set_reg(cpu, (int)rd_idx, (uint32_t)(product >> 32));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 << (src2 & 0x1f));
          } else {
            invalid_inst(memu, this_pc, inst, "invalid sll funct7");
          }
          break;
        case 0x2:
          if (f7 == 0x01) {
            int64_t product = (int64_t)(int32_t)src1 * (int64_t)(uint64_t)src2;
            cpu_set_reg(cpu, (int)rd_idx, (uint32_t)((uint64_t)product >> 32));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, (int32_t)src1 < (int32_t)src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid slt funct7");
          }
          break;
        case 0x3:
          if (f7 == 0x01) {
            uint64_t product = (uint64_t)src1 * (uint64_t)src2;
            cpu_set_reg(cpu, (int)rd_idx, (uint32_t)(product >> 32));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 < src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid sltu funct7");
          }
          break;
        case 0x4:
          if (f7 == 0x01) {
            cpu_set_reg(cpu, (int)rd_idx, div32((int32_t)src1, (int32_t)src2));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 ^ src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid xor funct7");
          }
          break;
        case 0x5:
          if (f7 == 0x01) {
            uint32_t result = (src2 == 0) ? UINT32_MAX : src1 / src2;
            cpu_set_reg(cpu, (int)rd_idx, result);
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 >> (src2 & 0x1f));
          } else if (f7 == 0x20) {
            cpu_set_reg(cpu, (int)rd_idx, (uint32_t)((int32_t)src1 >> (src2 & 0x1f)));
          } else {
            invalid_inst(memu, this_pc, inst, "invalid shift-right funct7");
          }
          break;
        case 0x6:
          if (f7 == 0x01) {
            cpu_set_reg(cpu, (int)rd_idx, rem32((int32_t)src1, (int32_t)src2));
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 | src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid or funct7");
          }
          break;
        case 0x7:
          if (f7 == 0x01) {
            uint32_t result = (src2 == 0) ? src1 : src1 % src2;
            cpu_set_reg(cpu, (int)rd_idx, result);
          } else if (f7 == 0x00) {
            cpu_set_reg(cpu, (int)rd_idx, src1 & src2);
          } else {
            invalid_inst(memu, this_pc, inst, "invalid and funct7");
          }
          break;
        default:
          invalid_inst(memu, this_pc, inst, "unsupported OP funct3");
          break;
      }
      break;

    case 0x37:
      cpu_set_reg(cpu, (int)rd_idx, imm_u(inst));
      break;

    case 0x63: {
      bool taken = false;
      switch (f3) {
        case 0x0:
          taken = src1 == src2;
          break;
        case 0x1:
          taken = src1 != src2;
          break;
        case 0x4:
          taken = (int32_t)src1 < (int32_t)src2;
          break;
        case 0x5:
          taken = (int32_t)src1 >= (int32_t)src2;
          break;
        case 0x6:
          taken = src1 < src2;
          break;
        case 0x7:
          taken = src1 >= src2;
          break;
        default:
          invalid_inst(memu, this_pc, inst, "unsupported branch funct3");
          break;
      }
      if (taken) {
        dnpc = this_pc + (uint32_t)imm_b(inst);
      }
      break;
    }

    case 0x67:
      if (f3 == 0x0) {
        cpu_set_reg(cpu, (int)rd_idx, snpc);
        dnpc = (src1 + (uint32_t)imm_i(inst)) & ~UINT32_C(1);
      } else {
        invalid_inst(memu, this_pc, inst, "unsupported jalr funct3");
      }
      break;

    case 0x6f:
      cpu_set_reg(cpu, (int)rd_idx, snpc);
      dnpc = this_pc + (uint32_t)imm_j(inst);
      break;

    case 0x73:
      if (inst == UINT32_C(0x00100073)) {
        memu->state = (cpu_reg(cpu, 10) == 0) ? MEMU_STATE_GOOD_TRAP : MEMU_STATE_BAD_TRAP;
        dnpc = this_pc;
      } else if (inst == UINT32_C(0x00000073)) {
        if (cpu->mtvec != 0) {
          cpu->mepc = this_pc;
          cpu->mcause = 11;
          dnpc = cpu->mtvec;
        } else {
          syscall_handle_ecall(memu, this_pc, snpc);
          dnpc = cpu->pc;
        }
      } else if (inst == UINT32_C(0x30200073)) {
        dnpc = cpu->mepc;
      } else if ((inst & UINT32_C(0xfe007fff)) == UINT32_C(0x12000073)) {
        // sfence.vma: no TLB, page tables are walked on every access
      } else if (f3 != 0) {
        exec_csr(memu, inst, this_pc, f3, rd_idx, rs1_idx);
      } else {
        invalid_inst(memu, this_pc, inst, "unsupported system instruction");
      }
      break;

    default:
      invalid_inst(memu, this_pc, inst, "unsupported opcode");
      break;
  }

  cpu->pc = dnpc;
}
