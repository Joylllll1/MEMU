# Chapter 7: 系统调用与批处理系统

## 7.1 从裸机程序到最小 OS

目前 guest 程序直接运行在 MEMU 模拟的硬件上。它可以计算、访问设备、最后 `ebreak`。这种程序叫裸机程序。

但真实应用通常不是这样运行的。应用会请求操作系统帮它输出、退出、读文件、申请内存。请求 OS 服务的机制就是系统调用。

本章要实现一个最小批处理系统：

```text
mini OS 启动
加载 user program A
A 调用 write 输出
A 调用 exit
mini OS 加载 user program B
B 调用 write 输出
B 调用 exit
所有程序结束，good trap
```

## 7.2 本章结束时应该看到什么

运行：

```sh
./build/memu --kernel tests/images/batch-os.elf --batch
```

或简化命令：

```sh
./build/memu --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
```

预期输出：

```text
program A
program B
HIT GOOD TRAP
```

具体 CLI 可以根据实现选择，但核心行为必须是：一个程序结束后，系统加载下一个程序。

## 7.3 本章新增模块

```text
include/
  memu/
    syscall.h
    batch.h
src/
  os/
    syscall.c
    batch.c
guest/
  lib/
    syscall.h
    syscall.c
tests/
  user/
    prog_a.c
    prog_b.c
```

如果你还没有 RISC-V C 工具链，可以先用手写汇编或机器码模拟 `ecall`。

## 7.4 第一件事：区分 `ecall` 和 `ebreak`

RV32I system 指令中：

```text
ecall  = 0x00000073
ebreak = 0x00100073
```

在 Chapter 5 中，`ebreak` 用于 MEMU trap。现在加入：

```text
ecall -> syscall path
```

第一版 `ecall` 不做特权级切换，不模拟完整 CSR，只是让 MEMU 调用 syscall handler。

这是教学简化。真实 RISC-V 会涉及 privilege mode、`mcause`、`mepc`、`mtvec` 等机制，后续再讨论。

### Checkpoint 1

写一个 guest 程序执行 `ecall`。如果 syscall number 未知，MEMU 应打印：

```text
unknown syscall: ...
```

并 bad trap 或 abort，而不是当作非法指令。

## 7.5 第二件事：固定 syscall ABI

采用常见 RISC-V ABI：

```text
a7: syscall number
a0-a5: arguments
a0: return value
```

定义最小 syscall：

```text
SYS_exit  = 93
SYS_write = 64
SYS_brk   = 214
```

这些编号参考 Linux RISC-V 常用编号，但 MEMU 可以只实现语义子集。

## 7.6 第三件事：guest 侧 syscall wrapper

guest 代码里不要每次手写寄存器。写：

```c
long syscall3(long n, long a0, long a1, long a2);
void exit(int code);
int write(int fd, const void *buf, int len);
```

RISC-V 内联汇编大致需要：

```c
register long r_a7 asm("a7") = n;
register long r_a0 asm("a0") = a0;
...
asm volatile("ecall" : "+r"(r_a0) : "r"(r_a7), ... : "memory");
```

如果还没引入 C 工具链，可以暂时用汇编测试程序设置 `a7/a0/a1/a2` 后执行 `ecall`。

## 7.7 第四件事：实现 `SYS_write`

只支持：

```text
fd = 1 stdout
fd = 2 stderr
```

参数：

```text
a0 = fd
a1 = guest buffer address
a2 = len
```

handler 做：

```text
从 guest memory 逐字节读取 buffer
写到 host stdout/stderr
返回实际写入长度
```

注意：`a1` 是 guest address，不是 host pointer。

### Checkpoint 2

guest 调用：

```c
write(1, "hello\n", 6);
```

预期 host 终端输出：

```text
hello
```

如果崩溃，优先检查是否直接把 guest address 当指针。

## 7.8 第五件事：实现 `SYS_exit`

参数：

```text
a0 = exit code
```

但在批处理系统中，用户程序 exit 不应该直接结束 MEMU。它应该通知 batch runtime：

```text
当前 user program 结束
加载下一个 user program
```

如果没有更多程序：

```text
MEMU good trap
```

如果 exit code 非 0：

```text
MEMU bad trap
```

## 7.9 第六件事：`SYS_brk`

很多 C 程序或简易 libc 会调用 `brk`。第一版可以非常简单：

```text
如果 a0 == 0，返回当前 program break
否则设置 program break = a0 并返回 0
```

也可以先 stub：

```text
总是返回 0
```

但如果后续用户程序使用 malloc，stub 可能不够。

## 7.10 第七件事：batch runtime

设计一个 batch state：

```c
typedef struct {
  const char *programs[16];
  int count;
  int current;
} BatchState;
```

流程：

```text
batch_load_current()
cpu_exec()
on SYS_exit:
  if code != 0 -> bad trap
  current++
  if current == count -> good trap
  else load next program and continue
```

### 加载地址问题

第一版可以让每个 user program 都加载到 `MEMU_MEM_BASE`，因为它们顺序执行，不同时存在。

这就是批处理系统和多道程序的区别：批处理一次只需要一个 user program 在内存里。

