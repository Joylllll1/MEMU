# MEMU Textbook

这套 textbook 是 MEMU 的实验手册。它的目标是让一个学生可以跟着文档，从空仓库一步一步实现一个教学型 emulator，并最终把它推进到能运行 NEMU PA riscv32 软件栈的程度。

请注意：这里的“学生可以跟着做”，不是指文档直接给出完整答案。好的实验手册应该给足上下文、任务边界、验证方法和调试线索，但仍然保留需要学生思考和实现的空间。

## 与 NEMU GitBook 的关系

NEMU GitBook 的路线大致是：

- PA0：准备环境。
- PA1：最简单的计算机和简易调试器。
- PA2：冯诺依曼计算机系统、运行时和输入输出。
- PA3：批处理系统、系统调用、文件系统。
- PA4：多道程序、虚存和中断。

MEMU textbook 会保留这条学习曲线，但做四点调整：

1. 宿主环境改为 macOS。
2. 工程框架改为 CMake + C11。
3. ISA 首选 RV32I，减少无关复杂度。
4. 在 Stage 0-8 之后增加 NEMU PA riscv32 兼容性收口章节。

## 如何跟着 textbook 做实验

每章都按这样的节奏组织：

```text
读背景
明确本章最后要看到什么
创建或阅读本章相关文件
完成任务 1
运行 checkpoint 1
完成任务 2
运行 checkpoint 2
回答必答题
用 stage instruction 做验收
```

不要跳过 checkpoint。emulator 的错误经常会跨层传播，早一点发现错误，后面会轻松很多。

## 章节安排

| Chapter | 对应 Stage | 内容 |
| --- | --- | --- |
| Chapter 0 | Stage 0 | macOS 环境和 Linux 差异 |
| Chapter 1 | Stage 0 | 从空仓库搭项目骨架 |
| Chapter 2 | Stage 1 | 最小计算机 TRM |
| Chapter 3 | Stage 2 | 简易调试器 |
| Chapter 4 | Stage 3 | RV32I 指令执行 |
| Chapter 5 | Stage 4 | loader、trap、测试基础设施 |
| Chapter 6 | Stage 5 | MMIO、设备和 mini AM |
| Chapter 7 | Stage 6 | syscall 和批处理系统 |
| Chapter 8 | Stage 7 | ramdisk、文件系统和应用 |
| Chapter 9 | Stage 8 | 多道程序、虚存和中断 |
| Chapter 10 | Compatibility | 对齐 NEMU PA riscv32 软件栈 |

## 和 LLM 协作的方式

使用 LLM 时，不要说：

```text
帮我实现一个 emulator。
```

要说：

```text
请阅读 docs/textbook/chapter-02-trm-core.md 的 2.3 到 2.5 小节，
只实现 memory、CPUState 和 inst_fetch，
不要实现完整 RV32I，也不要做 debugger。
实现后运行该小节的 checkpoint。
```

LLM 越被限制在当前小节，越不容易提前引入错误抽象。

进入兼容性阶段后，也不要说：

```text
帮我兼容 NEMU。
```

要说：

```text
当前 MEMU 跑 cpu-tests/branch 失败。
请只检查 RV32I B-type immediate、符号扩展和 PC 更新。
不要改 loader、debugger 或设备。
修复后运行 tests/compat/scripts/run-cpu-branch.sh。
```
