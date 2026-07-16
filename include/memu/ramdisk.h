#ifndef MEMU_RAMDISK_H
#define MEMU_RAMDISK_H

#include "memu/common.h"

typedef struct {
  uint8_t *data;
  size_t size;
} MEMURamdisk;

void ramdisk_init(MEMURamdisk *ramdisk);
void ramdisk_free(MEMURamdisk *ramdisk);
void ramdisk_load(MEMURamdisk *ramdisk, const char *path);
size_t ramdisk_read(const MEMURamdisk *ramdisk, void *buf, size_t offset, size_t len);
size_t ramdisk_write(MEMURamdisk *ramdisk, const void *buf, size_t offset, size_t len);

#endif
