#include <stdio.h>
#include <unistd.h>

int main(void) {
  puts("vfork-test: parent-before");
  pid_t pid = vfork();
  if (pid == 0) {
    char *argv[] = {"/bin/vfork-child", NULL};
    execve("/bin/vfork-child", argv, NULL);
    puts("vfork-test: exec-failed");
    _exit(2);
  }
  printf("vfork-test: parent-after pid=%d\n", (int)pid);
  return 0;
}
