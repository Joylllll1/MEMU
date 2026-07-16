#include <stdint.h>

volatile uint32_t data_value = 0x12345678u;
volatile uint32_t bss_value;
volatile uint32_t sink[8];

static uint32_t read_mhartid(void) {
  uint32_t value;
  __asm__ volatile("csrr %0, mhartid" : "=r"(value));
  return value;
}

static uint32_t read_mcycle(void) {
  uint32_t value;
  __asm__ volatile("csrr %0, mcycle" : "=r"(value));
  return value;
}

static void use_fences(void) {
  __asm__ volatile("fence" ::: "memory");
  __asm__ volatile("fence.i" ::: "memory");
}

int main(void) {
  uint32_t fail = 0;

  if (data_value != 0x12345678u) {
    fail |= 1u;
  }
  if (bss_value != 0) {
    fail |= 2u;
  }
  bss_value = 0xdeadbeefu;
  if (bss_value != 0xdeadbeefu) {
    fail |= 4u;
  }

  int32_t sdiv_lhs = -22;
  int32_t sdiv_rhs = 5;
  sink[0] = (uint32_t)(sdiv_lhs / sdiv_rhs);
  sink[1] = (uint32_t)(sdiv_lhs % sdiv_rhs);
  if (sink[0] != 0xfffffffcu || sink[1] != 0xfffffffeu) {
    fail |= 8u;
  }

  uint32_t udiv_lhs = 0xffffffffu;
  uint32_t udiv_rhs = 2u;
  sink[2] = udiv_lhs / udiv_rhs;
  sink[3] = udiv_lhs % udiv_rhs;
  sink[4] = udiv_lhs * udiv_rhs;
  if (sink[2] != 0x7fffffffu || sink[3] != 1u || sink[4] != 0xfffffffeu) {
    fail |= 16u;
  }

  if (read_mhartid() != 0) {
    fail |= 32u;
  }
  uint32_t c0 = read_mcycle();
  uint32_t c1 = read_mcycle();
  if (c1 < c0) {
    fail |= 64u;
  }
  use_fences();

  return (int)fail;
}
