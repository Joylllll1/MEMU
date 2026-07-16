# Chapter 5: 程序装载、Trap 与测试基础设施

## 5.1 为什么本章重要

前面几章里，你已经能执行 RV32I 指令，也能用 monitor 观察 guest 状态。但这些测试大多还是“小玩具”：手写几条机器码，加载到固定地址，然后看寄存器。

从本章开始，MEMU 要变得像一个可以持续开发的实验平台。你需要解决三个问题：

1. 程序怎么被装载到 guest memory？
2. guest 程序怎么告诉 MEMU“我成功/失败地结束了”？
3. 如何批量运行测试，并在失败时定位现场？

NEMU PA 中有很多基础设施，例如 trace、difftest、ELF loader、测试集合。MEMU 现在先做最小版本。

## 5.2 本章结束时应该看到什么

你应该能运行：

```sh
./build/memu --image tests/images/good.bin --batch
./build/memu --image tests/images/bad.bin --batch
./build/memu --elf tests/images/sum.elf --batch
tools/run-tests.sh
```

并且看到：

```text
HIT GOOD TRAP
```

或者在失败时看到：

```text
HIT BAD TRAP
recent instructions:
...
```

## 5.3 本章新增或整理的文件

建议：

```text
include/
  memu/
    loader.h
    trap.h
    trace.h
src/
  loader/
    image.c
    elf.c
  cpu/
    trap.c
  utils/
    trace.c
tools/
  run-tests.sh
  mkbin/
tests/
  images/
  isa/
```

如果你已经在 Chapter 2 写了 `image.c`，本章继续扩展它。

## 5.4 第一件事：重新确认 raw binary 约定

raw binary 没有元数据。它只是一些字节。因此必须由 MEMU 约定：

```text
加载地址 = MEMU_MEM_BASE
入口地址 = MEMU_MEM_BASE
```

命令行：

```sh
./build/memu --image tests/images/stage1-trap.bin --batch
```

`--image` 始终表示 raw binary。

### Checkpoint 1

确保 Chapter 2 和 Chapter 4 的所有 `.bin` 测试还能运行。

如果加入本章改动后旧测试跑不通，先修旧测试。不要继续写 ELF loader。

## 5.5 第二件事：统一 trap 约定

从现在开始，采用稳定约定：

```text
guest 执行 ebreak 时停机
a0 == 0 -> HIT GOOD TRAP
a0 != 0 -> HIT BAD TRAP
```

这和很多测试框架类似：返回码 0 表示成功，非 0 表示失败。

在 `include/memu/trap.h` 中定义：

```c
typedef enum {
  TRAP_NONE,
  TRAP_GOOD,
  TRAP_BAD,
  TRAP_ABORT,
} TrapKind;

void trap_handle_ebreak(uint32_t pc);
TrapKind trap_kind(void);
int trap_exit_code(void);
```

或者更简单：在 CPU state 或全局 state 中保存 trap 状态。

### `ebreak` 的 PC 记录

建议记录 trap instruction 所在 PC，而不是 `pc + 4`。这样出错时更容易对应 trace。

也就是说：

```text
this_pc = ebreak 指令地址
trap_pc = this_pc
```

### Checkpoint 2

准备两个 binary：

```asm
# good.bin
addi a0, zero, 0
ebreak

# bad.bin
addi a0, zero, 1
ebreak
```

运行：

```sh
./build/memu --image tests/images/good.bin --batch
echo $?
./build/memu --image tests/images/bad.bin --batch
echo $?
```

预期：

- good 返回 0。
- bad 返回非 0。

如果输出写了 `HIT GOOD TRAP` 但进程返回码不是 0，测试 runner 会被误导。

## 5.6 第三件事：测试镜像生成工具

手写二进制文件不适合长期维护。现在建立一个最小生成工具。

目录：

```text
tools/mkbin/
```

可以用 C 写：

```c
static void write_u32_le(FILE *fp, uint32_t x) {
  fputc(x & 0xff, fp);
  fputc((x >> 8) & 0xff, fp);
  fputc((x >> 16) & 0xff, fp);
  fputc((x >> 24) & 0xff, fp);
}
```

生成：

