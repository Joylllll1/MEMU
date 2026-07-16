# Chapter 2: 实现最小计算机 TRM

## 2.1 从现在开始创造一台计算机

本章对应 Stage 1。你将第一次让 MEMU 执行 guest 指令。

到本章结束时，MEMU 应该能加载一个 raw binary，执行：

```asm
addi a0, zero, 42
ebreak
```

然后打印类似：

```text
HIT GOOD TRAP
pc = 0x80000004
a0 = 0x0000002a
```

这看起来非常小，但它已经包含了一台计算机最核心的循环：

```text
从 PC 指向的内存取出指令
解释这条指令
修改机器状态
更新 PC
继续下一条
```

## 2.2 本章要新增的模块

从 Chapter 1 的项目骨架继续，新增：

```text
include/
  memu/
    cpu.h
    memory.h
    loader.h
src/
  cpu/
    cpu.c
    decode.c
  memory/
    memory.c
  loader/
    image.c
tests/
  images/
  smoke/
    run_stage1.sh
tools/
  mkbin/
    stage1_addi.py 或 stage1_addi.c
```

如果你暂时不想引入 Python，可以用一个小 C 工具或 shell 的 `printf` 生成二进制。但要注意：用 shell 写二进制在不同系统上容易踩转义坑，因此建议后续用小 C 工具或专门脚本。

## 2.3 第一件事：定义 guest memory

真实计算机有内存。MEMU 也需要一段数组来模拟内存。

建议在 `include/memu/memory.h` 中声明：

```c
#ifndef MEMU_MEMORY_H
#define MEMU_MEMORY_H

#include "memu/common.h"

#define MEMU_MEM_BASE 0x80000000u
#define MEMU_MEM_SIZE (128u * 1024u * 1024u)

void mem_init(void);
uint32_t mem_read(uint32_t addr, int len);
void mem_write(uint32_t addr, int len, uint32_t data);
uint8_t *guest_to_host(uint32_t addr);
bool mem_in_range(uint32_t addr, uint32_t len);

#endif
```

在 `src/memory/memory.c` 中实现：

```c
static uint8_t pmem[MEMU_MEM_SIZE];
```

### 地址转换

guest 程序看到的地址从 `0x80000000` 开始。但 `pmem` 是 host program 里的数组。你不能直接把 `0x80000000` 当指针用。

正确转换是：

```text
guest addr 0x80000000 -> pmem[0]
guest addr 0x80000004 -> pmem[4]
```

因此：

```c
uint8_t *guest_to_host(uint32_t addr) {
  if (!mem_in_range(addr, 1)) {
    MEMU_PANIC("address out of range: 0x%08x", addr);
  }
  return &pmem[addr - MEMU_MEM_BASE];
}
```

### 访存长度

`mem_read()` 和 `mem_write()` 先支持长度 1、2、4。RISC-V 是 little endian，所以：

```text
pmem[offset + 0] 是最低 8 位
pmem[offset + 1] 是次低 8 位
```

实现时不要用强制类型转换：

```c
*(uint32_t *)guest_to_host(addr)
```

这样可能引入未对齐访问和宿主字节序问题。教学项目里先手动拼字节，更清楚。

### Checkpoint 1：内存读写

临时写一个测试，或在 `mem_init()` 后手动调用：

```c
mem_write(MEMU_MEM_BASE, 4, 0x12345678);
printf("0x%08x\n", mem_read(MEMU_MEM_BASE, 4));
```

预期：

```text
0x12345678
```

再测试：

```c
mem_write(MEMU_MEM_BASE + 1, 1, 0xaa);
```

确认只修改一个字节。

## 2.4 第二件事：定义 CPUState

在 `include/memu/cpu.h` 中定义：

```c
#ifndef MEMU_CPU_H
#define MEMU_CPU_H

#include "memu/common.h"

typedef struct {
  uint32_t gpr[32];
  uint32_t pc;
} CPUState;

extern CPUState cpu;

void cpu_reset(uint32_t entry);
void cpu_exec(uint64_t n);
void cpu_dump(void);
const char *cpu_reg_name(int idx);

#endif
```

### 为什么是 32 个寄存器

RV32I 有 32 个整数寄存器，编号 x0 到 x31。其中 x0 很特殊，永远读出 0，写入会被丢弃。

建议在 `cpu.c` 中放寄存器名字：

```c
static const char *reg_names[32] = {
  "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
  "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
  "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
  "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
};
```

### `cpu_reset()`

