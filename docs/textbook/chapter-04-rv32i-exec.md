# Chapter 4: 实现 RV32I 取指、译码、执行

## 4.1 为什么现在扩展指令集

到目前为止，MEMU 只能执行很少几条指令。它已经证明“取指、译码、执行、更新 PC”的循环可以工作，但还不能运行真实编译器生成的程序。

本章要把 MEMU 扩展成一个可以运行常见 RV32I 裸机测试的解释器。你会实现算术、访存、分支、跳转和系统指令。

本章的关键词是：准确。不要追求性能，不要追求优雅的一行宏。你现在最重要的任务是把每条指令的语义写对，并为容易出错的地方留下测试。

## 4.2 本章结束时应该看到什么

你应该能运行一组小测试：

```sh
./build/memu --image tests/images/rv32i-add.bin --batch
./build/memu --image tests/images/rv32i-branch-sum.bin --batch
./build/memu --image tests/images/rv32i-load-store.bin --batch
./build/memu --image tests/images/rv32i-jump.bin --batch
```

每个测试都应该以 `HIT GOOD TRAP` 结束。

如果出错，MEMU 应该打印：

```text
invalid instruction at pc=..., inst=...
```

或者打印最近执行的若干条指令，帮助你定位。

## 4.3 建议整理代码

Chapter 2 的 `decode.c` 可能已经放了 `addi` 和 `ebreak`。本章会让它变大，因此建议整理为：

```text
include/
  memu/
    isa.h
src/
  cpu/
    decode.c
    exec_rv32i.c
tests/
  isa/
  images/
```

一种简单分工：

- `decode.c`：取字段、分发 opcode。
- `exec_rv32i.c`：具体指令语义 helper。
- `isa.h`：RISC-V 相关常量和寄存器编号。

如果你觉得拆文件太早，也可以先都放在 `decode.c`，但要用清楚的小函数分段。

## 4.4 第一步：字段提取 helper

RISC-V 指令固定 32 位。你需要频繁提取 bit fields。

建议写：

```c
static inline uint32_t bits(uint32_t x, int hi, int lo) {
  return (x >> lo) & ((1u << (hi - lo + 1)) - 1);
}

static inline uint32_t opcode(uint32_t inst) { return bits(inst, 6, 0); }
static inline uint32_t rd(uint32_t inst)     { return bits(inst, 11, 7); }
static inline uint32_t funct3(uint32_t inst) { return bits(inst, 14, 12); }
static inline uint32_t rs1(uint32_t inst)    { return bits(inst, 19, 15); }
static inline uint32_t rs2(uint32_t inst)    { return bits(inst, 24, 20); }
static inline uint32_t funct7(uint32_t inst) { return bits(inst, 31, 25); }
```

注意 `bits()` 如果要支持 32 位宽度，`1u << 32` 是未定义行为。这里提取字段最多 25 位左右，暂时安全。但你要知道这个边界。

### Checkpoint 1

对指令：

```text
0x02a00593  // addi a1, zero, 42
```

应得到：

```text
opcode = 0x13
rd     = 11
funct3 = 0
rs1    = 0
imm_i  = 42
```

写一个临时 debug 输出，确认后再继续。

## 4.5 第二步：符号扩展

很多 immediate 是有符号数。写一个通用 helper：

```c
static inline int32_t sign_extend(uint32_t x, int width) {
  uint32_t mask = 1u << (width - 1);
  return (int32_t)((x ^ mask) - mask);
}
```

检查：

```text
sign_extend(0x000, 12) = 0
sign_extend(0x001, 12) = 1
sign_extend(0x7ff, 12) = 2047
sign_extend(0x800, 12) = -2048
sign_extend(0xfff, 12) = -1
```

### Checkpoint 2

先不要写更多指令。写一个小测试或临时断言确认上面的五个值正确。

如果符号扩展错了，后面 branch、load offset、addi 负数都会错。

## 4.6 第三步：各类 immediate

实现：

```c
static inline int32_t imm_i(uint32_t inst);
static inline int32_t imm_s(uint32_t inst);
static inline int32_t imm_b(uint32_t inst);
static inline int32_t imm_u(uint32_t inst);
static inline int32_t imm_j(uint32_t inst);
```

### I-type

```text
imm[11:0] = inst[31:20]
```

### S-type

```text
imm[11:5] = inst[31:25]
imm[4:0]  = inst[11:7]
```

### B-type

```text
imm[12]   = inst[31]
imm[10:5] = inst[30:25]
imm[4:1]  = inst[11:8]
imm[11]   = inst[7]
imm[0]    = 0
```

B-type 是最容易写错的格式之一。不要凭感觉拼。

### U-type

```text
imm[31:12] = inst[31:12]
imm[11:0]  = 0
```

### J-type

