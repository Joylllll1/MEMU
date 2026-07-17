#include "memu/memory.h"

#include "memu/device.h"
#include "memu/mmu.h"

#include <string.h>

static uint8_t pmem[MEMU_MEM_SIZE];

bool mem_in_range(uint32_t addr, uint32_t len) {
  if (addr < MEMU_MEM_BASE) {
    return false;
  }

  uint64_t offset = (uint64_t)addr - MEMU_MEM_BASE;
  return offset + (uint64_t)len <= MEMU_MEM_SIZE;
}

uint8_t *guest_to_host(uint32_t addr) {
  MEMU_ASSERT(mem_in_range(addr, 1),
              "guest address out of range: 0x%08x", addr);
  return &pmem[(uint64_t)addr - MEMU_MEM_BASE];
}

static size_t guest_to_offset(uint32_t addr, int len) {
  MEMU_ASSERT(len == 1 || len == 2 || len == 4,
              "invalid memory access length: %d", len);
  MEMU_ASSERT(mem_in_range(addr, (uint32_t)len),
              "guest memory out of range: addr=0x%08x len=%d", addr, len);
  return (size_t)((uint64_t)addr - MEMU_MEM_BASE);
}

static inline uint32_t pmem_read(size_t off, int len) {
  switch (len) {
    case 1:
      return pmem[off];
    case 2:
      return (uint32_t)pmem[off] | ((uint32_t)pmem[off + 1u] << 8);
    case 4:
      return (uint32_t)pmem[off] |
             ((uint32_t)pmem[off + 1u] << 8) |
             ((uint32_t)pmem[off + 2u] << 16) |
             ((uint32_t)pmem[off + 3u] << 24);
    default:
      MEMU_PANIC("invalid memory access length: %d", len);
  }
  return 0;
}

static inline void pmem_write(size_t off, int len, uint32_t data) {
  switch (len) {
    case 1:
      pmem[off] = (uint8_t)data;
      return;
    case 2:
      pmem[off] = (uint8_t)data;
      pmem[off + 1u] = (uint8_t)(data >> 8);
      return;
    case 4:
      pmem[off] = (uint8_t)data;
      pmem[off + 1u] = (uint8_t)(data >> 8);
      pmem[off + 2u] = (uint8_t)(data >> 16);
      pmem[off + 3u] = (uint8_t)(data >> 24);
      return;
    default:
      MEMU_PANIC("invalid memory access length: %d", len);
  }
}

void memory_init(void) {
  memset(pmem, 0, sizeof(pmem));
}

uint32_t mem_read(uint32_t addr, int len) {
  if (mmu_active()) {
    if ((addr & 0xfffu) + (uint32_t)len > 0x1000u) {
      uint32_t value = 0;
      for (int i = 0; i < len; i++) {
        value |= (mem_read(addr + (uint32_t)i, 1) & 0xffu) << (8 * i);
      }
      return value;
    }
    addr = mmu_translate(addr, MMU_ACCESS_LOAD);
  }

  if (addr >= MEMU_MEM_BASE) {
    uint64_t off64 = (uint64_t)addr - MEMU_MEM_BASE;
    if (off64 + (uint64_t)len <= MEMU_MEM_SIZE) {
      return pmem_read((size_t)off64, len);
    }
  }

  if (device_in_range(addr, (uint32_t)len)) {
    return device_read(addr, len);
  }

  (void)guest_to_offset(addr, len);
  return 0;
}

void mem_write(uint32_t addr, int len, uint32_t data) {
  if (mmu_active()) {
    if ((addr & 0xfffu) + (uint32_t)len > 0x1000u) {
      for (int i = 0; i < len; i++) {
        mem_write(addr + (uint32_t)i, 1, (data >> (8 * i)) & 0xffu);
      }
      return;
    }
    addr = mmu_translate(addr, MMU_ACCESS_STORE);
  }

  if (addr >= MEMU_MEM_BASE) {
    uint64_t off64 = (uint64_t)addr - MEMU_MEM_BASE;
    if (off64 + (uint64_t)len <= MEMU_MEM_SIZE) {
      pmem_write((size_t)off64, len, data);
      return;
    }
  }

  if (device_in_range(addr, (uint32_t)len)) {
    device_write(addr, len, data);
    return;
  }

  (void)guest_to_offset(addr, len);
}

uint32_t inst_fetch(uint32_t pc) {
  uint32_t paddr = mmu_active() ? mmu_translate(pc, MMU_ACCESS_FETCH) : pc;
  MEMU_ASSERT(mem_in_range(paddr, 4),
              "instruction fetch out of range: pc=0x%08x paddr=0x%08x",
              pc, paddr);
  return pmem_read((size_t)((uint64_t)paddr - MEMU_MEM_BASE), 4);
}
