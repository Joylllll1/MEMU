# Stage 0: 项目骨架与开发环境

## 参考 NEMU 的位置

对应 NEMU PA0。PA0 的重点不是 emulator 本身，而是把开发环境、工具链、阅读方式和求助方式准备好。MEMU 在 macOS 上做，因此不会照搬 GNU/Linux 环境，但保留“工具先行、验证先行”的思想。

## 为什么做

emulator 后面会迅速变复杂。如果没有稳定的构建、测试、日志和文档结构，后续每一个 bug 都会变成猜谜。Stage 0 的任务是让仓库变成一个可以长期迭代的工程。

## 要实现什么

- 建立 CMake + C11 项目。
- 建立 `src/`、`include/`、`tests/`、`docs/`、`tools/` 目录。
- 提供一个能运行的 `memu` 空程序。
- 提供统一的日志、断言和错误退出风格。
- 写清楚 macOS 上需要的工具：clang、cmake、ninja 或 make、可选的 riscv toolchain。

## 怎么做

1. 创建 `CMakeLists.txt`，设置 C11 和 warning 选项。
2. 创建 `src/main.c`，先只解析 `--help` 和 `--version`。
3. 创建 `include/memu/common.h`，放公共 typedef、panic、assert 宏。
4. 创建 `tests/`，先放一个最小 smoke test 脚本。
5. 创建根目录 `README.md`，说明 MEMU 是什么、怎么构建、怎么运行。

## 怎么验证

```sh
cmake -S . -B build
cmake --build build
./build/memu --help
ctest --test-dir build --output-on-failure
```

期望结果：

- 构建无 error。
- `memu --help` 能打印帮助信息。
- smoke test 通过。

## 常见坑

- macOS 默认没有 GNU readline，Stage 2 前不要强依赖它。
- 不要在 Stage 0 引入 SDL、ELF、RISC-V 工具链等大依赖。
- 不要把所有代码写进 `main.c`，但也不要过度抽象。
- CMake 的输出目录要固定，避免文档里的命令每次不同。

## 给 LLM 的提示

请先创建最小可构建项目，不要实现 CPU。只允许加入项目结构、构建系统、日志和一个空 CLI。完成后必须运行构建命令和 smoke test。

## 和 NEMU 对齐的验收

对应 NEMU PA0。这个阶段还不要求运行 NEMU 软件包，但必须把后续运行 NEMU PA artifact 的路线准备好：

- macOS 上能构建和运行 MEMU 本体。
- 文档写明 guest 程序可能需要 Linux、Docker、Lima、UTM 或远程环境构建。
- `docs/` 中能找到 stage 文档、textbook 和 NEMU 兼容性目标。
- 后续 artifact 应该放到哪里、如何记录构建命令，需要有约定。

## 完成标准

- 仓库可以从干净状态构建。
- 用户能通过 `README.md` 完成第一次运行。
- 后续 stage 有明确目录可放代码和测试。
