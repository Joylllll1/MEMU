#include <stdio.h>
#include <unistd.h>

int pipe2(int pipefd[2], int flags);

int main(void) {
  int pipefd[2];
  char buf[64];

  int probe[2];
  if (pipe2(probe, 0) < 0) {
    puts("fd-test: pipe2-failed");
    return 1;
  }
  close(probe[0]);
  close(probe[1]);

  if (pipe(pipefd) < 0) {
    puts("fd-test: pipe-failed");
    return 1;
  }

  const char first[] = "fd-test: pipe-data\n";
  write(pipefd[1], first, sizeof(first) - 1);
  int n = read(pipefd[0], buf, sizeof(buf));
  if (n <= 0) {
    puts("fd-test: pipe-read-failed");
    return 1;
  }
  write(1, buf, (size_t)n);

  int saved_stdout = dup(1);
  if (saved_stdout < 0 || dup2(pipefd[1], 1) != 1) {
    puts("fd-test: dup-failed");
    return 1;
  }
  const char redirected[] = "fd-test: dup2-data\n";
  write(1, redirected, sizeof(redirected) - 1);
  if (dup2(saved_stdout, 1) != 1) {
    return 1;
  }
  close(saved_stdout);

  n = read(pipefd[0], buf, sizeof(buf));
  if (n <= 0) {
    puts("fd-test: redirected-read-failed");
    return 1;
  }
  write(1, buf, (size_t)n);
  close(pipefd[0]);
  close(pipefd[1]);
  puts("fd-test: PASS");
  return 0;
}
