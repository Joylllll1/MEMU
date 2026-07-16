# Chapter 3: 实现简易调试器

## 3.1 为什么现在要做调试器

在 Chapter 2 中，MEMU 已经能执行一个非常短的 guest 程序。你可能会觉得下一步应该马上实现更多 RV32I 指令。但如果现在直接冲进完整指令集，你很快会遇到一个问题：程序跑错时，你不知道 guest 机器内部发生了什么。

GDB 可以调试 `memu` 这个 host program，但它不会自动理解 guest 的 PC、guest 的寄存器、guest 的内存。比如你想知道：

```text
guest 的 pc 现在是多少？
guest 的 a0 为什么变成了 1？
guest memory 0x80000000 处是什么指令？
哪一条 guest 指令第一次改坏了 sp？
```

这些问题需要 MEMU 自己提供观察手段。这个观察手段就是简易调试器，也可以叫 monitor。

本章结束时，你应该可以运行：

```sh
./build/memu --image tests/images/stage1-trap.bin
```

然后在提示符里输入：

```text
(memu) info r
(memu) si
(memu) p $a1
(memu) x 3 0x80000000
(memu) w $a1
(memu) c
```

并看到寄存器、内存和表达式求值的结果。

## 3.2 本章新增模块

新增：

```text
include/
  memu/
    monitor.h
    expr.h
    watchpoint.h
src/
  monitor/
    monitor.c
    expr.c
    watchpoint.c
tests/
  smoke/
    run_monitor_commands.sh
```

模块职责：

- `monitor.c`：命令行交互、命令解析、调用 CPU 执行。
- `expr.c`：把表达式字符串转成值。
- `watchpoint.c`：保存和检查监视点。

注意：monitor 是 host 侧工具，不是 guest 硬件的一部分。它可以访问 MEMU 内部的 CPUState 和 memory，但不要把 monitor 逻辑写进 CPU 指令执行里。

## 3.3 第一步：进入 monitor

Chapter 2 中，`--batch` 表示直接运行到结束。现在我们约定：

- 有 `--batch`：加载 image 后直接 `cpu_exec(UINT64_MAX)`。
- 没有 `--batch`：加载 image 后进入 monitor。

在 `include/memu/monitor.h` 中声明：

```c
#ifndef MEMU_MONITOR_H
#define MEMU_MONITOR_H

void monitor_mainloop(void);

#endif
```

在 `src/monitor/monitor.c` 中写第一版：

```c
void monitor_mainloop(void) {
  char line[256];

  while (true) {
    printf("(memu) ");
    fflush(stdout);

    if (fgets(line, sizeof(line), stdin) == NULL) {
      putchar('\n');
      break;
    }

    handle_command(line);
  }
}
```

macOS 上先使用 `fgets()`。不要急着引入 GNU readline，因为 macOS 自带的是 libedit，行为和 GNU readline 并不完全一样。等 monitor 功能稳定后再增强交互体验。

### Checkpoint 1

运行：

```sh
./build/memu --image tests/images/stage1-trap.bin
```

预期看到：

```text
(memu)
```

输入空行不崩溃。输入 Ctrl-D 可以退出。

如果没有进入 monitor，而是直接运行到 `HIT GOOD TRAP`，检查 `--batch` 判断是否写反了。

## 3.4 第二步：命令表

不要用一堆 `if (strcmp(...))` 把命令逻辑散落在 `handle_command()` 里。建议仿照很多 debugger 的写法，用命令表。

```c
typedef int (*CommandHandler)(char *args);

typedef struct {
  const char *name;
  const char *description;
  CommandHandler handler;
} Command;
```

第一批命令：

```text
help
q
c
si
info
x
p
w
d
```

`handle_command()` 做三件事：

1. 去掉行尾换行。
2. 切出命令名和参数。
3. 在命令表中查找并调用 handler。

推荐规则：

```text
命令名 = 第一个非空白 token
args = 命令名之后的剩余字符串，可以为空
```

这样 `p $a0 + 1` 的参数能保留完整表达式，而不会被空格切碎。

### Checkpoint 2

先实现 `help` 和 `q`。

运行：

```text
(memu) help
(memu) help si
(memu) q
```

预期：

- `help` 列出所有命令。
- `help si` 打印 `si` 的说明。
- `q` 退出 monitor。
- 未知命令打印错误，不退出 MEMU。

## 3.5 第三步：`c` 和 `si`

`c` 表示 continue，直接运行到 guest 停机、abort 或 watchpoint 命中：

```c
static int cmd_c(char *args) {
  (void)args;
  cpu_exec(UINT64_MAX);
  return 0;
}
```

`si` 表示 step instruction：

```text
si       执行 1 条指令
si 10    执行 10 条指令
```

解析 `N` 时要处理：

- 没有参数：默认 1。
- 参数不是数字：报错。
- N 为 0：可以什么都不做并提示。