reset 做两件事：

```text
寄存器清零
pc = entry
```

注意：entry 对 raw binary 来说就是 `MEMU_MEM_BASE`。

### Checkpoint 2：reset

临时打印：

```text
pc = 0x80000000
zero = 0
a0 = 0
```

如果 PC 不是 `0x80000000`，先不要继续。

## 2.5 第三件事：取指

取指就是从 `cpu.pc` 指向的位置读 4 字节：

```c
static uint32_t inst_fetch(uint32_t pc) {
  return mem_read(pc, 4);
}
```

在 RV32I 基础指令里，指令长度固定 4 字节。后续如果支持压缩指令 C 扩展，才会遇到 2 字节指令。现在不要支持压缩指令。

### Checkpoint 3：取出机器码

把以下 4 个字节写入 `MEMU_MEM_BASE`：

```text
13 05 a0 02
```

它们按 little endian 组成：

```text
0x02a00513
```

这条指令是：

```asm
addi a0, zero, 42
```

取指应得到：

```text
inst = 0x02a00513
```

如果得到 `0x1305a002` 或别的值，说明字节序错了。

## 2.6 第四件事：最小执行循环

CPU 的执行循环放在 `src/cpu/cpu.c`：

```c
typedef enum {
  MEMU_RUNNING,
  MEMU_STOPPED,
  MEMU_END,
  MEMU_ABORT,
} MEMUState;
```

本章至少需要区分：

- running：正在运行。
- end：执行到 trap，正常结束。
- abort：遇到非法指令或内存错误。

执行循环：

```c
void cpu_exec(uint64_t n) {
  if (state is ended) return;
  state = running;
  while (n-- > 0 && state == running) {
    uint32_t pc = cpu.pc;
    uint32_t inst = inst_fetch(pc);
    decode_exec(inst);
    cpu.gpr[0] = 0;
  }
}
```

这里 `decode_exec()` 会执行一条指令并更新 PC。

## 2.7 第五件事：译码 `addi`

先只实现一条真正会修改寄存器的指令：`addi`。

机器码格式是 I-type：

```text
31      20 19   15 14  12 11    7 6      0
imm[11:0] rs1     funct3 rd       opcode
```

`addi` 的条件：

```text
opcode = 0x13
funct3 = 0x0
```

语义：

```text
rd = rs1 + sign_extend(imm12)
pc = pc + 4
```

### 需要的 helper

```c
static uint32_t bits(uint32_t x, int hi, int lo);
static int32_t sign_extend(uint32_t x, int bits);
```

`sign_extend(0xfff, 12)` 应该得到 `-1`。

### Checkpoint 4：执行 addi

加载 `0x02a00513`，执行一条指令：

```text
pc before = 0x80000000
inst      = 0x02a00513
pc after  = 0x80000004
a0        = 42
```

如果 `a0` 不等于 42，检查：

- rd 是否取成 bits 11..7。
- rs1 是否取成 bits 19..15。
- imm 是否取成 bits 31..20。
- x0 是否保持为 0。

## 2.8 第六件事：实现 `ebreak`

本章用 `ebreak` 表示 guest 程序结束。

`ebreak` 机器码：

```text
0x00100073
```

执行到 `ebreak` 时：

- 不再继续执行下一条指令。
- 根据 `a0` 判断 good/bad trap。
- 打印 PC 和关键寄存器。

建议约定：

```text
a0 == 42 暂时也认为是 good trap，用于 Stage 1 演示
Stage 4 开始改成 a0 == 0 表示 good trap
```

或者从一开始就采用：

```text
a0 == 0 good
a0 != 0 bad
```

如果采用后一种，那么 Stage 1 测试程序应改为：

```asm
addi a0, zero, 0
ebreak
```

本手册建议从一开始采用 `a0 == 0`，因为后续测试更一致。若想同时展示计算结果，可以使用 `a1 = 42`。

## 2.9 第七件事：生成第一个 guest binary

我们需要一个 raw binary，内容是两条指令：

```asm
addi a1, zero, 42
addi a0, zero, 0
ebreak
```

它们会：

- 把计算结果 42 放到 `a1`。
- 把退出码 0 放到 `a0`。
- 执行 `ebreak`。

早期可以手写机器码，放到 `tests/images/stage1-trap.bin`。

推荐写一个小工具生成它，而不是把二进制文件手工提交。工具可以输出 little endian 32-bit word。

伪代码：

