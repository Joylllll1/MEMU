#include "memu/ramdisk.h"

#include <errno.h>
#include <string.h>

void ramdisk_init(MEMURamdisk *ramdisk) {
  ramdisk->data = NULL;
  ramdisk->size = 0;
}

void ramdisk_free(MEMURamdisk *ramdisk) {
  free(ramdisk->data);
  ramdisk->data = NULL;
  ramdisk->size = 0;
}

void ramdisk_load(MEMURamdisk *ramdisk, const char *path) {
  FILE *fp = fopen(path, "rb");
  MEMU_ASSERT(fp != NULL, "failed to open ramdisk %s: %s", path, strerror(errno));
  MEMU_ASSERT(fseek(fp, 0, SEEK_END) == 0, "failed to seek ramdisk %s", path);
  long size = ftell(fp);
  MEMU_ASSERT(size >= 0, "failed to size ramdisk %s", path);
  MEMU_ASSERT(fseek(fp, 0, SEEK_SET) == 0, "failed to rewind ramdisk %s", path);

  uint8_t *data = NULL;
  if (size > 0) {
    data = malloc((size_t)size);
    MEMU_ASSERT(data != NULL, "failed to allocate ramdisk: %ld bytes", size);
    size_t nread = fread(data, 1, (size_t)size, fp);
    MEMU_ASSERT(nread == (size_t)size, "short read loading ramdisk %s", path);
  }
  fclose(fp);

  ramdisk_free(ramdisk);
  ramdisk->data = data;
  ramdisk->size = (size_t)size;
}

size_t ramdisk_read(const MEMURamdisk *ramdisk, void *buf, size_t offset, size_t len) {
  if (offset >= ramdisk->size) {
    return 0;
  }
  size_t avail = ramdisk->size - offset;
  size_t actual = len < avail ? len : avail;
  memcpy(buf, ramdisk->data + offset, actual);
  return actual;
}

size_t ramdisk_write(MEMURamdisk *ramdisk, const void *buf, size_t offset, size_t len) {
  if (offset >= ramdisk->size) {
    return 0;
  }
  size_t avail = ramdisk->size - offset;
  size_t actual = len < avail ? len : avail;
  memcpy(ramdisk->data + offset, buf, actual);
  return actual;
}
