#include <stdint.h>

#define PTE_V UINT32_C(0x1)
#define PTE_R UINT32_C(0x2)
#define PTE_W UINT32_C(0x4)
#define PTE_X UINT32_C(0x8)

#define PGSIZE 4096u
#define SERIAL ((volatile uint8_t *)0xa00003f8u)

#define USER_CODE_VA 0x40000000u
#define SWITCH_LIMIT 16

extern const uint8_t user_code_start[];
extern const uint8_t user_code_end[];
extern void trap_entry(void);

static uint32_t root_a[1024] __attribute__((aligned(4096)));
static uint32_t root_b[1024] __attribute__((aligned(4096)));
static uint32_t kpt_ram[1024] __attribute__((aligned(4096)));
static uint32_t kpt_mmio[1024] __attribute__((aligned(4096)));
static uint32_t upt_a[1024] __attribute__((aligned(4096)));
static uint32_t upt_b[1024] __attribute__((aligned(4096)));
static uint8_t code_a[4096] __attribute__((aligned(4096)));
static uint8_t code_b[4096] __attribute__((aligned(4096)));
static uint8_t data_a[4096] __attribute__((aligned(4096)));
static uint8_t data_b[4096] __attribute__((aligned(4096)));

static uint32_t ctx_a[32];
static uint32_t ctx_b[32];
uint32_t *cur_save = ctx_a;

static uint32_t satp_a;
static uint32_t satp_b;
static int cur;
static int switch_count;

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

static void build_tables(void) {
  for (uint32_t i = 0; i < 1024; i++) {
    kpt_ram[i] = pte_leaf(0x80000000u + i * PGSIZE, PTE_R | PTE_W | PTE_X);
    kpt_mmio[i] = pte_leaf(0xa0000000u + i * PGSIZE, PTE_R | PTE_W);
  }
  root_a[0x200] = pte_table(kpt_ram);
  root_a[0x280] = pte_table(kpt_mmio);
  root_a[0x100] = pte_table(upt_a);
  root_b[0x200] = pte_table(kpt_ram);
  root_b[0x280] = pte_table(kpt_mmio);
  root_b[0x100] = pte_table(upt_b);

  upt_a[0] = pte_leaf((uint32_t)(uintptr_t)code_a, PTE_R | PTE_X);
  upt_a[1] = pte_leaf((uint32_t)(uintptr_t)data_a, PTE_R | PTE_W);
  upt_b[0] = pte_leaf((uint32_t)(uintptr_t)code_b, PTE_R | PTE_X);
  upt_b[1] = pte_leaf((uint32_t)(uintptr_t)data_b, PTE_R | PTE_W);

  satp_a = 0x80000000u | ((uint32_t)(uintptr_t)root_a >> 12);
  satp_b = 0x80000000u | ((uint32_t)(uintptr_t)root_b >> 12);
}

uint32_t *mp_isr(void) {
  switch_count++;
  if (switch_count >= SWITCH_LIMIT) {
    serial_puts("\nPASS: mp-os\n");
    __asm__ volatile("li a0, 0\n\tebreak" ::: "a0");
  }
  cur = 1 - cur;
  uint32_t *next = (cur == 0) ? ctx_a : ctx_b;
  uint32_t next_satp = (cur == 0) ? satp_a : satp_b;
  cur_save = next;
  __asm__ volatile("csrw satp, %0\n\tsfence.vma" :: "r"(next_satp));
  return next;
}

int main(void) {
  build_tables();

  uint32_t code_len = (uint32_t)(user_code_end - user_code_start);
  for (uint32_t i = 0; i < code_len; i++) {
    code_a[i] = user_code_start[i];
    code_b[i] = user_code_start[i];
  }
  data_a[0] = 'A';
  data_b[0] = 'B';

  ctx_a[0] = USER_CODE_VA;
  ctx_b[0] = USER_CODE_VA;
  cur = 0;
  cur_save = ctx_a;

  serial_puts("mp-os: start\n");
  __asm__ volatile(
      "csrw satp, %0\n\t"
      "sfence.vma\n\t"
      "csrw mtvec, %1\n\t"
      "csrw mepc, %2\n\t"
      "csrsi mstatus, 8\n\t"
      "mret"
      :: "r"(satp_a), "r"((uint32_t)(uintptr_t)trap_entry), "r"(USER_CODE_VA));

  serial_puts("FAIL: mret did not enter user process\n");
  return 1;
}
