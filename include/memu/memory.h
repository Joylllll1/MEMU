#ifndef MEMU_MEMORY_H
#define MEMU_MEMORY_H

#include "memu/common.h"

void memory_init(void);

bool mem_in_range(uint32_t addr, uint32_t len);
uint8_t *guest_to_host(uint32_t addr);
uint32_t mem_read(uint32_t addr, int len);
void mem_write(uint32_t addr, int len, uint32_t data);
uint32_t inst_fetch(uint32_t pc);

#endif
