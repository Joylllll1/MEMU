#ifndef MEMU_EXPR_H
#define MEMU_EXPR_H

#include "memu/cpu.h"

uint32_t expr_eval(MEMU *memu, const char *s, bool *success);

#endif
