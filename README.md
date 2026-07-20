# MEMU

MEMU 的意思是 **My Emulator**。

它是一个参考 NEMU PA 路线实现的教学型 RISC-V 模拟器项目，目标不是做一个尽可能大的模拟器，而是做一个**可逐步实现、可持续阅读、能跑真实 PA 工件**的小型系统。项目主线围绕 `riscv32` 展开，按 `CPU -> memory/MMIO -> AM -> Nanos-lite -> Navy-apps` 这条栈逐层推进。

MEMU 当前的本地教学主线已经实现到 **Stage 8**，覆盖 monitor、RV32I/RV32M/CSR、loader、MMIO 设备、syscall、ramdisk/filesystem、批处理、Sv32 虚存、基础多进程与定时器抢占。真实 PA 兼容性方面，CPU、AM/IOE、AM apps、Nanos-lite、部分 Navy-apps、Sv32/NWM 等关键 gate 已经打通；当前仍有少量宿主交互侧验收项，其中 `pal-sdl` 已可运行，`nwm-sdl` 仍是主要待确认项。

README 只负责说明这个仓库是什么、怎么开始、去哪里看权威状态。更细的阶段进度和兼容性记录请看：

- [`docs/stage-progress.md`](docs/stage-progress.md)
- [`docs/compat-status.md`](docs/compat-status.md)
- [`docs/roadmap.md`](docs/roadmap.md)

## 这个项目适合谁

如果你想要的是下面这几件事，MEMU 是合适的：

- 按照 NEMU PA 的系统路线，自己实现一个小型 emulator。
- 在一个相对小的代码库里理解 CPU、内存、设备、OS runtime 和应用栈是怎么接起来的。
- 用 macOS 作为主要宿主环境，同时逐步对接真实的 PA 构建产物。

如果你只是想要一个“功能尽量全”的现成模拟器，这个仓库并不是那个方向。

## 当前状态

当前仓库可以分成两条线理解：

- **教学主线**：Stage 0 到 Stage 8 已基本建立，适合按章节阅读和继续实验。
- **兼容性主线**：真实 `cpu-tests`、AM tests、AM apps、Nanos-lite、Navy libc hello、NDL/miniSDL 的若干程序、Sv32 VME、NWM event loop/child path 等都已有通过记录。

目前剩余的主要开放项不是新的大阶段，而是宿主相关的交互验收，例如：

- `make pal-sdl`：PAL 已经可以运行，主要作为宿主交互路径的现成入口。
- `make nwm-sdl`：运行 NWM 和 nterm 子窗口。子窗口通过 dirty 通知即时合成，空闲时不再整屏刷新；焦点切换仍需人工验收。

因此，README 不再把自己写成阶段验收清单；以文档里的状态文件为准。

## 环境要求

在 macOS 上，至少准备：

- Apple clang，通常来自 Xcode Command Line Tools：`xcode-select --install`
- CMake 3.20+
- Ninja 或 Make
- SDL2：仅在运行 SDL 交互目标时需要，安装命令为 `brew install sdl2`

RISC-V 交叉工具链不是最开始就必须的。本仓库支持把外部环境中构建出的 guest artifacts 拷回 MEMU 使用；后续如果要跑真实 PA 兼容性目标，通常需要一个可用的 `ICS-PA` checkout 和 `riscv64-unknown-elf-*` 工具链。

## 快速开始

先构建并跑本地回归：

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

日常使用时，Makefile 更直接：

```sh
make
make test
make run
make batch
make help
```

这些命令分别表示：

- `make`：构建 `build/memu`
- `make test`：运行本地回归测试集
- `make run`：载入默认镜像并进入 monitor
- `make batch`：不进入 monitor，直接批量运行默认镜像
- `make help`：查看当前支持的快捷目标

如果想做一次干净重建：

```sh
make clean
make
```

## 最常用的目标

### 本地教学/回归目标

```sh
make expr-test
make rv32i-test
make stage4-test
make stage5-test
make stage6-test
make stage7-test
make stage8-test
make toolchain-test
```

这些目标大致对应：

- `expr-test`：表达式求值与 monitor 相关逻辑
- `rv32i-test`：RV32I/RV32M/CSR 本地指令覆盖
- `stage4-test`：loader、trap、ELF、运行时基础路径
- `stage5-test`：serial/timer/keyboard/framebuffer 等设备
- `stage6-test`：syscall 与 batch-list
- `stage7-test`：ramdisk、filesystem、应用装载
- `stage8-test`：Sv32、页故障、多进程样例与抢占脚手架
- `toolchain-test`：真实交叉工具链生成的 ELF smoke

### 真实 PA 兼容性目标

如果本机 `PA_HOME` 不是默认位置，请显式传入：

