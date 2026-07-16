# Chapter 9: 多道程序、虚存与中断

## 9.1 这一章为什么难

前面所有章节都可以把系统看成“一个程序占有整台机器”。即使有批处理系统，也是一段程序结束后再加载下一段。

本章开始，多件事情会同时存在：

- 内存里有多个进程。
- 每个进程有自己的寄存器状态。
- 每个进程有自己的栈。
- 进程可能看到相同虚拟地址。
- timer interrupt 可以打断当前执行流。

这就是从批处理走向多任务系统的关键。

本章不要追求完整真实 OS。目标是教学版多道程序、简化虚存和定时器中断。

## 9.2 本章结束时应该看到什么

你应该能运行：

```sh
./build/memu --kernel tests/images/mp-os.elf --batch
```

并看到类似：

```text
ABABABAB
vm test passed
timer preempt test passed
HIT GOOD TRAP
```

其中：

- A/B 来自两个进程交替输出。
- vm test 证明相同虚拟地址映射到不同物理页。
- timer preempt 证明不主动 yield 的进程也能被切走。

## 9.3 本章新增模块

```text
include/
  memu/
    proc.h
    mmu.h
    interrupt.h
src/
  os/
    proc.c
    schedule.c
    mmu.c
    interrupt.c
tests/
  user/
    yield_a.c
    yield_b.c
    vm_a.c
    vm_b.c
```

## 9.4 第一件事：进程和上下文

上下文就是一个进程继续运行所需的状态。第一版可以直接复用 `CPUState`：

```c
typedef struct {
  int pid;
  enum {
    PROC_UNUSED,
    PROC_RUNNABLE,
    PROC_RUNNING,
    PROC_EXITED,
  } state;
  CPUState context;
  uint8_t stack[STACK_SIZE];
} PCB;
```

全局：

```c
PCB pcb[MAX_PROC];
PCB *current;
```

### Checkpoint 1

创建两个 PCB，但只运行第一个。确认旧的 batch/user 程序仍能运行。

## 9.5 第二件事：cooperative yield

先实现主动切换，不做中断。

新增 syscall：

```text
SYS_yield
```

流程：

```text
user A 调用 yield
ecall 进入 handler
保存 A 的 CPUState 到 A 的 PCB
选择 B
从 B 的 PCB 恢复 CPUState
返回 guest 执行 B
```

这里“返回 guest 执行 B”听起来神奇，其实只是把全局 `cpu` 替换成 B 的 context，然后继续 `cpu_exec()`。

### Checkpoint 2

两个用户程序：

```text
A: putch('A'); yield(); repeat
B: putch('B'); yield(); repeat
```

预期输出：

```text
ABABAB
```

如果只输出 A，scheduler 没切换。

如果输出 A 后崩溃，可能是 B 的 PC 或栈没初始化。

## 9.6 第三件事：每个进程独立栈

即使还没有虚存，也必须给每个进程独立栈。

创建进程时：

```text
context.pc = entry
context.gpr[sp] = stack_top_guest_address
```

这里要小心：`pcb.stack` 是 host 数组，不等于 guest 栈地址。如果你的用户程序运行在 guest memory 中，它的 `sp` 必须是 guest address。

一种简化：

```text
为每个进程在 guest physical memory 中分配一段栈
proc0 stack: 0x81000000 - 0x8100ffff
proc1 stack: 0x81010000 - 0x8101ffff
```

不要把 host pointer 塞进 guest `sp`。

## 9.7 第四件事：没有虚存前的多进程加载

在加入虚存前，先把不同进程加载到不同物理地址：

```text
proc0 text: 0x80000000
proc1 text: 0x80100000
proc2 text: 0x80200000
```

这是临时方案。它的缺点是：程序必须知道自己被链接到哪里，或者必须是位置无关代码。

本小节目标是先让 scheduler 跑通。

## 9.8 第五件事：地址空间和页表

