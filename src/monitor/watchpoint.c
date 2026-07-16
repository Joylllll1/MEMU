#include "memu/watchpoint.h"

#include "memu/expr.h"

#include <string.h>

#define NR_WP 32

typedef struct {
  int id;
  bool used;
  char expr[128];
  uint32_t last_value;
} Watchpoint;

static Watchpoint watchpoints[NR_WP];

static const char *skip_spaces(const char *s) {
  while (*s == ' ' || *s == '\t') {
    s++;
  }
  return s;
}

void watchpoint_init(void) {
  for (int i = 0; i < NR_WP; i++) {
    watchpoints[i] = (Watchpoint){
      .id = i + 1,
      .used = false,
      .expr = "",
      .last_value = 0,
    };
  }
}

int watchpoint_set(MEMU *memu, const char *expr) {
  expr = skip_spaces(expr == NULL ? "" : expr);
  if (*expr == '\0') {
    puts("Usage: w EXPR");
    return -1;
  }

  bool success = false;
  uint32_t value = expr_eval(memu, expr, &success);
  if (!success) {
    printf("Bad expression: %s\n", expr);
    return -1;
  }

  for (int i = 0; i < NR_WP; i++) {
    if (!watchpoints[i].used) {
      watchpoints[i].used = true;
      watchpoints[i].last_value = value;
      snprintf(watchpoints[i].expr, sizeof(watchpoints[i].expr), "%s", expr);
      printf("Watchpoint %d: %s = 0x%08x\n",
             watchpoints[i].id, watchpoints[i].expr, value);
      return watchpoints[i].id;
    }
  }

  puts("No free watchpoints");
  return -1;
}

bool watchpoint_delete(int id) {
  for (int i = 0; i < NR_WP; i++) {
    if (watchpoints[i].used && watchpoints[i].id == id) {
      watchpoints[i].used = false;
      printf("Deleted watchpoint %d\n", id);
      return true;
    }
  }

  printf("No watchpoint %d\n", id);
  return false;
}

bool watchpoint_check(MEMU *memu) {
  for (int i = 0; i < NR_WP; i++) {
    if (!watchpoints[i].used) {
      continue;
    }

    bool success = false;
    uint32_t value = expr_eval(memu, watchpoints[i].expr, &success);
    if (!success) {
      printf("Watchpoint %d expression failed: %s\n",
             watchpoints[i].id, watchpoints[i].expr);
      return true;
    }

    if (value != watchpoints[i].last_value) {
      printf("Watchpoint %d triggered\n", watchpoints[i].id);
      printf("expr: %s\n", watchpoints[i].expr);
      printf("old value = 0x%08x\n", watchpoints[i].last_value);
      printf("new value = 0x%08x\n", value);
      watchpoints[i].last_value = value;
      return true;
    }
  }

  return false;
}

void watchpoint_display(void) {
  bool any = false;
  for (int i = 0; i < NR_WP; i++) {
    if (watchpoints[i].used) {
      printf("%d: %s = 0x%08x\n",
             watchpoints[i].id, watchpoints[i].expr, watchpoints[i].last_value);
      any = true;
    }
  }

  if (!any) {
    puts("No watchpoints");
  }
}