```sh
make pa-cpu-tests PA_HOME=/path/to/ICS-PA
make pa-am-tests PA_HOME=/path/to/ICS-PA
make pa-app-tests PA_HOME=/path/to/ICS-PA
make pa-cte-os-tests PA_HOME=/path/to/ICS-PA
make pa-nanos-tests PA_HOME=/path/to/ICS-PA
make pa-nanos-libc-test PA_HOME=/path/to/ICS-PA
make pa-vme-test PA_HOME=/path/to/ICS-PA
```

此外，仓库里还有一些更细的兼容性目标，例如：

```sh
make pa-navy-ndl-test
make pa-ndl-test
make pa-bird-test
make pa-pal-test
make pa-fork-test
make pa-vfork-test
make pa-fd-test
make pa-memfd-test
make pa-nwm-test
make pa-nwm-child-test
```

这些目标的最新通过情况，不要看 README，请看 [`docs/compat-status.md`](docs/compat-status.md)。

## 交互目标

如果你想直接在宿主机上打开窗口体验目前的图形路径，可以使用：

```sh
make mario
make bad-apple-sdl
make snake-sdl
make typing-sdl
make nslider-sdl
make bird-sdl
make pal-sdl
make nwm-sdl
```

说明：

- `make mario` 会构建 SDL 版本 MEMU，并运行 LiteNES/Mario。
- `make pal-sdl` 与 `make nwm-sdl` 是当前路线里仍依赖人工宿主验收的目标；后者会显示带标题栏的 nterm 子窗口，并支持基本字符输入、退格和回车。
- 关闭 SDL 窗口通常就是正常退出。

## Monitor 与运行方式

不带 `--batch` 时，MEMU 会进入 monitor。常用命令包括：

- `help`, `q`, `c`, `si`
- `info r`, `info w`
- `x N EXPR`
- `p EXPR`
- `w EXPR`, `d N`

常见运行方式：

```sh
./build/memu --help
./build/memu --version
./build/memu --self-test --batch
./build/memu --image tests/images/stage1-trap.bin
./build/memu --image tests/images/stage1-trap.bin --batch --dump-regs
./build/memu --elf tests/images/toolchain-basic.elf --batch
./build/memu --ramdisk tests/images/ramdisk.img --run /bin/fs-cat --batch
```

调试开关：

```sh
./build/memu --image tests/images/sys-write.bin --batch --trace-syscall
./build/memu --image tests/images/fb-clear.bin --batch --trace-device
make batch IMAGE=tests/images/rv32i-branch-sum.bin RUN_ARGS=--trace
```

## 项目结构

```text
MEMU/
|- README.md
|- AGENTS.md
|- Makefile
|- CMakeLists.txt
|- include/memu/         公共头文件
|- src/cpu/              CPU 状态与执行循环
|- src/isa/              RV32 指令译码与执行
|- src/memory/           物理内存、MMU、Sv32
|- src/device/           串口、定时器、键盘、帧缓冲、音频、磁盘
|- src/os/               syscall、ramdisk、filesystem、batch runtime
|- src/monitor/          monitor、表达式、watchpoint
|- tests/                本地测试、镜像、脚本
|- tools/                工件生成、PA patch、兼容性运行脚本
`- docs/                 路线图、阶段文档、教材、兼容性记录
```

## 文档阅读顺序

如果你是第一次认真看这个项目，建议按下面顺序读：

1. [`docs/stage-progress.md`](docs/stage-progress.md)
2. [`docs/roadmap.md`](docs/roadmap.md)
3. [`docs/README.md`](docs/README.md)
4. [`docs/textbook/README.md`](docs/textbook/README.md)
5. 对应阶段的 `docs/textbook/chapter-*.md`
6. 对应阶段的 `docs/stages/stage-XX-*.md`
7. [`docs/nemu-stage-acceptance.md`](docs/nemu-stage-acceptance.md)
8. [`docs/nemu-strict-alignment.md`](docs/nemu-strict-alignment.md)
9. 相关 `src/` / `include/` 代码

如果你是要继续做兼容性路线，再补充阅读：

- [`docs/compat-status.md`](docs/compat-status.md)
- [`docs/nemu-compatibility.md`](docs/nemu-compatibility.md)
- [`docs/textbook/chapter-10-nemu-compatibility.md`](docs/textbook/chapter-10-nemu-compatibility.md)

## 一些实现约束

这个仓库默认坚持这些原则：

- 使用 C11。
- 保持代码小、直白、容易继续实验。
- 优先围绕 `riscv32` 主线推进，不并行追多 ISA。
- 本地 smoke pass 不等于 NEMU 对齐完成；严格状态以文档记录为准。
- 外部 PA tree 会复制到临时目录或缓存目录后再 patch，不直接改你的原始 checkout。

## License

仓库里属于 MEMU 的源码和脚本按本项目自身约定维护；外部 PA、ROM、游戏资源或第三方工件不自动包含在“可自由再分发”的范围内。涉及 PAL、ROM、游戏数据等内容时，请只使用你有权合法持有的资源。
