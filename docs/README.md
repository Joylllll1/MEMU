# MEMU Docs 阅读指南

MEMU 是一个参考 NEMU PA 路线、用 LLM 结对实现的教学型 emulator 项目。这里的文档分成三类：

- `textbook/`：实验手册。它应该像 NEMU GitBook 一样，带学生一步一步复现 MEMU。
- `stages/`：验收清单。它用来确认某个阶段做完没有。
- `nemu-compatibility.md`：最终兼容目标。它定义 MEMU 至少要跑通哪些 NEMU PA riscv32 软件包。

读文档时不要只看 `stages/`。`stages/` 会告诉你“做到什么算完成”，但真正教你怎么从零写出来的是 `textbook/`。

## 推荐使用方式

每一阶段都按这个循环推进：

1. 读对应的 textbook chapter。
2. 按 chapter 里的小实验逐步实现。
3. 每完成一个 checkpoint 就构建和运行。
4. 遇到 bug 时先看 chapter 的调试建议。
5. 最后用对应 stage instruction 做验收。
6. Stage 0-8 完成后，按 `nemu-compatibility.md` 和 Chapter 10 做 NEMU PA 软件栈兼容性收口。

例如 Stage 1 的阅读顺序是：

```text
docs/textbook/chapter-02-trm-core.md
docs/stages/stage-01-trm-core.md
```

## 文档写作标准

MEMU textbook 不是 API 文档，也不是课程大纲。每一章都应该包含：

- 背景：为什么现在需要这一层抽象。
- 实验目标：本章结束后学生能看到什么结果。
- 目录规划：建议创建哪些文件，每个文件负责什么。
- 小步任务：一次只引入一个概念。
- 检查点：每一步应该运行什么命令，看到什么输出。
- 调试提示：如果结果不对，先查哪些地方。
- 必答题：让学生确认自己真的理解了系统行为。
- LLM 协作提示：如何把当前小任务交给 LLM，而不是让它乱做。

## macOS 与 NEMU Linux 环境

NEMU 官方 PA 默认在 GNU/Linux 环境完成。MEMU 在你的 MacBook 上开发，所以不能机械照搬 NEMU 的命令和工具链。MEMU 默认使用：

- macOS 作为宿主环境。
- C11 + clang。
- CMake 作为构建系统。
- RV32I 作为第一条 guest ISA 路线。
- 标准 C 和小工具优先，后续需要时再引入 RISC-V 交叉工具链、Docker 或 SDL。

核心原则是：学习 NEMU 的系统路线，不复制 NEMU 的 Linux 工程假设。

## 最终验收目标

MEMU 不应该停在“能跑几个自制 demo”。第一条完整路线的目标是：

```text
RV32I/RV32IM core
-> AM / am-kernels
-> Nanos-lite
-> Navy-apps
-> PAL/仙剑类综合应用
```

详细目标见：

```text
docs/nemu-stage-acceptance.md
docs/nemu-compatibility.md
docs/textbook/chapter-10-nemu-compatibility.md
```
