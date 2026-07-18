#include "memu/fs.h"

#include "memu/device.h"
#include "memu/memory.h"
#include "memu/syscall.h"

#include <string.h>

#define FS_MAGIC "MEMUFS1"
#define FS_MAGIC_SIZE 8u
#define FS_HEADER_SIZE 12u
#define FS_RECORD_SIZE (MEMU_FS_NAME_MAX + 8u)
#define FS_STD_FD_BASE 3u
#define FS_PROC_DISPINFO "WIDTH:400\nHEIGHT:300\n"

static uint32_t read_le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void guest_write_bytes(uint32_t guest_addr, const uint8_t *data, uint32_t len) {
  for (uint32_t i = 0; i < len; i++) {
    mem_write(guest_addr + i, 1, data[i]);
  }
}

static uint32_t guest_write_string(uint32_t guest_addr, const char *s, uint32_t len) {
  uint32_t actual = (uint32_t)strlen(s);
  if (actual > len) {
    actual = len;
  }
  guest_write_bytes(guest_addr, (const uint8_t *)s, actual);
  return actual;
}

void fs_init(MEMUFS *fs) {
  memset(fs, 0, sizeof(*fs));
  ramdisk_init(&fs->ramdisk);
}

void fs_free(MEMUFS *fs) {
  ramdisk_free(&fs->ramdisk);
  memset(fs, 0, sizeof(*fs));
}

static void add_special(MEMUFS *fs, const char *name, MEMUFileKind kind, uint32_t size) {
  MEMU_ASSERT(fs->file_count < MEMU_FS_MAX_FILES,
              "too many files in ramdisk table");
  MEMUFileInfo *file = &fs->files[fs->file_count++];
  snprintf(file->name, sizeof(file->name), "%s", name);
  file->kind = kind;
  file->size = size;
  file->disk_offset = 0;
}

void fs_load_ramdisk(MEMUFS *fs, const char *path) {
  ramdisk_load(&fs->ramdisk, path);
  MEMU_ASSERT(fs->ramdisk.size >= FS_HEADER_SIZE, "ramdisk too small: %s", path);
  const uint8_t *data = fs->ramdisk.data;
  MEMU_ASSERT(memcmp(data, FS_MAGIC, strlen(FS_MAGIC)) == 0,
              "invalid ramdisk magic: %s", path);

  uint32_t count = read_le32(data + FS_MAGIC_SIZE);
  MEMU_ASSERT(count <= MEMU_FS_MAX_FILES, "ramdisk file count too large: %u", count);
  size_t table_end = FS_HEADER_SIZE + (size_t)count * FS_RECORD_SIZE;
  MEMU_ASSERT(table_end <= fs->ramdisk.size, "ramdisk file table exceeds image");

  fs->file_count = 0;
  memset(fs->open_files, 0, sizeof(fs->open_files));
  for (uint32_t i = 0; i < count; i++) {
    const uint8_t *rec = data + FS_HEADER_SIZE + (size_t)i * FS_RECORD_SIZE;
    MEMUFileInfo *file = &fs->files[fs->file_count++];
    memcpy(file->name, rec, MEMU_FS_NAME_MAX);
    file->name[MEMU_FS_NAME_MAX - 1] = '\0';
    file->disk_offset = read_le32(rec + MEMU_FS_NAME_MAX);
    file->size = read_le32(rec + MEMU_FS_NAME_MAX + 4u);
    file->kind = MEMU_FILE_RAMDISK;
    MEMU_ASSERT((uint64_t)file->disk_offset + file->size <= fs->ramdisk.size,
                "ramdisk file out of range: %s", file->name);
  }

  add_special(fs, "/proc/dispinfo", MEMU_FILE_PROC_DISPINFO,
              (uint32_t)strlen(FS_PROC_DISPINFO));
  add_special(fs, "/dev/events", MEMU_FILE_DEV_EVENTS, 0);
  add_special(fs, "/dev/fb", MEMU_FILE_DEV_FB, MEMU_FB_SIZE);
  add_special(fs, "/dev/sbctl", MEMU_FILE_DEV_SBCTL, 12);
  add_special(fs, "/dev/sb", MEMU_FILE_DEV_SB, UINT32_MAX);

  printf("MEMU: loaded ramdisk %s, files=%d, bytes=%zu\n",
         path, fs->file_count, fs->ramdisk.size);
}

