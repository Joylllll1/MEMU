#include "memu/loader.h"

#include "memu/memory.h"

#include <errno.h>
#include <string.h>

#define EI_NIDENT 16
#define PT_LOAD UINT32_C(1)
#define ET_EXEC UINT16_C(2)
#define EM_RISCV UINT16_C(243)

typedef struct {
  unsigned char e_ident[EI_NIDENT];
  uint16_t e_type;
  uint16_t e_machine;
  uint32_t e_version;
  uint32_t e_entry;
  uint32_t e_phoff;
  uint32_t e_shoff;
  uint32_t e_flags;
  uint16_t e_ehsize;
  uint16_t e_phentsize;
  uint16_t e_phnum;
  uint16_t e_shentsize;
  uint16_t e_shnum;
  uint16_t e_shstrndx;
} Elf32Ehdr;

typedef struct {
  uint32_t p_type;
  uint32_t p_offset;
  uint32_t p_vaddr;
  uint32_t p_paddr;
  uint32_t p_filesz;
  uint32_t p_memsz;
  uint32_t p_flags;
  uint32_t p_align;
} Elf32Phdr;

bool load_image(const char *path, uint32_t load_addr, uint32_t *entry) {
  FILE *fp = fopen(path, "rb");
  MEMU_ASSERT(fp != NULL, "failed to open image '%s': %s", path, strerror(errno));

  MEMU_ASSERT(mem_in_range(load_addr, 1),
              "image load address out of range: 0x%08x", load_addr);

  uint8_t *dst = guest_to_host(load_addr);
  size_t cap = MEMU_MEM_SIZE - ((uint64_t)load_addr - MEMU_MEM_BASE);
  size_t nread = fread(dst, 1, cap, fp);

  MEMU_ASSERT(ferror(fp) == 0, "failed to read image '%s'", path);

  int extra = fgetc(fp);
  MEMU_ASSERT(extra == EOF, "image '%s' is too large for guest memory", path);

  fclose(fp);

  if (entry != NULL) {
    *entry = load_addr;
  }

  printf("MEMU: loaded %s, %zu bytes at 0x%08x\n", path, nread, load_addr);
  return true;
}

static void read_exact(FILE *fp, void *buf, size_t size, const char *what, const char *path) {
  MEMU_ASSERT(fread(buf, 1, size, fp) == size, "failed to read %s from '%s'", what, path);
}

bool load_elf(const char *path, uint32_t *entry) {
  FILE *fp = fopen(path, "rb");
  MEMU_ASSERT(fp != NULL, "failed to open ELF '%s': %s", path, strerror(errno));

  Elf32Ehdr ehdr;
  read_exact(fp, &ehdr, sizeof(ehdr), "ELF header", path);

  MEMU_ASSERT(ehdr.e_ident[0] == 0x7f && ehdr.e_ident[1] == 'E' &&
              ehdr.e_ident[2] == 'L' && ehdr.e_ident[3] == 'F',
              "'%s' is not an ELF file", path);
  MEMU_ASSERT(ehdr.e_ident[4] == 1, "'%s' is not ELF32", path);
  MEMU_ASSERT(ehdr.e_ident[5] == 1, "'%s' is not little-endian ELF", path);
  MEMU_ASSERT(ehdr.e_type == ET_EXEC, "'%s' is not ET_EXEC", path);
  MEMU_ASSERT(ehdr.e_machine == EM_RISCV, "'%s' is not RISC-V ELF", path);
  MEMU_ASSERT(ehdr.e_phentsize == sizeof(Elf32Phdr),
              "'%s' has unsupported program header size %u", path, ehdr.e_phentsize);

  size_t loaded_segments = 0;
  for (uint16_t i = 0; i < ehdr.e_phnum; i++) {
    uint64_t phoff = (uint64_t)ehdr.e_phoff + (uint64_t)i * ehdr.e_phentsize;
    MEMU_ASSERT(fseek(fp, (long)phoff, SEEK_SET) == 0,
                "failed to seek program header %u in '%s'", i, path);

    Elf32Phdr phdr;
    read_exact(fp, &phdr, sizeof(phdr), "program header", path);
    if (phdr.p_type != PT_LOAD) {
      continue;
    }

    MEMU_ASSERT(phdr.p_memsz >= phdr.p_filesz,
                "ELF segment memsz < filesz in '%s'", path);
    if (phdr.p_memsz == 0) {
      continue;
    }
    MEMU_ASSERT(mem_in_range(phdr.p_vaddr, phdr.p_memsz),
                "ELF segment out of guest memory: vaddr=0x%08x memsz=%u",
                phdr.p_vaddr, phdr.p_memsz);

    uint8_t *dst = guest_to_host(phdr.p_vaddr);
    MEMU_ASSERT(fseek(fp, (long)phdr.p_offset, SEEK_SET) == 0,
                "failed to seek segment data in '%s'", path);
    read_exact(fp, dst, phdr.p_filesz, "segment data", path);
    memset(dst + phdr.p_filesz, 0, phdr.p_memsz - phdr.p_filesz);
    loaded_segments++;
  }

  fclose(fp);
  MEMU_ASSERT(loaded_segments > 0, "ELF '%s' has no PT_LOAD segments", path);
  MEMU_ASSERT(mem_in_range(ehdr.e_entry, 1),
              "ELF entry out of guest memory: 0x%08x", ehdr.e_entry);

  if (entry != NULL) {
    *entry = ehdr.e_entry;
  }
  printf("MEMU: loaded ELF %s, entry=0x%08x, segments=%zu\n",
         path, ehdr.e_entry, loaded_segments);
  return true;
}