虚存要解决的问题是：多个程序可以看到相同虚拟地址，但映射到不同物理内存。

定义：

```c
typedef struct {
  uint32_t va;
  uint32_t pa;
  uint32_t size;
  uint32_t flags;
} PageMap;

typedef struct {
  PageMap maps[128];
  int count;
} AddressSpace;
```

先用线性查表，不做真实 RISC-V Sv32。

地址翻译：

```text
vaddr -> find PageMap -> paddr -> guest_to_host(paddr)
```

把 `mem_read/mem_write` 改造成：

```text
如果启用虚存:
  vaddr -> paddr
普通物理访存:
  paddr -> pmem
```

## 9.9 第六件事：每个进程独立 AddressSpace

PCB 增加：

```c
AddressSpace as;
```

进程切换时：

```text
current = next
active address space = &next->as
cpu = next->context
```

### Checkpoint 3：相同虚拟地址

准备两个进程，它们都访问虚拟地址：

```text
0x80400000
```

但映射：

```text
proc A: 0x80400000 -> physical page P1
proc B: 0x80400000 -> physical page P2
```

A 写 0x11111111，B 写 0x22222222。切换回来后 A 仍应读到 0x11111111。

如果 A 读到 B 的值，说明地址空间没切换或映射冲突。

## 9.10 第七件事：page fault

如果访问没有映射的虚拟地址，MEMU 不应该随便访问物理内存。打印：

```text
page fault: vaddr=..., pc=..., access=read/write
```

然后 bad trap 或 abort。

这会让虚存 bug 更容易定位。

## 9.11 第八件事：timer interrupt

cooperative yield 依赖程序主动让出 CPU。如果某个程序死循环，系统无法切换。

先用指令计数模拟 timer：

```text
每执行 N 条 guest 指令，触发 timer interrupt
```

流程：

```text
cpu_exec loop 中计数
到达 interval
设置 interrupt pending
进入 interrupt handler
scheduler 选择下一个进程
```

第一版不模拟完整 CSR，只记录 cause：

```text
TRAP_TIMER
```

## 9.12 Checkpoint 4：抢占测试

两个程序：

```text
A: while (1) putch('A');
B: while (1) putch('B');
```

如果没有 timer，只会输出 A。打开 timer 后，应该看到 A 和 B 都出现。

输出不一定严格 `ABAB`，但不能只有一个字符。

## 9.13 第九件事：进程退出和回收

`SYS_exit` 在多进程系统中：

```text
current->state = PROC_EXITED
schedule next runnable
如果没有 runnable -> good trap
```

不要再像 batch 那样简单加载下一个覆盖当前内存。多进程系统里其它进程仍在内存中。

第一版可以不真正释放物理页，只标记进程退出。后续再做资源回收。

## 9.14 调试路线

### 切换后寄存器乱了

检查 context 是否保存/恢复完整。尤其是 `pc`、`sp`、`ra` 和 `a0-a7`。

### yield 后回到错误位置

检查 `ecall` 后保存的 PC。通常应该保存下一条指令地址，而不是 `ecall` 自己，否则会重复 yield。

### 虚存测试互相覆盖

检查 active address space 是否随 current 进程切换。

### page fault 地址奇怪

检查 guest virtual address 和 physical address 是否混用。

### timer interrupt 太频繁

先把 interval 调大，比如每 1000 条指令一次。太频繁会让日志难读。

## 9.15 必答题

1. 上下文切换最少需要保存哪些状态？
2. 为什么每个进程必须有独立栈？
3. 没有虚存时，多进程加载为什么麻烦？
4. 虚拟地址、物理地址、host pointer 三者有什么区别？
5. cooperative yield 和 timer preemption 的区别是什么？
6. timer interrupt 为什么不能依赖程序主动调用 syscall？

## 9.16 给 LLM 的提示

建议分任务：