void fs_attach(MEMU *memu, MEMUFS *fs) {
  memu->fs = fs;
}

static int find_file(const MEMUFS *fs, const char *path) {
  for (int i = 0; i < fs->file_count; i++) {
    if (strcmp(fs->files[i].name, path) == 0) {
      return i;
    }
  }
  return -1;
}

bool fs_load_program(MEMU *memu, const char *path) {
  MEMU_ASSERT(memu->fs != NULL, "--run requires --ramdisk");
  int idx = find_file(memu->fs, path);
  if (idx < 0) {
    fprintf(stderr, "fs loader: program not found: %s\n", path);
    return false;
  }

  const MEMUFileInfo *file = &memu->fs->files[idx];
  MEMU_ASSERT(file->kind == MEMU_FILE_RAMDISK,
              "fs loader can load only regular files: %s", path);
  MEMU_ASSERT(file->size <= MEMU_MEM_SIZE,
              "fs program too large: %s (%u bytes)", path, file->size);

  memory_init();
  for (uint32_t i = 0; i < file->size; i++) {
    mem_write(MEMU_MEM_BASE + i, 1, memu->fs->ramdisk.data[file->disk_offset + i]);
  }
  memu->cpu = (CPUState){
    .pc = MEMU_MEM_BASE,
  };
  syscall_reset_program(memu);
  memu->state = MEMU_STATE_RUNNING;
  printf("MEMU: loaded fs program %s, %u bytes at 0x%08x\n",
         path, file->size, MEMU_MEM_BASE);
  return true;
}

uint32_t fs_open(MEMUFS *fs, const char *path) {
  int idx = find_file(fs, path);
  if (idx < 0) {
    return UINT32_MAX;
  }

  for (uint32_t fd = FS_STD_FD_BASE; fd < MEMU_FS_MAX_OPEN; fd++) {
    MEMUOpenFile *open = &fs->open_files[fd];
    if (!open->used) {
      *open = (MEMUOpenFile){
        .used = true,
        .file_index = idx,
        .open_offset = 0,
      };
      return fd;
    }
  }
  return UINT32_MAX;
}

static MEMUOpenFile *get_open(MEMUFS *fs, uint32_t fd) {
  if (fd < FS_STD_FD_BASE || fd >= MEMU_FS_MAX_OPEN) {
    return NULL;
  }
  MEMUOpenFile *open = &fs->open_files[fd];
  return open->used ? open : NULL;
}

uint32_t fs_read(MEMUFS *fs, uint32_t fd, uint32_t guest_buf, uint32_t len) {
  MEMUOpenFile *open = get_open(fs, fd);
  if (open == NULL) {
    return UINT32_MAX;
  }

  MEMUFileInfo *file = &fs->files[open->file_index];
  if (file->kind == MEMU_FILE_DEV_EVENTS) {
    uint32_t event = device_read_key_event();
    const char *key = device_key_name(event);
    if (key == NULL) {
      return 0;
    }
    char line[32];
    snprintf(line, sizeof(line), "%s %s\n",
             (event & MEMU_KEYDOWN_MASK) ? "kd" : "ku", key);
    return guest_write_string(guest_buf, line, len);
  }

  if (file->kind == MEMU_FILE_DEV_SBCTL) {
    if (len < 4) {
      return 0;
    }
    uint32_t available = device_audio_query();
    uint8_t bytes[4] = {
      (uint8_t)available,
      (uint8_t)(available >> 8),
      (uint8_t)(available >> 16),
      (uint8_t)(available >> 24),
    };
    guest_write_bytes(guest_buf, bytes, sizeof(bytes));
    return sizeof(bytes);
  }

  if (file->kind == MEMU_FILE_DEV_SB) {
    return UINT32_MAX;
  }

  if (open->open_offset >= file->size) {
    return 0;
  }

  uint32_t avail = file->size - open->open_offset;
  uint32_t actual = len < avail ? len : avail;
  switch (file->kind) {
    case MEMU_FILE_RAMDISK:
      guest_write_bytes(guest_buf,
                        fs->ramdisk.data + file->disk_offset + open->open_offset,
                        actual);
      break;
    case MEMU_FILE_PROC_DISPINFO:
      guest_write_bytes(guest_buf,
                        (const uint8_t *)FS_PROC_DISPINFO + open->open_offset,
                        actual);
      break;
    case MEMU_FILE_DEV_EVENTS:
      return 0;
    case MEMU_FILE_DEV_FB:
    case MEMU_FILE_DEV_SBCTL:
    case MEMU_FILE_DEV_SB:
      return UINT32_MAX;
  }

  open->open_offset += actual;
  return actual;
}

