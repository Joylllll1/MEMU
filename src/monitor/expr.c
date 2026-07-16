#include "memu/expr.h"

#include "memu/memory.h"

#include <ctype.h>
#include <string.h>

enum {
  TK_NUM = 256,
  TK_REG,
  TK_EQ,
  TK_NEQ,
  TK_AND,
  TK_DEREF,
  TK_NEG,
};

typedef struct {
  int type;
  char str[64];
} Token;

static Token tokens[128];
static int nr_token;

static bool is_operator(int type) {
  return type == '+' || type == '-' || type == '*' || type == '/' ||
         type == TK_EQ || type == TK_NEQ || type == TK_AND ||
         type == TK_DEREF || type == TK_NEG;
}

static bool push_token(int type, const char *start, size_t len) {
  if (nr_token >= (int)MEMU_ARRAY_LEN(tokens) || len >= sizeof(tokens[0].str)) {
    return false;
  }

  tokens[nr_token].type = type;
  memcpy(tokens[nr_token].str, start, len);
  tokens[nr_token].str[len] = '\0';
  nr_token++;
  return true;
}

static bool make_tokens(const char *s) {
  nr_token = 0;

  for (size_t i = 0; s[i] != '\0';) {
    if (isspace((unsigned char)s[i])) {
      i++;
      continue;
    }

    if (s[i] == '0' && (s[i + 1] == 'x' || s[i + 1] == 'X')) {
      size_t start = i;
      i += 2;
      while (isxdigit((unsigned char)s[i])) {
        i++;
      }
      if (i == start + 2 || !push_token(TK_NUM, s + start, i - start)) {
        return false;
      }
      continue;
    }

    if (isdigit((unsigned char)s[i])) {
      size_t start = i;
      while (isdigit((unsigned char)s[i])) {
        i++;
      }
      if (!push_token(TK_NUM, s + start, i - start)) {
        return false;
      }
      continue;
    }

    if (s[i] == '$') {
      size_t start = ++i;
      while (isalnum((unsigned char)s[i]) || s[i] == '_') {
        i++;
      }
      if (i == start || !push_token(TK_REG, s + start, i - start)) {
        return false;
      }
      continue;
    }

    if (s[i] == '=' && s[i + 1] == '=') {
      if (!push_token(TK_EQ, s + i, 2)) {
        return false;
      }
      i += 2;
      continue;
    }

    if (s[i] == '!' && s[i + 1] == '=') {
      if (!push_token(TK_NEQ, s + i, 2)) {
        return false;
      }
      i += 2;
      continue;
    }

    if (s[i] == '&' && s[i + 1] == '&') {
      if (!push_token(TK_AND, s + i, 2)) {
        return false;
      }
      i += 2;
      continue;
    }

    if (strchr("+-*/()", s[i]) != NULL) {
      if (!push_token((unsigned char)s[i], s + i, 1)) {
        return false;
      }
      i++;
      continue;
    }

    return false;
  }

  for (int i = 0; i < nr_token; i++) {
    int prev = (i == 0) ? 0 : tokens[i - 1].type;
    bool unary = (i == 0 || prev == '(' || is_operator(prev));
    if (tokens[i].type == '*' && unary) {
      tokens[i].type = TK_DEREF;
    } else if (tokens[i].type == '-' && unary) {
      tokens[i].type = TK_NEG;
    }
  }

  return true;
}

static bool check_parentheses(int l, int r) {
  if (tokens[l].type != '(' || tokens[r].type != ')') {
    return false;
  }

  int depth = 0;
  for (int i = l; i <= r; i++) {
    if (tokens[i].type == '(') {
      depth++;
    } else if (tokens[i].type == ')') {
      depth--;
      if (depth == 0 && i < r) {
        return false;
      }
      if (depth < 0) {
        return false;
      }
    }
  }
  return depth == 0;
}

static int precedence(int type) {
  switch (type) {
    case TK_AND:
      return 1;
    case TK_EQ:
    case TK_NEQ:
      return 2;
    case '+':
    case '-':
      return 3;
    case '*':
    case '/':
      return 4;
    case TK_DEREF:
    case TK_NEG:
      return 5;
    default:
      return 0;
  }
}

static int find_main_op(int l, int r) {
  int depth = 0;
  int op = -1;
  int best_prec = 100;

  for (int i = r; i >= l; i--) {
    if (tokens[i].type == ')') {
      depth++;
      continue;
    }
    if (tokens[i].type == '(') {
      depth--;
      continue;
    }
    if (depth != 0) {
      continue;
    }

    int prec = precedence(tokens[i].type);
    if (prec > 0 &&
        (prec < best_prec ||
         (prec == best_prec &&
          (tokens[i].type == TK_DEREF || tokens[i].type == TK_NEG)))) {
      best_prec = prec;
      op = i;
    }
  }

  return op;
}

static uint32_t eval_range(MEMU *memu, int l, int r, bool *success) {
  if (l > r) {
    *success = false;
    return 0;
  }

  if (l == r) {
    if (tokens[l].type == TK_NUM) {
      char *end = NULL;
      unsigned long value = strtoul(tokens[l].str, &end, 0);
      if (*end != '\0') {
        *success = false;
        return 0;
      }
      return (uint32_t)value;
    }

    if (tokens[l].type == TK_REG) {
      return cpu_reg_str2val(&memu->cpu, tokens[l].str, success);
    }

    *success = false;
    return 0;
  }

  if (check_parentheses(l, r)) {
    return eval_range(memu, l + 1, r - 1, success);
  }

  int op = find_main_op(l, r);
  if (op < 0) {
    *success = false;
    return 0;
  }

  if (tokens[op].type == TK_DEREF || tokens[op].type == TK_NEG) {
    if (op != l) {
      *success = false;
      return 0;
    }
    uint32_t val = eval_range(memu, op + 1, r, success);
    if (!*success) {
      return 0;
    }
    if (tokens[op].type == TK_DEREF) {
      return mem_read(val, 4);
    }
    return (uint32_t)(-(int32_t)val);
  }

  uint32_t lhs = eval_range(memu, l, op - 1, success);
  if (!*success) {
    return 0;
  }
  uint32_t rhs = eval_range(memu, op + 1, r, success);
  if (!*success) {
    return 0;
  }

  switch (tokens[op].type) {
    case '+':
      return lhs + rhs;
    case '-':
      return lhs - rhs;
    case '*':
      return lhs * rhs;
    case '/':
      if (rhs == 0) {
        *success = false;
        return 0;
      }
      return lhs / rhs;
    case TK_EQ:
      return lhs == rhs;
    case TK_NEQ:
      return lhs != rhs;
    case TK_AND:
      return (lhs != 0) && (rhs != 0);
    default:
      *success = false;
      return 0;
  }
}

uint32_t expr_eval(MEMU *memu, const char *s, bool *success) {
  *success = false;
  if (s == NULL || *s == '\0' || !make_tokens(s) || nr_token == 0) {
    return 0;
  }

  bool ok = true;
  uint32_t value = eval_range(memu, 0, nr_token - 1, &ok);
  *success = ok;
  return ok ? value : 0;
}
