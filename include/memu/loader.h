#ifndef MEMU_LOADER_H
#define MEMU_LOADER_H

#include "memu/common.h"

bool load_image(const char *path, uint32_t load_addr, uint32_t *entry);
bool load_elf(const char *path, uint32_t *entry);

#endif