```text
imm[20]    = inst[31]
imm[10:1]  = inst[30:21]
imm[11]    = inst[20]
imm[19:12] = inst[19:12]
imm[0]     = 0
```

J-type 也是高危区域。

### Checkpoint 3

为 B-type 和 J-type 准备至少两个测试：

- 正偏移。
- 负偏移。

可以先用手写机器码，也可以后续用 RISC-V assembler 生成。关键是：不要等完整程序跑错了才第一次测试 immediate。

## 4.7 第四步：PC 更新模型

建议在执行每条指令时使用两个概念：

```c
uint32_t this_pc = cpu.pc;
uint32_t snpc = this_pc + 4;
uint32_t dnpc = snpc;
```

含义：

- `this_pc`：当前指令地址。
- `snpc`：顺序执行的下一条地址。
- `dnpc`：动态决定的下一条地址。

普通指令：

```text
dnpc = snpc
```

branch taken：

```text
dnpc = this_pc + imm_b(inst)
```

jal：

```text
rd = snpc
dnpc = this_pc + imm_j(inst)
```

jalr：

```text
rd = snpc
dnpc = (rs1 + imm_i(inst)) & ~1
```

最后统一：

```c
cpu.pc = dnpc;
cpu.gpr[0] = 0;
```

这种写法比在每条指令里到处 `cpu.pc += 4` 更不容易错。

## 4.8 第五步：U-type 指令

实现：

```text
lui
auipc
```

语义：

```text
lui:   rd = imm_u
auipc: rd = pc + imm_u
```

### Checkpoint 4

测试：

```asm
lui a0, 0x12345
```

应得到：

```text
a0 = 0x12345000
```

测试 `auipc` 时要注意它使用的是当前指令的 PC，不是下一条 PC。

## 4.9 第六步：I/R 算术指令

实现 I-type：

```text
addi slti sltiu xori ori andi slli srli srai
```

实现 R-type：

```text
add sub sll slt sltu xor srl sra or and
```

### signed 和 unsigned

`slt`：

```c
rd = (int32_t)src1 < (int32_t)src2;
```

`sltu`：

```c
rd = src1 < src2;
```

### shift amount

RV32I 中 shift amount 只取低 5 位：

```c
shamt = src2 & 0x1f;
```

I-type shift 的 shamt 来自 immediate 低 5 位。

### `srai` 和 `srli`

二者 opcode 和 funct3 一样，靠 funct7 区分：

```text
srli funct7 = 0x00
srai funct7 = 0x20
```

### Checkpoint 5

准备一个 arithmetic 测试，覆盖：

- `add` 和 `sub`。
- `and/or/xor`。
- `slt` 和 `sltu` 对 `0xffffffff` 的不同行为。
- `srl` 和 `sra` 对负数的不同结果。

预期最后 `a0 = 0` 并 `ebreak` good trap。

## 4.10 第七步：load/store

实现 load：

```text
lb lh lw lbu lhu
```

实现 store：

```text
sb sh sw
```

所有访存必须走：

```c
mem_read(addr, len)
mem_write(addr, len, data)
```

不要在指令实现中直接访问 `pmem`。

### load 的扩展

```text
lb  -> 读 1 字节，符号扩展到 32 位
lh  -> 读 2 字节，符号扩展到 32 位
lw  -> 读 4 字节
lbu -> 读 1 字节，零扩展
lhu -> 读 2 字节，零扩展
```

### 对齐

RV32I 对未对齐访存的处理可以很复杂。教学版 MEMU 第一阶段可以选择：

- 暂时允许未对齐，由 `mem_read` 按字节拼。
- 或者检测未对齐并 abort。

建议先允许未对齐，减少早期阻塞；但文档和代码注释要写明这是简化。

### Checkpoint 6

测试：

```asm
addi t0, zero, 0x7f
sw   t0, 0(sp)
lw   t1, 0(sp)
```

但注意：此时 `sp` 可能还是 0，不能直接用。你需要先把 `sp` 设置到 guest memory 的某个安全位置，例如：

```text
sp = MEMU_MEM_BASE + 0x1000
```

可以在 `cpu_reset()` 中临时设置 `sp`，或者在测试程序里构造。

## 4.11 第八步：branch

实现：

```text
beq bne blt bge bltu bgeu
```

branch 的共同形式：

```c
if (condition) {
  dnpc = this_pc + imm_b(inst);
}
```

### Checkpoint 7：循环求和

写一个程序计算：

```text
1 + 2 + ... + 100 = 5050
```

伪汇编：

```asm
addi t0, zero, 0      # i
addi t1, zero, 0      # sum
addi t2, zero, 100
loop:
addi t0, t0, 1
add  t1, t1, t0
blt  t0, t2, loop
```

最后检查 `t1 == 5050`，然后 good trap。

如果结果是 4950 或 5150，通常是循环边界错。如果直接飞出内存，通常是 B-type immediate 拼错。

