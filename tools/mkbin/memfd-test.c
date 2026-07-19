#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

int main(void) {
  int fd = memfd_create("memu-test", 0);
  if (fd < 0 || ftruncate(fd, 4096) != 0) {
    puts("memfd-test: create-failed");
    return 1;
  }
  uint32_t *shared = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  if (shared == MAP_FAILED) {
    puts("memfd-test: mmap-failed");
    return 1;
  }
  shared[0] = 0x12345678u;
  shared[1] = 0x9abcdef0u;
  printf("memfd-test: values=%x,%x\n", shared[0], shared[1]);
  munmap(shared, 4096);
  close(fd);
  return 0;
}