### Checkpoint 3

运行：

```text
(memu) si
(memu) si 2
(memu) c
```

如果 guest 已经执行到 `ebreak`，再次 `si` 或 `c` 应该提示程序已经结束，而不是继续从 trap 后面的垃圾内存取指。

## 3.6 第四步：`info r`

现在你需要观察 guest registers。

`info` 是一个二级命令：

```text
info r    打印寄存器
info w    打印 watchpoints，后面实现
```

先实现 `info r`。

建议输出：

```text
pc   0x80000004
zero 0x00000000
ra   0x00000000
sp   0x00000000
...
a0   0x00000000
a1   0x0000002a
```

`cpu_dump()` 可以放在 `cpu.c` 中，monitor 只负责调用它。这样未来 batch 模式出错时也可以复用同一份寄存器打印逻辑。

### Checkpoint 4

运行：

```text
(memu) info r
(memu) si
(memu) info r
```

如果第一条 guest 指令是：

```asm
addi a1, zero, 42
```

那么第二次 `info r` 应该看到：

```text
a1 0x0000002a
```

如果 `a1` 没变，先不要继续写表达式。回到 Chapter 2 查 `addi`。

## 3.7 第五步：`x N EXPR`

`x` 用来扫描 guest memory。它的形式是：

```text
x N EXPR
```

含义：

- 先计算表达式 `EXPR` 得到起始地址。
- 从这个地址开始，以 4 字节为单位打印 N 个 word。

第一版可以只支持：

```text
x 3 0x80000000
```

输出：

```text
0x80000000: 0x02a00593
0x80000004: 0x00000513
0x80000008: 0x00100073
```

### 实现提示

`x` 的参数解析要小心。第一个 token 是 N，剩下全部是表达式。

伪代码：

```c
char *n_str = strtok(args, " ");
char *expr_str = args_after_n;
```

不要把 `expr_str` 再用空格切碎，因为后面会支持：

```text
x 4 $pc + 8
```

### Checkpoint 5

运行：

```text
(memu) x 3 0x80000000
```

确认输出的三条机器码和 `xxd tests/images/stage1-trap.bin` 一致，只是显示顺序是 32-bit word。

## 3.8 第六步：表达式求值的最小版本

现在开始实现 `expr.c`。不要一开始就追求完整 C 表达式。先支持：

- 十进制整数：`42`
- 十六进制整数：`0x2a`
- 寄存器：`$pc`、`$a0`、`$a1`

接口：

```c
uint32_t expr_eval(const char *s, bool *success);
```

先实现简单规则：

```text
如果以 0x 开头 -> strtoul base 16
如果以数字开头 -> strtoul base 10
如果以 $ 开头 -> 查寄存器
否则失败
```

寄存器查询建议放在 CPU 模块：

```c
uint32_t cpu_reg_str2val(const char *name, bool *success);
```

这样表达式模块不需要知道寄存器数组的细节。

### Checkpoint 6

实现 `p EXPR`：

```text
(memu) p 42
42 (0x0000002a)
(memu) p 0x80000000
2147483648 (0x80000000)
(memu) p $pc
2147483648 (0x80000000)
```

同时让 `x` 改用 `expr_eval()`，于是：

```text
(memu) x 3 $pc
```

应该能工作。

## 3.9 第七步：tokenizer

接下来支持算术表达式。先把字符串分解成 tokens。

支持 token：

```text
decimal number
hex number
register
+
-
*
/
(
)
==
!=
&&
whitespace
```

每个 token 保存：

```c
typedef struct {
  int type;
  char str[64];
} Token;
```

最大 token 数可以先固定为 128。超出时报错。

### 为什么要 tokenizer

表达式字符串里没有天然边界。例如：

```text
0x80000000+($a0+5)*4
```

你不能只用空格切分。tokenizer 的任务是识别“有意义的最小单元”。

### Checkpoint 7

给 tokenizer 加一个临时 debug 开关，输入：

```text
p 0x80000000 + ($a0 + 5) * 4
```

应识别为：

```text
HEX + ( REG + DEC ) * DEC
```

如果 token 顺序不对，先修 tokenizer，不要写递归求值。

## 3.10 第八步：递归求值

表达式求值可以按归纳定义写：

```text
expr ::= number
       | register
       | '(' expr ')'
       | expr '+' expr
       | expr '-' expr
       | expr '*' expr
       | expr '/' expr
       | expr '==' expr
       | expr '!=' expr
       | expr '&&' expr
```

实现步骤：

1. 检查 token 区间 `[l, r]` 是否被一对完整括号包住。
2. 如果是，递归计算内部。
3. 否则找到主运算符。
4. 递归计算左右两边。
5. 合并结果。

### 主运算符

主运算符是当前表达式最后被计算的运算符。例如：

```text
1 + 2 * 3
```

