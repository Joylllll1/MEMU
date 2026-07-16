#ifndef MEMU_WATCHPOINT_H
#define MEMU_WATCHPOINT_H

#include "memu/cpu.h"

void watchpoint_init(void);
int watchpoint_set(MEMU *memu, const char *expr);
bool watchpoint_delete(int id);
bool watchpoint_check(MEMU *memu);
void watchpoint_display(void);

#endif
