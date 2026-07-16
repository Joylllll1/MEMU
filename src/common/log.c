#include "memu/common.h"

#include <stdarg.h>

void memu_panic(const char *file, int line, const char *fmt, ...) {
  fprintf(stderr, "MEMU panic at %s:%d: ", file, line);

  va_list ap;
  va_start(ap, fmt);
  vfprintf(stderr, fmt, ap);
  va_end(ap);

  fputc('\n', stderr);
  exit(1);
}