uint32_t fs_write(MEMUFS *fs, uint32_t fd, uint32_t guest_buf, uint32_t len) {
  MEMUOpenFile *open = get_open(fs, fd);
  if (open == NULL) {
    return UINT32_MAX;
  }

  MEMUFileInfo *file = &fs->files[open->file_index];
  if (file->kind == MEMU_FILE_DEV_SBCTL) {
    if (len < 12) {
      return UINT32_MAX;
    }
    uint32_t config[3] = {0, 0, 0};
    for (uint32_t i = 0; i < 12; i++) {
      config[i / 4u] |= mem_read(guest_buf + i, 1) << ((i % 4u) * 8u);
    }
    device_audio_configure(config[0], config[1], config[2]);
    return 12;
  }

  if (file->kind == MEMU_FILE_DEV_SB) {
    uint8_t chunk[1024];
    uint32_t done = 0;
    while (done < len) {
      uint32_t chunk_len = len - done;
      if (chunk_len > sizeof(chunk)) {
        chunk_len = sizeof(chunk);
      }
      for (uint32_t i = 0; i < chunk_len; i++) {
        chunk[i] = (uint8_t)mem_read(guest_buf + done + i, 1);
      }
      uint32_t written = device_audio_play(chunk, chunk_len);
      done += written;
      if (written != chunk_len) {
        break;
      }
    }
    return done;
  }

  if (file->kind == MEMU_FILE_DEV_FB) {
    uint32_t actual = len;
    if (open->open_offset >= MEMU_FB_SIZE) {
      return 0;
    }
    if (actual > MEMU_FB_SIZE - open->open_offset) {
      actual = MEMU_FB_SIZE - open->open_offset;
    }
    for (uint32_t i = 0; i < actual; i++) {
      mem_write(MEMU_FB_ADDR + open->open_offset + i, 1, mem_read(guest_buf + i, 1));
    }
    open->open_offset += actual;
    return actual;
  }

  return UINT32_MAX;
}

uint32_t fs_lseek(MEMUFS *fs, uint32_t fd, int32_t offset, uint32_t whence) {
  MEMUOpenFile *open = get_open(fs, fd);
  if (open == NULL) {
    return UINT32_MAX;
  }

  const MEMUFileInfo *file = &fs->files[open->file_index];
  int64_t base = 0;
  if (whence == 0) {
    base = 0;
  } else if (whence == 1) {
    base = open->open_offset;
  } else if (whence == 2) {
    base = file->size;
  } else {
    return UINT32_MAX;
  }

  int64_t next = base + offset;
  if (next < 0 || next > (int64_t)file->size) {
    return UINT32_MAX;
  }

  open->open_offset = (uint32_t)next;
  return open->open_offset;
}

uint32_t fs_close(MEMUFS *fs, uint32_t fd) {
  MEMUOpenFile *open = get_open(fs, fd);
  if (open == NULL) {
    return UINT32_MAX;
  }
  memset(open, 0, sizeof(*open));
  return 0;
}