```c
write_u32_le(0x02a00593); // addi a1, zero, 42
write_u32_le(0x00000513); // addi a0, zero, 0
write_u32_le(0x00100073); // ebreak
```

### Checkpoint 5：检查二进制字节

用 macOS 自带工具：

```sh
xxd tests/images/stage1-trap.bin
```

应该看到每条指令按 little endian 排列。例如 `0x00100073` 会显示为：

```text
73 00 10 00
```

## 2.10 第八件事：raw image loader

在 `include/memu/loader.h` 声明：

```c
bool load_image(const char *path, uint32_t load_addr, uint32_t *entry);
```

第一版 loader：

```text
打开文件
检查文件大小不超过 MEM_SIZE
读入到 guest memory load_addr
entry = load_addr
```

注意：读入目标地址必须是：

```c
guest_to_host(load_addr)
```

不要把 `load_addr` 当 host pointer。

### Checkpoint 6：加载 image

运行：

```sh
./build/memu --image tests/images/stage1-trap.bin --batch
```

你现在需要扩展 Chapter 1 的 CLI，支持：

```text
--image FILE
--batch
```

`--batch` 表示不进入 monitor，直接运行到结束。

## 2.11 第九件事：把 main 接起来

`main()` 的流程变成：

```text
parse args
mem_init()
load_image(image, MEMU_MEM_BASE, &entry)
cpu_reset(entry)
if batch:
  cpu_exec(UINT64_MAX)
else:
  暂时也 cpu_exec(UINT64_MAX)，monitor 下一章再做
print final state
return good/bad status
```

此时你会第一次拥有“能执行其它程序的程序”。

## 2.12 预期输出

运行：

```sh
./build/memu --image tests/images/stage1-trap.bin --batch
```

预期输出可以类似：

```text
MEMU: loaded tests/images/stage1-trap.bin at 0x80000000
MEMU: HIT GOOD TRAP at pc=0x80000008
pc  0x80000008
a0  0x00000000
a1  0x0000002a
```

PC 到底打印 `ebreak` 的地址还是下一条地址，要在代码中固定。建议打印 trap 指令所在 PC，这样更容易定位。

## 2.13 调试路线

如果运行结果不对，按这个顺序查：

### 1. image 是否正确加载

在 loader 后打印前 12 字节：

```text
0x80000000: 0x02a00593
0x80000004: 0x00000513
0x80000008: 0x00100073
```

如果这里不对，问题在生成 binary 或 loader。

### 2. 取指是否正确

第一条取指必须得到：

```text
0x02a00593
```

如果字节反了，问题在 `mem_read()`。

### 3. addi 译码是否正确

对 `0x02a00593`：

```text
opcode = 0x13
rd = 11
rs1 = 0
imm = 42
```

如果 rd 不是 11，检查 bit helper。

### 4. x0 是否保持为 0

每条指令后强制：

```c
cpu.gpr[0] = 0;
```

### 5. ebreak 是否停机

如果执行到 `0x00100073` 后继续跑，说明 state 没切换到 END。

## 2.14 本章必答题

请回答：

1. 为什么 guest 地址 `0x80000000` 不能直接作为 C 指针？
2. 为什么 `mem_read()` 不建议用 `*(uint32_t *)` 直接读？
3. `addi a1, zero, 42` 执行后，哪些状态发生了变化？
4. 为什么 x0 必须保持为 0？
5. 执行 `ebreak` 后，PC 应该如何记录？你选择的约定是什么？
6. raw binary 和 ELF 的区别是什么？为什么本章先不用 ELF？

## 2.15 给 LLM 的提示

让 LLM 实现本章时，建议这样说：

```text
请根据 docs/textbook/chapter-02-trm-core.md 实现 Stage 1。
只实现 guest memory、CPUState、raw image loader、inst_fetch、
addi、ebreak 和 --image/--batch。
不要实现完整 RV32I，不要实现 monitor，不要实现 ELF。
每完成一个 checkpoint 都运行对应命令并报告结果。
```

## 2.16 本章完成标准

本章结束时，以下命令必须通过：

```sh
cmake --build build
./build/memu --image tests/images/stage1-trap.bin --batch
```

并且：

- image 被加载到 `0x80000000`。
- 第一条指令能设置 `a1 = 42`。
- 第二条指令能设置 `a0 = 0`。
- `ebreak` 能停止 MEMU。
- MEMU 打印 `HIT GOOD TRAP`。

通过后，再进入 Chapter 3 的简易调试器。
