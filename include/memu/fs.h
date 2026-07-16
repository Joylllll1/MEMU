#ifndef MEMU_FS_H
#define MEMU_FS_H

#include "memu/cpu.h"
#include "memu/ramdisk.h"

#define MEMU_FS_MAX_FILES 64
#define MEMU_FS_MAX_OPEN 32
#define MEMU_FS_NAME_MAX 64

typedef enum {
  MEMU_FILE_RAMDISK,
  MEMU_FILE_PROC_DISPINFO,
  MEMU_FILE_DEV_EVENTS,
  MEMU_FILE_DEV_FB,
} MEMUFileKind;

typedef struct {
  char name[MEMU_FS_NAME_MAX];
  uint32_t size;
  uint32_t disk_offset;
  MEMUFileKind kind;
} MEMUFileInfo;

typedef struct {
  bool used;
  int file_index;
  uint32_t open_offset;
} MEMUOpenFile;

struct MEMUFS {
  MEMURamdisk ramdisk;
  MEMUFileInfo files[MEMU_FS_MAX_FILES];
  int file_count;
  MEMUOpenFile open_files[MEMU_FS_MAX_OPEN];
};

void fs_init(MEMUFS *fs);
void fs_free(MEMUFS *fs);
void fs_load_ramdisk(MEMUFS *fs, const char *path);
void fs_attach(MEMU *memu, MEMUFS *fs);
bool fs_load_program(MEMU *memu, const char *path);
uint32_t fs_open(MEMUFS *fs, const char *path);
uint32_t fs_read(MEMUFS *fs, uint32_t fd, uint32_t guest_buf, uint32_t len);
uint32_t fs_write(MEMUFS *fs, uint32_t fd, uint32_t guest_buf, uint32_t len);
uint32_t fs_lseek(MEMUFS *fs, uint32_t fd, int32_t offset, uint32_t whence);
uint32_t fs_close(MEMUFS *fs, uint32_t fd);

#endif
