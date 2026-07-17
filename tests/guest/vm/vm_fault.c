#include <stdint.h>

#define PTE_V UINT32_C(0x1)
#define PTE_R UINT32_C(0x2)
#define PTE_W UINT32_C(0x4)
#define PTE_X UINT32_C(0x8)

#define PGSIZE 4096u
#define SERIAL ((volatile uint8_t *)0xa00003f8u)

static uint32_t root_pt[1024] __attribute__((aligned(4096)));
static uint32_t kpt_ram[1024] __attribute__((aligned(4096)));
static uint32_t kpt_mmio[1024] __attribute__((aligned(4096)));

uint32_t *cur_save;

static uint32_t pte_leaf(uint32_t pa, uint32_t flags) {
  return ((pa >> 12) << 10) | flags | PTE_V;
}

static uint32_t pte_table(const void *table) {
  return (((uint32_t)(uintptr_t)table >> 12) << 10) | PTE_V;
}

static void serial_puts(const char *s) {
  while (*s != '\0') {
    *SERIAL = (uint8_t)*s++;
  }
}

uint32_t *mp_isr(void) {
  return cur_save;
}

int main(void) {
  for (uint32_t i = 0; i < 1024; i++) {
    kpt_ram[i] = pte_leaf(0x80000000u + i * PGSIZE, PTE_R | PTE_W | PTE_X);
    kpt_mmio[i] = pte_leaf(0xa0000000u + i * PGSIZE, PTE_R | PTE_W);
  }
  root_pt[0x200] = pte_table(kpt_ram);
  root_pt[0x280] = pte_table(kpt_mmio);

  uint32_t satp = 0x80000000u | ((uint32_t)(uintptr_t)root_pt >> 12);
  serial_puts("vm-fault: enabling satp\n");
  __asm__ volatile("csrw satp, %0\n\tsfence.vma" :: "r"(satp));

  volatile uint32_t *bad = (volatile uint32_t *)0x50000000u;
  uint32_t value = *bad;
  (void)value;

  serial_puts("FAIL: survived unmapped access\n");
  __asm__ volatile("li a0, 1\n\tebreak" ::: "a0");
  return 1;
}
