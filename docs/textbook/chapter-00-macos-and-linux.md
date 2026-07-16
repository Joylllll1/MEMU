# Chapter 0: macOS 环境与 NEMU 的 Linux 前提

## 0.1 为什么第一章不是写代码

很多系统实验失败，不是因为学生写不出 CPU，而是因为一开始没有分清“我在哪个环境里工作”。NEMU PA 默认使用 GNU/Linux；你现在使用的是 MacBook。它们都能写 C 程序，但工程细节并不相同。

这一章的目标是把环境边界划清楚。你不需要安装一堆工具，也不需要马上配置 RISC-V 交叉编译器。你只需要知道：哪些东西可以直接参考 NEMU，哪些东西必须为 macOS 改写。

## 0.2 四个层次

后面所有实验都要分清四个层次：

| 层次 | 在 MEMU 中的含义 | 例子 |
| --- | --- | --- |
| Host machine | 真实机器 | 你的 MacBook |
| Host OS | 真实操作系统 | macOS |
| Host program | 运行在 macOS 上的程序 | `memu` |
| Guest machine | MEMU 模拟出来的机器 | RV32I 计算机 |
| Guest program | 运行在 guest machine 上的程序 | `sum.bin`、`hello.elf` |

当你在终端执行：

```sh
./build/memu --image tests/images/addi.bin
```

`./build/memu` 是 macOS 程序；`addi.bin` 是 RISC-V 程序。前者由 Apple clang 编译，后者最终会由 RISC-V 工具链或手写机器码生成。

如果你把这两层混起来，就会出现很典型的错误：

- 试图用 macOS 的 `printf()` 解释 guest 程序里的 `printf()`。
- 把 guest 地址 `0x80000000` 当成 host 指针。
- 以为 macOS 的 syscall 就是 guest 的 syscall。
- 以为 `clang` 编译出来的可执行文件可以直接放进 MEMU 跑。

这些都是概念层次混乱造成的。

## 0.3 NEMU 的 Linux 假设

NEMU GitBook 中很多命令默认满足这些条件：

- 有 GNU/Linux 用户态。
- 有 GCC 和 GNU Make。
- 有 GNU binutils，例如 `objdump`、`readelf`。
- 有 GNU readline。
- 有课程仓库脚本和 Makefile 变量。
- 有适配 PA 的交叉编译工具链。

MEMU 不应该假设这些东西已经存在。我们要做的是：

- 保留 NEMU 的系统路线。
- 把构建和工具链换成 macOS 友好的方式。
- 在需要 Linux 工具时，明确是用 Homebrew、Docker，还是预编译二进制。

## 0.4 Stage 0 只检查最小工具

现在只需要检查：

```sh
clang --version
cmake --version
git --version
```

可选：

```sh
ninja --version
```

如果没有 CMake，可以稍后用 Homebrew 安装：

```sh
brew install cmake
```

但本章不要求你立刻安装。先把文档和工程边界确定下来。

## 0.5 暂时不要安装什么

Stage 0 暂时不要安装：

- RISC-V toolchain。
- SDL。
- GNU readline。
- Capstone。
- QEMU。
- Docker。

这些工具以后可能会用，但现在装它们只会制造噪音。一个教学项目最怕开局就把学生淹没在依赖里。

## 0.6 MEMU 的默认工程选择

MEMU 采用以下默认选择：

| 问题 | 选择 | 原因 |
| --- | --- | --- |
| 宿主系统 | macOS | 项目运行在你的 MacBook 上 |
| 语言 | C11 | 贴近 NEMU，又避免 GNU 扩展 |
| 编译器 | clang | macOS 默认可用 |
| 构建 | CMake | 跨平台，适合小项目逐步扩展 |
| ISA | RV32I | 简洁，适合教学 |
| 早期 guest 程序 | raw binary | 避免过早引入 ELF |
| 早期 monitor | `fgets()` | 避免 readline 兼容性 |
| 早期设备 | stdout + host clock | 避免 SDL 和窗口权限问题 |

## 0.7 本章小实验：确认你没有混淆 host 和 guest

请回答下面的问题：

1. `memu` 是 x86/ARM 程序，还是 RISC-V 程序？
2. `tests/images/addi.bin` 是 macOS 程序，还是 RISC-V 程序？
3. guest 地址 `0x80000000` 能不能直接转换成 C 指针使用？
4. macOS 的 `write()` syscall 和 guest 的 `SYS_write` 是一回事吗？

参考答案：

1. `memu` 是 host program，由 macOS 上的 clang 编译。
2. `addi.bin` 是 guest program，应该包含 RISC-V 指令。
3. 不能。必须通过 MEMU 的地址转换函数映射到 host memory。
4. 不是。guest 的 syscall 是 MEMU 或 guest OS 解释出来的约定。

## 0.8 给 LLM 的提示

后面请始终提醒 LLM：

```text
本项目在 macOS 上开发。不要假设 apt、GNU readline、Linux-only Makefile 或 GNU objdump 存在。
当前阶段优先使用 C11、clang、CMake 和标准库。
区分 host program、guest machine 和 guest program。
```

## 0.9 本章完成标准

你完成本章后，应该能用自己的话说明：

- MEMU 和 NEMU 的环境差异。
- 为什么 MEMU 不能照搬 NEMU 的 Linux 命令。
- host program 和 guest program 的区别。
- 为什么 Stage 0 不安装大依赖。
