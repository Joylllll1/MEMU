#include "memu/batch.h"

#include "memu/loader.h"
#include "memu/memory.h"
#include "memu/syscall.h"

#include <string.h>

void batch_init(MEMUBatch *batch, const char *const *programs, int count) {
  MEMU_ASSERT(count > 0, "batch-list requires at least one program");
  MEMU_ASSERT(count <= MEMU_BATCH_MAX_PROGRAMS,
              "batch-list supports at most %d programs, got %d",
              MEMU_BATCH_MAX_PROGRAMS, count);

  memset(batch, 0, sizeof(*batch));
  batch->count = count;
  batch->current = 0;
  for (int i = 0; i < count; i++) {
    batch->programs[i] = programs[i];
  }
}

void batch_attach(MEMU *memu, MEMUBatch *batch) {
  memu->batch = batch;
}

void batch_load_current(MEMU *memu) {
  MEMUBatch *batch = memu->batch;
  MEMU_ASSERT(batch != NULL, "batch runtime is not attached");
  MEMU_ASSERT(batch->current >= 0 && batch->current < batch->count,
              "batch current index out of range: %d", batch->current);

  memory_init();
  uint32_t entry = 0;
  load_image(batch->programs[batch->current], MEMU_MEM_BASE, &entry);
  memu->cpu = (CPUState){
    .pc = entry,
  };
  syscall_reset_program(memu);
  memu->state = MEMU_STATE_RUNNING;
  printf("MEMU batch: loaded program %d/%d: %s\n",
         batch->current + 1, batch->count, batch->programs[batch->current]);
}

void batch_handle_exit(MEMU *memu, int code) {
  MEMUBatch *batch = memu->batch;
  MEMU_ASSERT(batch != NULL, "batch runtime is not attached");

  if (code != 0) {
    memu->state = MEMU_STATE_BAD_TRAP;
    return;
  }

  batch->current++;
  if (batch->current >= batch->count) {
    memu->state = MEMU_STATE_GOOD_TRAP;
    return;
  }

  batch_load_current(memu);
}
