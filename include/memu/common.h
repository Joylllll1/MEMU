#ifndef MEMU_COMMON_H
#define MEMU_COMMON_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define MEMU_VERSION "0.1.0"

#define MEMU_MEM_BASE UINT32_C(0x80000000)
#define MEMU_MEM_SIZE (128u * 1024u * 1024u)

#define MEMU_ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))

void memu_panic(const char *file, int line, const char *fmt, ...);

#define MEMU_PANIC(...) memu_panic(__FILE__, __LINE__, __VA_ARGS__)

#define MEMU_ASSERT(cond, ...)            \
  do {                                    \
    if (!(cond)) {                        \
      MEMU_PANIC(__VA_ARGS__);            \
    }                                     \
  } while (0)

#endif
