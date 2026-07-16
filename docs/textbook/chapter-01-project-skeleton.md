# Chapter 1: 从空仓库搭项目骨架

## 1.1 本章目标

现在开始写第一个真正的实验。你还不会实现 CPU，也不会执行 RISC-V 指令，但你要先得到一个健康的 C 项目。

本章结束时，你应该可以运行：

```sh
cmake -S . -B build
cmake --build build
./build/memu --help
ctest --test-dir build --output-on-failure
```

并且看到：

- `memu` 可以打印帮助信息。
- CTest 至少运行一个 smoke test。
- 项目目录已经为后续 CPU、memory、monitor 留出位置。

## 1.2 为什么要先做工程骨架

你可能会想：既然目标是 emulator，为什么不直接写 CPU？

原因很简单：后续每个阶段都会反复经历“改代码 -> 构建 -> 运行 -> 观察输出 -> 定位 bug”。如果构建和测试入口不稳定，你每次都会花时间猜问题到底在工程系统还是 emulator 逻辑。

这就是 NEMU PA 反复强调基础设施的原因。基础设施本身不一定是计算机系统知识，但它决定你能不能有效地学习系统知识。

## 1.3 目录结构

从空仓库开始，先建立最小结构：

```text
MEMU/
  CMakeLists.txt
  README.md
  include/
    memu/
      common.h
  src/
    main.c
  tests/
    smoke/
      run_help.sh
  docs/
```

暂时不要创建这些目录：

```text
src/cpu/
src/memory/
src/device/
src/monitor/
```

它们会在后续章节出现。过早创建空目录会让项目看起来很完整，但学生并不知道每个目录为什么存在。

## 1.4 第一个文件：`CMakeLists.txt`

先写顶层 CMake。它要完成五件事：

1. 声明项目。
2. 使用 C11。
3. 生成 `memu` 可执行文件。
4. 打开常用 warning。
5. 注册测试。

建议结构：

```cmake
cmake_minimum_required(VERSION 3.20)

project(MEMU LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(memu
  src/main.c
)

target_include_directories(memu PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(memu PRIVATE
  -Wall
  -Wextra
  -Wpedantic
)

enable_testing()
add_test(NAME help COMMAND
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke/run_help.sh
  $<TARGET_FILE:memu>
)
```

这里先不要使用 `-Werror`。教学项目早期变化很快，`-Werror` 容易让不同编译器版本带来不必要阻塞。等代码稳定后再考虑。

### Checkpoint 1

运行：

```sh
cmake -S . -B build
```

你应该看到 CMake 生成 build 目录。如果报错：

- 检查 CMake 版本是否太低。
- 检查 `src/main.c` 是否已经存在。
- 检查路径大小写。

## 1.5 第二个文件：`src/main.c`

第一版 `main.c` 只处理三个行为：

- `--help`
- `--version`
- 未知参数报错

建议行为：

```text
$ ./build/memu --help
Usage: memu [OPTIONS]

Options:
  --help       Show this help message
  --version    Show MEMU version
```

未知参数：

```text
$ ./build/memu --bad
memu: unknown option '--bad'
Try '--help' for usage.
```

这看起来很小，但它会形成后续命令行接口的风格。后面我们会加入：

```text
--image FILE
--batch
--max-instr N
--trace
--ramdisk FILE
```

### 实现要求

不要在 `main.c` 里写 emulator 逻辑。第一版可以有这些函数：

```c
static void print_help(FILE *out);
static void print_version(void);
static int parse_args(int argc, char **argv);
int main(int argc, char **argv);
```

其中 `parse_args()` 暂时只识别 `--help` 和 `--version`。

### Checkpoint 2

运行：

```sh
cmake --build build
./build/memu --help
./build/memu --version
./build/memu --bad
```

预期：

- 前两个命令返回 0。
- `--bad` 返回非 0。
- 终端输出清楚，不崩溃。

## 1.6 第三个文件：`include/memu/common.h`

现在创建公共头文件，但保持克制。它只放全局通用的东西：

```c
#ifndef MEMU_COMMON_H
#define MEMU_COMMON_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint32_t word_t;

#define MEMU_ARRAY_LEN(arr) (sizeof(arr) / sizeof((arr)[0]))

#define MEMU_PANIC(...) do {            \
  fprintf(stderr, "MEMU panic: ");      \
  fprintf(stderr, __VA_ARGS__);         \
  fprintf(stderr, "\n");                \
  abort();                              \
} while (0)

#endif
```

注意这里不要包含 `cpu.h` 或 `memory.h`。公共头文件如果变成“什么都包含”，后续会让依赖关系变得混乱。

### 思考题 1

为什么 `common.h` 不应该包含 CPUState 的定义？

提示：想象后续 `memory.c`、`monitor.c`、`device.c` 都包含 `common.h`，如果 `common.h` 又包含很多模块，就会发生什么？

## 1.7 第四个文件：smoke test

创建：

```text
tests/smoke/run_help.sh
```

内容：

```sh
#!/usr/bin/env sh
set -eu

memu="$1"
"$memu" --help >/dev/null
"$memu" --version >/dev/null
```

给脚本加执行权限：

```sh
chmod +x tests/smoke/run_help.sh
```

### Checkpoint 3

运行：

```sh
ctest --test-dir build --output-on-failure
```

预期看到类似：

```text
100% tests passed
```

如果 CTest 找不到测试，检查：

- `enable_testing()` 是否在 `CMakeLists.txt` 中。
- `add_test()` 是否写在顶层。
- 是否在配置后又修改了 CMake，需要重新运行 `cmake -S . -B build`。

## 1.8 第五个文件：根目录 README

根目录 `README.md` 不要太长，只写：

- MEMU 是什么。
- 当前阶段能做什么。
- 如何构建。
- 如何运行测试。

示例结构：

```md
# MEMU

MEMU is a small educational emulator inspired by NEMU.

## Build

cmake -S . -B build
cmake --build build

## Test

ctest --test-dir build --output-on-failure
```

## 1.9 让 LLM 做本章时怎么说

可以这样给 LLM 任务：

```text
请根据 docs/textbook/chapter-01-project-skeleton.md 实现 Stage 0。
只创建 CMakeLists.txt、src/main.c、include/memu/common.h、
tests/smoke/run_help.sh 和根 README.md。
不要实现 CPU、memory、loader、debugger。
实现后运行 cmake、build、memu --help 和 ctest。
```

这段提示很重要。没有“不要实现 CPU”这句话，LLM 很容易提前铺很多空架子。

## 1.10 常见错误和诊断

### CMake 找不到 `src/main.c`

说明文件还没创建，或者路径写错。

### 测试脚本 Permission denied

运行：

```sh
chmod +x tests/smoke/run_help.sh
```

### `ctest` 显示 No tests were found

通常是修改 CMake 后没有重新配置：

```sh
cmake -S . -B build
```

### macOS 上 shell 脚本行为和 Linux 不同

本项目 smoke test 使用 `/usr/bin/env sh`，不要使用 bash-only 特性。

## 1.11 必答题

请回答：

1. 为什么 Stage 0 不实现 CPU？
2. 为什么第一版 monitor 不使用 readline？
3. 为什么 smoke test 只测试 `--help` 和 `--version` 也有意义？
4. 如果 `common.h` 包含所有模块头文件，会有什么后果？

## 1.12 本章完成标准

本章结束时，以下命令必须通过：

```sh
cmake -S . -B build
cmake --build build
./build/memu --help
./build/memu --version
ctest --test-dir build --output-on-failure
```

通过后，你才进入 Chapter 2。