```text
good.bin
bad.bin
rv32i-add.bin
rv32i-branch-sum.bin
rv32i-load-store.bin
```

### 为什么不直接提交二进制

可以提交生成后的 `.bin`，但必须保留生成来源。否则几周后你看到 `0x00a00513`，很难想起来它对应哪条指令。

推荐：

```text
tests/isa/good.S 或 tools/mkbin/good.c
tests/images/good.bin
```

## 5.7 第四件事：`--max-instr`

测试程序可能因为 branch 错误陷入死循环。加入：

```sh
./build/memu --image loop.bin --batch --max-instr 100000
```

如果超过限制：

```text
MEMU abort: instruction limit reached
pc = ...
```

默认值可以是：

```text
batch 模式：10000000
monitor c：无限或较大值
```

### Checkpoint 3

写一个死循环 binary：

```asm
jal zero, 0
```

运行：

```sh
./build/memu --image tests/images/infinite-loop.bin --batch --max-instr 100
```

预期 MEMU abort，而不是卡死。

## 5.8 第五件事：iringbuf

完整 trace 很多，默认全部打印会影响阅读。我们先实现 instruction ring buffer。

数据结构：

```c
#define IRINGBUF_SIZE 32

typedef struct {
  uint32_t pc;
  uint32_t inst;
} ITraceEntry;
```

每执行一条指令前或后记录：

```c
trace_record(pc, inst);
```

出错时打印最近 32 条：

```text
recent guest instructions:
  0x80000000: 0x02a00513
  0x80000004: 0x00000073
->0x80000008: 0xdeadbeef
```

箭头指向最后一条或出错指令。

### Checkpoint 4

准备一个非法指令测试：

```text
0xffffffff
```

运行后应看到 invalid instruction 和 recent instructions。

## 5.9 第六件事：`--trace`

iringbuf 是出错时打印。`--trace` 是每条指令都打印。

命令：

```sh
./build/memu --image tests/images/good.bin --batch --trace
```

输出：

```text
0x80000000: 0x00000513
0x80000004: 0x00100073
```

本章不要求完整反汇编。完整反汇编可以等后面再接 Capstone 或手写简单 disasm。

### macOS 注意

不要为了反汇编立刻引入 GNU objdump 或 Capstone。当前 trace 打印 PC 和机器码已经足够定位大部分早期 bug。

## 5.10 第七件事：ELF 是什么

raw binary 简单，但真实编译器通常输出 ELF。ELF 文件包含：

- 文件类型。
- 目标 ISA。
- 入口地址。
- program headers。
- section headers。
- 符号表等。

loader 真正关心的是 program headers，尤其是 `PT_LOAD` 段。section headers 对运行程序不是必需的。

## 5.11 第八件事：最小 ELF loader

命令行约定：

```sh
./build/memu --elf tests/images/sum.elf --batch
```

为了避免混淆：

- `--image`：raw binary。
- `--elf`：ELF executable。

第一版 ELF loader 只支持：

```text
ELF32
little endian
RISC-V
ET_EXEC
PT_LOAD
static executable
```

不支持：

```text
dynamic linking
shared object
relocation
compressed instruction requirement
64-bit ELF
```

### 读取 ELF header

你可以使用 `<elf.h>` 吗？macOS 有自己的 `<elf.h>` 情况并不稳定。为了跨平台，建议自己定义最小结构，或者写一个只读字段的 parser。

需要检查：

```text
e_ident[0..3] == 0x7f 'E' 'L' 'F'
EI_CLASS == ELFCLASS32
EI_DATA == ELFDATA2LSB
e_machine == EM_RISCV
e_type == ET_EXEC
```

### 加载 PT_LOAD

对每个 program header：

```text
if p_type == PT_LOAD:
  从文件 p_offset 读取 p_filesz 字节
  拷贝到 guest address p_vaddr
  p_memsz > p_filesz 的部分清零
```

最后：

```text
cpu.pc = e_entry
```

## 5.12 ELF loader 的三个地址

这是本章最容易混淆的地方：

| 名称 | 含义 |
| --- | --- |
| file offset | ELF 文件中的偏移，例如 `p_offset` |
| guest address | guest 程序看到的地址，例如 `p_vaddr` |
| host pointer | MEMU 进程里的 C 指针，例如 `&pmem[...]` |

