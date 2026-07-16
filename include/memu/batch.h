#ifndef MEMU_BATCH_H
#define MEMU_BATCH_H

#include "memu/cpu.h"

#define MEMU_BATCH_MAX_PROGRAMS 16

struct MEMUBatch {
  const char *programs[MEMU_BATCH_MAX_PROGRAMS];
  int count;
  int current;
};

void batch_init(MEMUBatch *batch, const char *const *programs, int count);
void batch_attach(MEMU *memu, MEMUBatch *batch);
void batch_load_current(MEMU *memu);
void batch_handle_exit(MEMU *memu, int code);

#endif
