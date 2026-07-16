  .section .text.start, "ax"
  .globl _start
_start:
  la sp, _stack_top
  call main
  ebreak
1:
  j 1b

  .section .bss.stack, "aw", @nobits
  .align 4
  .space 4096
_stack_top:
