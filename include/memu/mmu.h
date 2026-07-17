#ifndef MEMU_MMU_H
#define MEMU_MMU_H

#include "memu/common.h"
#include "memu/cpu.h"

typedef enum {
  MMU_ACCESS_FETCH,
  MMU_ACCESS_LOAD,
  MMU_ACCESS_STORE,
} MMUAccess;

void mmu_set_cpu(const CPUState *cpu);
bool mmu_active(void);
uint32_t mmu_translate(uint32_t vaddr, MMUAccess access);

#endif
