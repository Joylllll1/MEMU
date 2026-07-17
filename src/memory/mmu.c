#include "memu/mmu.h"

#include "memu/memory.h"

#define SATP_MODE_BIT UINT32_C(0x80000000)
#define SATP_PPN_MASK UINT32_C(0x003fffff)

#define PTE_V UINT32_C(0x01)
#define PTE_R UINT32_C(0x02)
#define PTE_W UINT32_C(0x04)
#define PTE_X UINT32_C(0x08)

static const CPUState *mmu_cpu = NULL;

void mmu_set_cpu(const CPUState *cpu) {
  mmu_cpu = cpu;
}

bool mmu_active(void) {
  return mmu_cpu != NULL && (mmu_cpu->satp & SATP_MODE_BIT) != 0;
}

static const char *access_name(MMUAccess access) {
  switch (access) {
    case MMU_ACCESS_FETCH:
      return "fetch";
    case MMU_ACCESS_LOAD:
      return "load";
    case MMU_ACCESS_STORE:
      return "store";
  }
  return "unknown";
}

static uint32_t phys_read32(uint32_t paddr) {
  MEMU_ASSERT(mem_in_range(paddr, 4),
              "page table walk outside physical memory: paddr=0x%08x", paddr);
  const uint8_t *p = guest_to_host(paddr);
  return (uint32_t)p[0] |
         ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

uint32_t mmu_translate(uint32_t vaddr, MMUAccess access) {
  if (!mmu_active()) {
    return vaddr;
  }

  uint32_t pc = mmu_cpu->pc;
  uint32_t root = (mmu_cpu->satp & SATP_PPN_MASK) << 12;
  uint32_t vpn1 = (vaddr >> 22) & 0x3ffu;
  uint32_t vpn0 = (vaddr >> 12) & 0x3ffu;

  uint32_t pte1 = phys_read32(root + vpn1 * 4u);
  if ((pte1 & PTE_V) == 0) {
    MEMU_PANIC("page fault: level-1 pte invalid: vaddr=0x%08x access=%s "
               "pc=0x%08x pte=0x%08x root=0x%08x",
               vaddr, access_name(access), pc, pte1, root);
  }
  if ((pte1 & (PTE_R | PTE_W | PTE_X)) != 0) {
    MEMU_PANIC("page fault: superpage unsupported: vaddr=0x%08x access=%s "
               "pc=0x%08x pte=0x%08x",
               vaddr, access_name(access), pc, pte1);
  }

  uint32_t leaf_base = (pte1 >> 10) << 12;
  uint32_t pte0 = phys_read32(leaf_base + vpn0 * 4u);
  if ((pte0 & PTE_V) == 0) {
    MEMU_PANIC("page fault: level-0 pte invalid: vaddr=0x%08x access=%s "
               "pc=0x%08x pte=0x%08x table=0x%08x",
               vaddr, access_name(access), pc, pte0, leaf_base);
  }

  uint32_t need = (access == MMU_ACCESS_FETCH) ? PTE_X :
                  (access == MMU_ACCESS_LOAD) ? PTE_R : PTE_W;
  if ((pte0 & need) == 0) {
    MEMU_PANIC("page fault: permission denied: vaddr=0x%08x access=%s "
               "pc=0x%08x pte=0x%08x",
               vaddr, access_name(access), pc, pte0);
  }

  return ((pte0 >> 10) << 12) | (vaddr & 0xfffu);
}
