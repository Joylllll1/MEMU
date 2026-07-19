#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>

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
  int status = -1;
  pid_t waited = wait(&status);
  printf("vfork-test: waited pid=%d status=%d\n", (int)waited, status);
  return 0;
}
