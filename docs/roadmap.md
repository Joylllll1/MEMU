# MEMU Roadmap

## 项目目标

MEMU 的目标是参考 NEMU PA 路线，用 LLM 从零实现一个教学型 emulator。它应该足够小，适合持续阅读和修改；也要足够完整，能支撑裸机程序、简单运行时、设备、系统调用、文件系统、多任务实验，并最终运行 NEMU PA riscv32 路线中的代表性软件包。

这里的“最终运行 NEMU 能运行的东西”，先限定为：

```text
guest ISA: riscv32
software stack: AM -> am-kernels -> Nanos-lite -> Navy-apps -> PAL-like app
host: macOS
```

MEMU 不在第一条路线里同时追 x86、mips32、riscv64。先把 riscv32 路线跑穿，再扩 ISA。

## 与 NEMU PA 的对应关系

NEMU GitBook 的主线是：PA0 配置环境，PA1 最简单的计算机和简易调试器，PA2 冯诺依曼计算机系统、运行时和 IO，PA3 批处理系统、系统调用和文件系统，PA4 分时多任务、虚存和中断。MEMU 将它改写为以下 stages：

| MEMU Stage | 参考 NEMU | 主题 | 结束时应该得到什么 |
| --- | --- | --- | --- |
| Stage 0 | PA0 | 项目和环境 | 可构建、可测试、文档清楚的空 emulator 项目 |
| Stage 1 | PA1 | 最小计算机 TRM | 内存、寄存器、PC、取指执行循环和 halt |
| Stage 2 | PA1 | 简易调试器 | `help/c/q/si/info r/x/p/w` 的基础能力 |
| Stage 3 | PA2 | RV32I 指令执行 | 覆盖常用 RV32I 指令，能跑指令测试 |
| Stage 4 | PA2 | 程序、运行时、测试 | raw/ELF loader、trap、trace、测试集 |
| Stage 5 | PA2 | IO 与 AM | serial、timer、keyboard、framebuffer 的最小 MMIO 模型 |
| Stage 6 | PA3 | syscall 与批处理 | 用户程序可通过 syscall 退出、输出、切换到下一个程序 |
| Stage 7 | PA3 | 文件系统与应用 | ramdisk、固定文件表、read/write/lseek，跑更多小程序 |
| Stage 8 | PA4 | 多任务、虚存、中断 | 上下文切换、页表、timer interrupt 的教学实现 |

## NEMU 兼容性收口线

Stage 0-8 是教学主线；它们保证你理解并实现每一层抽象。完成 Stage 8 后，还要进入兼容性收口线，目标是运行 NEMU PA riscv32 软件栈中的真实构建产物。

| Compatibility Stage | 对齐对象 | 目标 |
| --- | --- | --- |
| C1 | `am-kernels/tests/cpu-tests`、AM hello/dummy | 跑通 RV32I 指令测试和最小裸机运行时 |
| C2 | `am-kernels/tests/am-tests` | 跑通 timer、keyboard、display 等 AM 设备测试 |
| C3 | `nanos-lite` | 跑通 loader、syscall、ramdisk、基础用户程序 |
| C4 | `navy-apps`、NDL、miniSDL | 跑通文本/图形 Navy 小程序，例如 `NSlider` |
| C5 | PAL/仙剑类综合应用 | 跑通复杂应用的主循环、显示、输入、资源读取 |

详细要求见：

```text
docs/nemu-stage-acceptance.md
docs/nemu-compatibility.md
docs/textbook/chapter-10-nemu-compatibility.md
```

## 推进原则

每个 stage 必须有明确的完成标准。不要为了“像 NEMU”而过早加入复杂抽象；要先让当前系统跑起来，再把下一层抽象接上来。

代码实现时采用以下默认选择：

- 语言：C11。
- 构建：CMake，优先兼容 macOS clang。
- ISA：RV32I 起步，必要时补 RV32M、CSR 和异常相关机制。
- 内存模型：先从一段连续物理内存开始。
- 设备模型：先用 memory mapped IO，不实现 port IO。
- 测试：每个阶段至少有一个 smoke test 和一个失败时可定位的日志。
- 兼容：最终以 NEMU PA riscv32 软件栈的实际 artifact 作为验收，而不是只跑 MEMU 自己写的 demo。

## macOS 与 Linux 的分工

MEMU 本体在 macOS 上开发和运行。NEMU PA 的 guest 程序构建可以先放在 Linux、Docker、Lima、UTM 或远程环境里完成。

推荐分工：

| 环境 | 负责什么 |
| --- | --- |
| macOS | 开发 MEMU、运行 MEMU、调试 emulator |
| Linux/toolchain | 构建 AM、am-kernels、Nanos-lite、Navy-apps |
| MEMU compat scripts | 记录 artifact 来源并运行回归 |

不要为了让所有 NEMU PA Makefile 原样跑在 macOS 上而拖慢主线。先拿到 guest artifact，让 MEMU 能加载并执行；之后再优化构建体验。

## 什么时候进入下一阶段

只有当当前 stage 的 `怎么验证` 全部通过，并且你能用自己的话解释“这个 stage 加入了哪一层计算机系统抽象”时，才进入下一阶段。

如果验证失败，先检查：

- PC 是否更新正确。
- 指令长度和对齐是否正确。
- 大小端是否正确。
- 符号扩展是否正确。
- x0 是否保持为 0。
- 内存越界是否被检查。
- trap/halt 是否被明确区分。

## 什么时候说 MEMU 达到了 NEMU PA 核心要求

当下面目标都完成时，MEMU 才算达到第一条路线的核心要求：

- `cpu-tests` 的核心 RV32I 测试通过。
- AM hello/dummy/trap 程序可运行。
- AM timer、keyboard、framebuffer 测试可运行。
- Nanos-lite 能加载并运行基础用户程序。
- syscall、loader、ramdisk、固定文件表行为稳定。
- Navy-apps 的至少一个文本程序和一个图形程序可运行。
- `NSlider` 或同等级 miniSDL demo 可交互运行。
- PAL/仙剑类综合应用能进入主循环，显示画面，响应按键，读取资源。
- 所有未支持项都有明确记录，而不是静默失败。
