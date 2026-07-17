  .section .text.start, "ax"
  .globl _start
_start:
  la sp, _stack_top
  call main
  ebreak
1:
  j 1b

  .section .text, "ax"
  .globl trap_entry
  .align 2
trap_entry:
  csrci mstatus, 8
  csrw  mscratch, x31
  la    x31, cur_save
  lw    x31, 0(x31)
  sw    x1,  4(x31)
  sw    x2,  8(x31)
  sw    x3, 12(x31)
  sw    x4, 16(x31)
  sw    x5, 20(x31)
  sw    x6, 24(x31)
  sw    x7, 28(x31)
  sw    x8, 32(x31)
  sw    x9, 36(x31)
  sw    x10, 40(x31)
  sw    x11, 44(x31)
  sw    x12, 48(x31)
  sw    x13, 52(x31)
  sw    x14, 56(x31)
  sw    x15, 60(x31)
  sw    x16, 64(x31)
  sw    x17, 68(x31)
  sw    x18, 72(x31)
  sw    x19, 76(x31)
  sw    x20, 80(x31)
  sw    x21, 84(x31)
  sw    x22, 88(x31)
  sw    x23, 92(x31)
  sw    x24, 96(x31)
  sw    x25, 100(x31)
  sw    x26, 104(x31)
  sw    x27, 108(x31)
  sw    x28, 112(x31)
  sw    x29, 116(x31)
  sw    x30, 120(x31)
  csrr  x1, mscratch
  sw    x1, 124(x31)
  csrr  x1, mepc
  sw    x1, 0(x31)
  la    sp, _isr_stack_top
  call  mp_isr
  mv    x31, a0
  lw    x1, 0(x31)
  csrw  mepc, x1
  lw    x1,  4(x31)
  lw    x2,  8(x31)
  lw    x3, 12(x31)
  lw    x4, 16(x31)
  lw    x5, 20(x31)
  lw    x6, 24(x31)
  lw    x7, 28(x31)
  lw    x8, 32(x31)
  lw    x9, 36(x31)
  lw    x10, 40(x31)
  lw    x11, 44(x31)
  lw    x12, 48(x31)
  lw    x13, 52(x31)
  lw    x14, 56(x31)
  lw    x15, 60(x31)
  lw    x16, 64(x31)
  lw    x17, 68(x31)
  lw    x18, 72(x31)
  lw    x19, 76(x31)
  lw    x20, 80(x31)
  lw    x21, 84(x31)
  lw    x22, 88(x31)
  lw    x23, 92(x31)
  lw    x24, 96(x31)
  lw    x25, 100(x31)
  lw    x26, 104(x31)
  lw    x27, 108(x31)
  lw    x28, 112(x31)
  lw    x29, 116(x31)
  lw    x30, 120(x31)
  lw    x31, 124(x31)
  csrsi mstatus, 8
  mret

  # User process body. Uses only absolute addressing (lui/addi) plus local
  # branches, so the same bytes run correctly after being copied into any
  # physical page mapped at USER_CODE_VA.
  .globl user_code_start
  .globl user_code_end
  .align 2
user_code_start:
  lui   a0, 0x40001
  lui   a2, 0xa0000
  addi  a2, a2, 0x3f8
1:
  li    t0, 10000
2:
  addi  t0, t0, -1
  bnez  t0, 2b
  lbu   a1, 0(a0)
  sb    a1, 0(a2)
  lw    t1, 4(a0)
  addi  t1, t1, 1
  sw    t1, 4(a0)
  j     1b
user_code_end:

  .section .bss.stack, "aw", @nobits
  .align 4
  .space 4096
_stack_top:
  .space 4096
  .globl _isr_stack_top
_isr_stack_top:
