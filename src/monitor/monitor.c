#include "memu/monitor.h"

#include "memu/expr.h"
#include "memu/memory.h"
#include "memu/watchpoint.h"

#include <ctype.h>
#include <limits.h>
#include <string.h>

typedef struct Monitor Monitor;
typedef int (*CommandHandler)(Monitor *monitor, char *args);

typedef struct {
  const char *name;
  const char *description;
  CommandHandler handler;
} Command;

struct Monitor {
  MEMU *memu;
};

static int cmd_help(Monitor *monitor, char *args);
static int cmd_q(Monitor *monitor, char *args);
static int cmd_c(Monitor *monitor, char *args);
static int cmd_si(Monitor *monitor, char *args);
static int cmd_info(Monitor *monitor, char *args);
static int cmd_x(Monitor *monitor, char *args);
static int cmd_p(Monitor *monitor, char *args);
static int cmd_w(Monitor *monitor, char *args);
static int cmd_d(Monitor *monitor, char *args);

static const Command commands[] = {
  {"help", "Display command help", cmd_help},
  {"q", "Quit monitor", cmd_q},
  {"c", "Continue execution", cmd_c},
  {"si", "Step N instructions, default 1", cmd_si},
  {"info", "Display registers or watchpoints: info r | info w", cmd_info},
  {"x", "Scan memory: x N EXPR", cmd_x},
  {"p", "Evaluate expression: p EXPR", cmd_p},
  {"w", "Set watchpoint: w EXPR", cmd_w},
  {"d", "Delete watchpoint: d N", cmd_d},
};

static char *skip_spaces(char *s) {
  while (*s != '\0' && isspace((unsigned char)*s)) {
    s++;
  }
  return s;
}

static void rstrip(char *s) {
  size_t len = strlen(s);
  while (len > 0 && isspace((unsigned char)s[len - 1])) {
    s[--len] = '\0';
  }
}

static bool parse_u64_arg(const char *s, uint64_t *value) {
  char *end = NULL;
  unsigned long long parsed = strtoull(s, &end, 0);
  if (end == s) {
    return false;
  }
  while (*end != '\0') {
    if (!isspace((unsigned char)*end)) {
      return false;
    }
    end++;
  }
  *value = (uint64_t)parsed;
  return true;
}

static bool is_guest_running(const MEMU *memu) {
  return memu->state == MEMU_STATE_RUNNING;
}

static int cmd_help(Monitor *monitor, char *args) {
  (void)monitor;
  args = skip_spaces(args);
  if (*args == '\0') {
    for (size_t i = 0; i < MEMU_ARRAY_LEN(commands); i++) {
      printf("%-8s %s\n", commands[i].name, commands[i].description);
    }
    return 0;
  }

  for (size_t i = 0; i < MEMU_ARRAY_LEN(commands); i++) {
    if (strcmp(args, commands[i].name) == 0) {
      printf("%-8s %s\n", commands[i].name, commands[i].description);
      return 0;
    }
  }

  printf("Unknown command: %s\n", args);
  return 0;
}

static int cmd_q(Monitor *monitor, char *args) {
  (void)monitor;
  (void)args;
  return 1;
}

static int cmd_c(Monitor *monitor, char *args) {
  (void)args;
  if (!is_guest_running(monitor->memu)) {
    puts("Program is not running");
    return 0;
  }
  cpu_exec(monitor->memu, UINT64_MAX);
  return 0;
}

static int cmd_si(Monitor *monitor, char *args) {
  if (!is_guest_running(monitor->memu)) {
    puts("Program is not running");
    return 0;
  }

  args = skip_spaces(args);
  uint64_t n = 1;
  if (*args != '\0' && !parse_u64_arg(args, &n)) {
    puts("Usage: si [N]");
    return 0;
  }

  if (n == 0) {
    puts("si 0: no instruction executed");
    return 0;
  }

  cpu_exec(monitor->memu, n);
  return 0;
}

static int cmd_info(Monitor *monitor, char *args) {
  args = skip_spaces(args);
  if (strcmp(args, "r") == 0) {
    cpu_dump_regs(&monitor->memu->cpu);
  } else if (strcmp(args, "w") == 0) {
    watchpoint_display();
  } else {
    puts("Usage: info r | info w");
  }
  return 0;
}

static int cmd_x(Monitor *monitor, char *args) {
  args = skip_spaces(args);
  if (*args == '\0') {
    puts("Usage: x N EXPR");
    return 0;
  }

  char *n_str = args;
  while (*args != '\0' && !isspace((unsigned char)*args)) {
    args++;
  }
  if (*args != '\0') {
    *args++ = '\0';
  }
  args = skip_spaces(args);

  uint64_t n = 0;
  if (!parse_u64_arg(n_str, &n) || n > UINT32_MAX || *args == '\0') {
    puts("Usage: x N EXPR");
    return 0;
  }

  bool success = false;
  uint32_t addr = expr_eval(monitor->memu, args, &success);
  if (!success) {
    printf("Bad expression: %s\n", args);
    return 0;
  }

  for (uint64_t i = 0; i < n; i++) {
    uint32_t cur = addr + (uint32_t)(i * 4u);
    printf("0x%08x: 0x%08x\n", cur, mem_read(cur, 4));
  }
  return 0;
}

static int cmd_p(Monitor *monitor, char *args) {
  args = skip_spaces(args);
  if (*args == '\0') {
    puts("Usage: p EXPR");
    return 0;
  }

  bool success = false;
  uint32_t value = expr_eval(monitor->memu, args, &success);
  if (!success) {
    printf("Bad expression: %s\n", args);
    return 0;
  }

  printf("%u (0x%08x)\n", value, value);
  return 0;
}

static int cmd_w(Monitor *monitor, char *args) {
  watchpoint_set(monitor->memu, args);
  return 0;
}

static int cmd_d(Monitor *monitor, char *args) {
  (void)monitor;
  args = skip_spaces(args);
  uint64_t id = 0;
  if (*args == '\0' || !parse_u64_arg(args, &id) || id > INT_MAX) {
    puts("Usage: d N");
    return 0;
  }

  watchpoint_delete((int)id);
  return 0;
}

static int handle_command(Monitor *monitor, char *line) {
  rstrip(line);
  char *cmd = skip_spaces(line);
  if (*cmd == '\0') {
    return 0;
  }

  char *args = cmd;
  while (*args != '\0' && !isspace((unsigned char)*args)) {
    args++;
  }
  if (*args != '\0') {
    *args++ = '\0';
  }
  args = skip_spaces(args);

  for (size_t i = 0; i < MEMU_ARRAY_LEN(commands); i++) {
    if (strcmp(cmd, commands[i].name) == 0) {
      return commands[i].handler(monitor, args);
    }
  }

  printf("Unknown command: %s\n", cmd);
  return 0;
}

void monitor_mainloop(MEMU *memu) {
  Monitor monitor = {
    .memu = memu,
  };
  char line[256];

  while (true) {
    printf("(memu) ");
    fflush(stdout);

    if (fgets(line, sizeof(line), stdin) == NULL) {
      putchar('\n');
      break;
    }

    if (handle_command(&monitor, line) != 0) {
      break;
    }
  }
}
