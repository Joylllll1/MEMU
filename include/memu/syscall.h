#ifndef MEMU_SYSCALL_H
#define MEMU_SYSCALL_H

#include "memu/cpu.h"

#define MEMU_SYS_WRITE 64u
#define MEMU_SYS_EXIT 93u
#define MEMU_SYS_BRK 214u
#define MEMU_SYS_OPENAT 56u
#define MEMU_SYS_CLOSE 57u
#define MEMU_SYS_LSEEK 62u
#define MEMU_SYS_READ 63u
#define MEMU_SYS_OPEN 1024u

void syscall_reset_program(MEMU *memu);
void syscall_handle_ecall(MEMU *memu, uint32_t pc, uint32_t snpc);

#endif
