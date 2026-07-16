# Stage 1: 最小计算机 TRM

## 参考 NEMU 的位置

对应 NEMU PA1 中“最简单的计算机”。核心模型是：从 PC 指向的内存取出指令，执行指令，更新 PC，如此循环。

## 为什么做

这是 emulator 的地基。计算机系统最关键的想法是“存储程序，程序控制”：程序和数据都在内存中，CPU 通过 PC 找到下一条指令。只要内存、寄存器、PC 和执行循环成立，后续所有复杂机制都可以接上来。

## 要实现什么

- `CPUState`：32 个通用寄存器和 `pc`。
- `Memory`：一段连续物理内存，比如 128 MiB。
- 取指函数：从 `pc` 读取 32-bit little endian 指令。
- 最小执行循环：`cpu_exec(n)`。
- 只实现少量 RV32I 指令：`lui`、`addi`、`jal`、`ebreak`。
- `ebreak` 暂时作为 MEMU trap/halt。

## 怎么做

1. 定义内存基址，例如 `MEM_BASE = 0x80000000`。
2. 实现 guest address 到 host pointer 的转换，所有访存都经过边界检查。
3. 定义寄存器读写函数，保证 `x0` 永远是 0。
4. 实现 `inst_fetch()`，一次读取 4 字节。
5. 实现最小 decode：按 opcode 分发。
6. 写一个内置测试程序，手工放入几条机器码：设置寄存器、循环或 halt。

## 怎么验证

```sh
cmake --build build
./build/memu --image tests/images/stage1-addi.bin --batch
```

期望结果：

- 程序执行到 `ebreak` 后退出。
- 退出日志显示 `HIT GOOD TRAP`。
- 寄存器结果符合预期，例如 `x10 = 42`。

## 常见坑

- RISC-V 指令是 little endian，取指时不能按文本顺序拼错。
- `pc` 默认加 4，但 `jal`、branch、trap 会改变控制流。
- 立即数需要符号扩展，不能简单当无符号数。
- `x0` 写入必须被丢弃。
- 访存地址要先从 guest address 转换到内存数组下标。

## 给 LLM 的提示

实现 Stage 1 时，只做最小 TRM 和四条指令。不要加入完整 RV32I，不要写 ELF loader，不要写调试器。每增加一条指令，都要说明它的编码字段和 PC 更新规则。

## 和 NEMU 对齐的验收

对应 NEMU PA1 的“最简单的计算机”。这个阶段的目标不是跑 `cpu-tests`，而是确认 TRM 状态机成立：

- 能从 raw image 的固定入口取指。
- 能执行几条最小指令并更新 PC。
- 能通过 trap 明确表达程序结束。
- 能打印关键寄存器和 PC，便于后续接入 monitor。

如果这一步不稳定，后续 PA2 的 `cpu-tests` 会把错误放大。

## 完成标准

- MEMU 可以加载 raw binary 到内存基址。
- `cpu_exec()` 可以执行固定条数或直到 trap。
- 最小测试程序能稳定 halt，并打印关键寄存器。