错误示例：

```c
fread((void *)ph.p_vaddr, 1, ph.p_filesz, fp);
```

这是错的，因为 `p_vaddr` 是 guest address，不是 host pointer。

正确做法：

```c
fread(guest_to_host(ph.p_vaddr), 1, ph.p_filesz, fp);
```

## 5.13 Checkpoint 5：加载 ELF

如果你暂时没有 RISC-V 工具链，可以先跳过 ELF 的实际生成，只写 loader 并用后续工具补测试。

如果你已有工具链，准备一个最小程序：

```c
void _start(void) {
  asm volatile(
    "li a0, 0\n"
    "ebreak\n"
  );
}
```

编译成 RV32I ELF 后运行：

```sh
./build/memu --elf tests/images/good.elf --batch
```

预期 good trap。

## 5.14 第九件事：测试 runner

创建：

```text
tools/run-tests.sh
```

第一版：

```sh
#!/usr/bin/env sh
set -eu

memu="${1:-./build/memu}"

for img in tests/images/*.bin; do
  echo "RUN $img"
  "$memu" --image "$img" --batch
done

for elf in tests/images/*.elf; do
  [ -e "$elf" ] || continue
  echo "RUN $elf"
  "$memu" --elf "$elf" --batch
done
```

注意：如果没有 `.elf` 文件，shell glob 在不同 shell 下可能行为不同。上面用 `[ -e "$elf" ] || continue` 做兼容。

### Checkpoint 6

运行：

```sh
tools/run-tests.sh ./build/memu
```

所有 good 测试应通过。bad 测试不要放进默认 runner，或者单独标记 expected-fail。

## 5.15 第十件事：CTest 集成

在 CMake 里加入：

```cmake
add_test(NAME memu-tests COMMAND
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/run-tests.sh
  $<TARGET_FILE:memu>
)
```

这样你可以统一运行：

```sh
ctest --test-dir build --output-on-failure
```

## 5.16 调试路线

### good binary 被判成 bad trap

检查 `a0` 的值。可能是测试程序没有设置 `a0 = 0`。

### bad binary 返回码还是 0

检查 host process exit code 是否和 trap kind 对应。

### ELF 程序入口不对

打印：

```text
e_entry
每个 PT_LOAD 的 p_offset p_vaddr p_filesz p_memsz
```

确认 `cpu.pc = e_entry`，不是固定 `MEMU_MEM_BASE`。

### `.bss` 未初始化

如果 `p_memsz > p_filesz`，多出来的部分必须清零。

### runner 卡住

给 runner 默认加 `--max-instr`，防止单个测试死循环。

## 5.17 必答题

请回答：

1. raw binary 为什么需要 MEMU 约定加载地址？
2. ELF loader 为什么看 program header，而不是 section header？
3. `p_filesz` 和 `p_memsz` 有什么区别？
4. 为什么 `p_vaddr` 不能直接当 C 指针？
5. good trap 和 host process exit code 应该如何对应？
6. 为什么 bad 测试不应该混进默认 pass runner？

## 5.18 给 LLM 的提示

建议分任务：

```text
1. 统一 ebreak trap 约定和 host exit code。
2. 实现 --max-instr、iringbuf 和 --trace。
3. 写 mkbin 工具和 tools/run-tests.sh。
4. 实现最小 ELF32 RISC-V loader。
5. 把 runner 接入 CTest。
```

强调：

```text
不要引入动态链接，不要支持 ELF64，不要依赖 Linux-only <elf.h>。
```

## 5.19 本章完成标准

必须通过：

```sh
cmake --build build
./build/memu --image tests/images/good.bin --batch
./build/memu --image tests/images/bad.bin --batch
./build/memu --image tests/images/infinite-loop.bin --batch --max-instr 100
tools/run-tests.sh ./build/memu
ctest --test-dir build --output-on-failure
```

如果有 ELF 测试：

```sh
./build/memu --elf tests/images/good.elf --batch
```

通过后进入 Chapter 6。下一章会让 guest 程序通过 MMIO 输出字符、读取时间，并逐步接近 AM 的抽象。