```text
1. 实现 PCB 和单进程运行，不改变旧行为。
2. 实现 SYS_yield 和 cooperative scheduler。
3. 给每个进程分配独立 guest stack。
4. 实现简化 AddressSpace 和地址翻译。
5. 实现 page fault 报错。
6. 实现 instruction-count timer interrupt。
```

不要让 LLM 一开始实现真实 RISC-V Sv32、完整 CSR、权限级和 TLB。教学版先跑通概念。

## 9.17 本章完成标准

必须通过：

```text
两个 yield 进程交替输出
两个进程相同虚拟地址不互相覆盖
未映射地址触发 page fault
timer 打开后不主动 yield 的进程也能被切换
所有进程 exit 后 good trap
```

完成本章后，MEMU 已经走完从最小计算机到教学版多任务系统的主线。后续可以继续扩展：difftest、性能优化、图形 demo、真实 RISC-V privilege、Sv32 页表和更完整的 OS。

## 9.18 NEMU PA4 对齐路线

PA4 的目标不是把系统变复杂，而是让多个程序在同一台机器上合理共存。对齐 NEMU 时，建议按三个层次推进：

```text
cooperative yield
virtual memory
timer interrupt preemption
```

每一层都要保证 PA3 应用不回退。

### 第一层：yield-os

先实现最小上下文切换：

```text
process A: print A, yield
process B: print B, yield
```

期望：

```text
ABABAB...
```

输出不必严格交替，但不能只有一个进程。

上下文至少包含：

```text
pc
gpr[32]
address_space pointer or id
```

如果切换后 `ra`、`sp` 或 `a0` 错了，很多 bug 会表现成随机跳转。先把上下文 dump 做好：

```text
[ctx-save] pid=1 pc=0x... sp=0x... ra=0x...
[ctx-load] pid=2 pc=0x... sp=0x... ra=0x...
```

### 第二层：虚存

教学版可以先不实现真实 Sv32 页表，但必须严格区分三种地址：

```text
guest virtual address
guest physical address
host pointer
```

建议先写一个简化页表：

```text
vpn -> ppn + permission
```

然后让两个进程都使用：

```text
virtual 0x80400000
```

但映射到不同物理页。测试方式：

```text
process A writes 0xaaaaaaaa to virtual X
process B writes 0xbbbbbbbb to virtual X
switch back to A
A still reads 0xaaaaaaaa
```

如果这个测试失败，说明 active address space 没有随进程切换，或者地址翻译绕过了页表。

### 第三层：timer interrupt

cooperative yield 依赖程序主动让出 CPU。timer interrupt 要验证：

```text
process A: while (1) print A
process B: while (1) print B
```

打开 timer 后，输出里必须同时出现 A 和 B。

第一版 timer interrupt 可以按指令数触发：

```text
every 1000 guest instructions -> interrupt
```

这样更可复现。真实时间 timer 可以之后补。

### PA3 回归

每完成 PA4 一层，都跑一遍 PA3 回归：

```text
Nanos-lite hello
file read app
NDL draw app
NSlider
PAL current known state
```

PA4 很容易破坏 loader、syscall 或地址翻译。如果 `yield-os` 通过但 NSlider 坏了，不能算 PA4 完成。

## 9.19 本章 NEMU 对齐完成标准

Chapter 9 完成时，至少满足：

- `yield-os` 或同等级测试通过。
- 两个进程有独立 guest stack。
- context dump 可以定位切换前后的状态。
- 简化虚存能让相同 virtual address 映射到不同 physical page。
- 未映射地址触发 page fault，并打印 fault address。
- timer interrupt 可以抢占不主动 yield 的程序。
- Stage 7 的 Navy 小程序仍可运行。
- PAL/仙剑目标状态没有因为 PA4 回退。

这一章结束后，MEMU 的教学主线完成。后面进入的是兼容性收口：把更多 NEMU PA 真实 artifact 加入回归，补齐性能、设备、库函数和长期稳定性。