主运算符是 `+`，因为乘法优先级更高，先算 `2 * 3`。

扫描时要忽略括号内部的运算符。

优先级从低到高：

```text
&&
== !=
+ -
* /
unary
```

### Checkpoint 8

运行：

```text
(memu) p 1 + 2 * 3
7 (0x00000007)
(memu) p (1 + 2) * 3
9 (0x00000009)
(memu) p 1 + 2 == 3
1 (0x00000001)
(memu) p 1 + 2 == 4
0 (0x00000000)
```

## 3.11 第九步：指针解引用

调试时经常需要查看某个 guest 地址里的值：

```text
p *0x80000000
```

这里的 `*` 不是乘法，而是解引用。

判断规则：

如果 `*` 出现在表达式开头，或者前一个 token 是：

```text
( + - * / == != &&
```

那么这个 `*` 是一元解引用。

把它转换成 token 类型 `TK_DEREF`，求值时：

```c
value = mem_read(expr_value, 4);
```

### Checkpoint 9

运行：

```text
(memu) p *0x80000000
```

预期得到第一条指令：

```text
0x02a00593
```

如果得到字节反转值，问题在 memory endian。

## 3.12 第十步：watchpoint

watchpoint 的功能是：当某个表达式的值发生变化时，自动停止。

例如：

```text
(memu) w $a1
(memu) c
```

当 `$a1` 从 0 变成 42 时，MEMU 应该停下来并打印：

```text
Watchpoint 1 triggered
expr: $a1
old value = 0x00000000
new value = 0x0000002a
```

### 数据结构

```c
#define NR_WP 32

typedef struct {
  int id;
  bool used;
  char expr[128];
  uint32_t last_value;
} Watchpoint;
```

接口：

```c
void watchpoint_init(void);
int watchpoint_set(const char *expr);
bool watchpoint_delete(int id);
bool watchpoint_check(void);
void watchpoint_display(void);
```

`watchpoint_check()` 在每条指令执行后调用。如果发现变化，返回 true，让 `cpu_exec()` 停下来。

### Checkpoint 10

运行：

```text
(memu) w $a1
(memu) c
```

预期：执行第一条 `addi a1, zero, 42` 后停止，而不是一直跑到 `ebreak`。

然后：

```text
(memu) info w
(memu) d 1
(memu) info w
```

应能看到 watchpoint 被删除。

## 3.13 自动化 monitor 测试

交互式程序也可以做 smoke test。创建：

```text
tests/smoke/run_monitor_commands.sh
```

用 here document 或管道输入：

```sh
#!/usr/bin/env sh
set -eu

memu="$1"
image="$2"

"$memu" --image "$image" <<'EOF'
info r
si
p $a1
x 3 0x80000000
q
EOF
```

注意：这个脚本只是 smoke test，不要求精确匹配所有输出。后续可以逐渐增强为 golden output 测试。

## 3.14 调试路线

### monitor 无法退出

检查 `q` handler 是否返回一个特殊值，让 mainloop break。

### `si` 后寄存器不变

先确认 `cpu_exec(1)` 是否真的执行了一条指令。可以临时打印 PC before/after。

### `p $a1` 失败

检查寄存器名字表是否支持 ABI 名字。`a1` 是 x11。

### `x 3 $pc` 崩溃

检查表达式求值是否成功，以及 `mem_read()` 是否对越界地址调用 `panic`。

### watchpoint 不触发

确认每条指令后调用了 `watchpoint_check()`。如果只在 `cpu_exec()` 结束后检查，就会错过变化点。

## 3.15 必答题

请回答：

1. 为什么 GDB 不能完全替代 MEMU monitor？
2. `x` 命令为什么要接表达式，而不是只接数字地址？
3. `*` 作为乘法和解引用时，如何区分？
4. watchpoint 应该在指令执行前检查，还是执行后检查？为什么？
5. 如果表达式求值失败，monitor 应该继续运行还是退出 MEMU？

## 3.16 给 LLM 的提示

让 LLM 实现本章时，建议分成四次：

```text
1. 只实现 monitor mainloop、help、q、c、si、info r。
2. 只实现 x、p 和最小 expr：数字、十六进制、寄存器。
3. 扩展 expr tokenizer 和递归求值，支持 + - * / == != && ()。
4. 实现 dereference 和 watchpoint。
```

每次都要求它运行当前 checkpoint。不要让它一次性写完整 debugger。

## 3.17 本章完成标准

以下交互必须可用：

```text
(memu) help
(memu) info r
(memu) si
(memu) p 1 + 2 * 3
(memu) p $a1
(memu) x 3 0x80000000
(memu) p *0x80000000
(memu) w $a1
(memu) c
(memu) d 1
(memu) q
```

通过后再进入 Chapter 4。下一章会大量增加指令，如果没有本章的可观测性，调试会非常痛苦。
