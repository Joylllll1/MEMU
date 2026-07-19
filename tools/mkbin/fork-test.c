#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>

static void run_child(void) {
  char *argv[] = {"/bin/vfork-child", NULL};
  execve(argv[0], argv, NULL);
  puts("fork-test: exec-failed");
  _exit(2);
}

int main(void) {
  puts("fork-test: parent-before");

  pid_t first = fork();
  if (first == 0) run_child();
  if (first < 0) {
    puts("fork-test: first-fork-failed");
    return 1;
  }
  printf("fork-test: parent-after-first pid=%d\n", (int)first);

  pid_t second = fork();
  if (second == 0) run_child();
  if (second < 0) {
    puts("fork-test: second-fork-failed");
    return 1;
  }
  printf("fork-test: parent-after-second pid=%d\n", (int)second);

  pid_t waited_first = wait(NULL);
  pid_t waited_second = wait(NULL);
  printf("fork-test: waited=%d,%d\n", (int)waited_first, (int)waited_second);
  return 0;
}