## 4.12 第九步：jump

实现：

```text
jal
jalr
```

`jal`：

```text
rd = pc + 4
pc = pc + imm_j
```

`jalr`：

```text
rd = pc + 4
pc = (rs1 + imm_i) & ~1
```

注意 `jalr` 清最低位，这是 RISC-V 规定。

### Checkpoint 8

写一个简单函数调用形状：

```asm
jal ra, func
addi a0, zero, 1      # 不应执行
ebreak
func:
addi a0, zero, 0
jalr zero, 0(ra)
```

这个例子需要你想清楚返回后会不会执行 `ebreak`，以及 `ra` 保存的地址是什么。

## 4.13 第十步：system 指令

现在至少区分：

```text
ecall  = 0x00000073
ebreak = 0x00100073
```

本章中：

- `ebreak` 继续作为 halt/trap。
- `ecall` 可以先打印 “ecall not implemented” 并 abort。

Chapter 7 再实现 syscall。

## 4.14 第十一步：非法指令

遇到不认识的指令，不要当 nop。打印：

```text
invalid instruction at pc=0x80000010, inst=0xdeadbeef
```

然后 abort。

如果已经实现 iringbuf 或 itrace，也打印最近执行的指令。

## 4.15 第十二步：最小 itrace

在 Chapter 3 你已经有 monitor；现在需要更适合批处理测试的 trace。

第一版可以加参数：

```sh
./build/memu --image test.bin --batch --trace
```

每条指令打印：

```text
0x80000000: 0x02a00593
```

暂时不要求完整反汇编。等需要时再加入：

```text
0x80000000: 0x02a00593  addi a1, zero, 42
```

### iringbuf

大量输出 trace 会很吵。更好的方式是保留最近 N 条：

```c
#define IRINGBUF_SIZE 32
```

每执行一条指令，把 `{pc, inst}` 写入环形缓冲区。出错时打印最近 32 条。

## 4.16 测试组织

本章建议建立：

```text
tests/images/rv32i-add.bin
tests/images/rv32i-load-store.bin
tests/images/rv32i-branch-sum.bin
tests/images/rv32i-jump.bin
tests/smoke/run_rv32i.sh
```

`run_rv32i.sh` 做：

```sh
#!/usr/bin/env sh
set -eu

memu="$1"

for img in tests/images/rv32i-*.bin; do
  echo "RUN $img"
  "$memu" --image "$img" --batch
done
```

后续可以升级成检查输出里是否有 `HIT GOOD TRAP`。

## 4.17 调试路线

### 算术结果错

检查：

- rd/rs1/rs2 提取。
- signed/unsigned。
- x0 是否被写坏。

### load/store 错

检查：

- 地址是否在 guest memory 范围。
- little endian。
- sign extend 和 zero extend。
- store 的 S-type immediate。

### branch 飞掉

优先检查 B-type immediate。打印：

```text
pc, inst, imm_b, target
```

如果 target 不是 4 字节对齐，基本就是 immediate 拼错。

### jal/jalr 返回错

检查：

- rd 是否写入 `pc + 4`。
- target 是否用当前 PC 算。
- `jalr` 是否清最低位。

### 程序卡死

用 `--max-instr N` 限制执行条数。超过 N 后打印当前 PC 和最近指令。

## 4.18 必答题

请回答：

1. 为什么建议使用 `snpc` 和 `dnpc` 两个概念？
2. B-type immediate 的 bit 为什么容易拼错？
3. `slt` 和 `sltu` 在比较 `0xffffffff` 和 `0` 时有什么不同？
4. `lb` 和 `lbu` 的区别是什么？
5. `jalr` 为什么要把目标地址最低位清 0？
6. 未实现指令为什么不能默默当作 nop？

## 4.19 给 LLM 的提示

不要让 LLM 一次实现全部 RV32I。建议这样分：

```text
1. 实现字段提取、符号扩展和 immediate helper，补测试。
2. 实现 U-type 和 I/R 算术，补 arithmetic 测试。
3. 实现 load/store，补 memory 测试。
4. 实现 branch，补 sum loop 测试。
5. 实现 jal/jalr/system/invalid instruction 和 itrace。
```

每一步都运行前一步测试，确保没有回归。

## 4.20 本章完成标准

以下测试必须 good trap：

```sh
./build/memu --image tests/images/rv32i-add.bin --batch
./build/memu --image tests/images/rv32i-load-store.bin --batch
./build/memu --image tests/images/rv32i-branch-sum.bin --batch
./build/memu --image tests/images/rv32i-jump.bin --batch
```

并且：

- 非法指令有清楚报错。
- `--trace` 或 iringbuf 能帮助定位最近执行的 guest 指令。
- monitor 的 `si/info r/x/p` 仍然可用。

通过后进入 Chapter 5。下一章会解决程序装载、ELF、trap 规范和自动化测试。