## 7.11 Checkpoint 3：两个程序顺序运行

准备两个程序：

```text
prog-a: write stdout "program A\n"; exit(0)
prog-b: write stdout "program B\n"; exit(0)
```

运行 batch：

```sh
./build/memu --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
```

预期：

```text
program A
program B
HIT GOOD TRAP
```

如果只输出 A，说明 `SYS_exit` 没有加载下一个程序。

如果 A 一直重复，说明 current index 没有推进，或 PC 没重置。

## 7.12 第八件事：OS 和 user 的边界

本章的 OS 可能主要在 host 侧由 MEMU 实现。这是教学简化。

后续可以把更多 OS 逻辑放入 guest kernel ELF 中，但初期目标是理解：

```text
user ecall -> syscall handler -> OS 决策 -> 返回 user 或加载下一个
```

不要一开始做完整 RISC-V privilege。

## 7.13 调试路线

### ecall 后 PC 不动

`ecall` 应该消费当前指令。处理完后通常让 PC 指向下一条，除非加载了新程序并重置 PC。

### write 输出乱码

检查 guest buffer 地址、长度和 guest memory 读取。

### exit 后继续执行用户程序

检查 syscall handler 是否通知 batch runtime 停止当前程序。

### batch 第二个程序不运行

检查 loader 是否重置 memory、PC 和必要寄存器。

## 7.14 必答题

1. `ecall` 和 `ebreak` 在 MEMU 中分别表示什么？
2. 为什么 user `exit` 不应该直接结束 MEMU？
3. syscall 参数为什么放在寄存器里，而不是 host stack？
4. 批处理系统为什么可以复用同一个加载地址？
5. 本章没有做用户态/内核态隔离，会带来什么简化和局限？

## 7.15 给 LLM 的提示

建议分任务：

```text
1. 在 system 指令中区分 ecall/ebreak。
2. 实现 syscall ABI 和 unknown syscall 报错。
3. 实现 SYS_write。
4. 实现 SYS_exit 和 batch-list。
5. 实现两个 user 程序测试。
```

不要让 LLM 引入完整 privilege、CSR 或虚存。那是后续章节。

## 7.16 本章完成标准

必须通过：

```sh
./build/memu --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
```

并看到：

```text
program A
program B
HIT GOOD TRAP
```

通过后进入 Chapter 8。下一章会把 user program 和数据组织成文件系统。

## 7.17 NEMU PA3 起步对齐

本章对应 NEMU PA3 的前半段：Nanos-lite、loader、syscall 和批处理。

你可以先用 MEMU 自己的 mini OS 理解控制流，但最终要对齐 Nanos-lite 的运行方式。对齐时，关注的是接口和行为，不是复制 Nanos-lite 的源码。

### 第一层：syscall ABI

RISC-V 常见约定：

```text
a7: syscall number
a0-a5: arguments
a0: return value
```

在 MEMU 中记录每次 syscall：

```text
[syscall] pc=0x... no=SYS_write a0=1 a1=0x... a2=6 -> 6
```

这个日志很重要。PA3 的错误经常不是“完全不能跑”，而是某个 syscall 返回值差一点，导致上层库误判。

### 第二层：最小用户程序

先不要跑复杂应用。准备一个用户程序，只做：

```c
int main(void) {
  write(1, "hello\n", 6);
  exit(0);
}
```

验收：

```text
Nanos-lite boot...
hello
user program exited with code 0
HIT GOOD TRAP
```

如果这里失败，优先检查：

- `ecall` 之后 PC 是否前进。
- `a7/a0/a1/a2` 是否读对。
- guest buffer 地址是否通过 guest memory 读取。
- `write` 返回值是否是实际写入字节数。

### 第三层：brk 和堆

很多程序即使看起来没有显式 malloc，也可能在 libc 初始化中碰到 `brk`。

第一版 `brk` 可以简单，但不能无脑返回 0：

```text
heap_start <= new_brk <= heap_end -> success
otherwise -> fail
```

建议日志：

```text
[syscall] brk request=0x... old=0x... new=0x... result=0
```

如果你还没有真实堆，可以先给每个用户程序一段固定 heap 区间，并在文档中标注这是教学简化。

### 第四层：批处理列表

用两个程序做测试：

```text
/bin/hello
/bin/bye
```

输出应该是：

```text
hello
bye
HIT GOOD TRAP
```

如果第二个程序不运行，问题通常在：

- `SYS_exit` 没有回到 OS。
- loader 没有重置 PC。
- 新程序加载时没有清理旧程序的 `.bss` 或栈。
- batch index 没有推进。

## 7.18 本章 NEMU 对齐完成标准

Stage 6 / Chapter 7 完成时，至少要有：

- `ecall` 和 `ebreak` 分清。
- `SYS_exit`、`SYS_write`、`SYS_brk` 可用。
- syscall trace 默认可开关。
- 一个 Nanos-lite 风格最小用户程序可运行。
- 两个用户程序可以由 batch runtime 顺序运行。
- unknown syscall 会明确报错，而不是继续乱跑。

不要在本章引入完整虚存、真实特权级和复杂进程。PA3 前半段的重点是 syscall 和 loader 的控制流。
