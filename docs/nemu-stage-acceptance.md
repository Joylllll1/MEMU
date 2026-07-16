# NEMU-Aligned Stage Acceptance

这份文档把 MEMU 的每个 stage 和 NEMU PA 的可运行目标对齐。原则是：一个阶段是否完成，不能只看 MEMU 内部模块是否写完，还要看它能不能运行 NEMU PA 在相近位置要求或展示的软件。

严禁把 MEMU 自己生成的 smoke test 当成 NEMU 对齐完成。smoke test 只能证明 local scaffold 存在；stage complete 必须以真实 NEMU PA artifact 或明确记录的 blocker 为准。详细规则见 `docs/nemu-strict-alignment.md`。

## 总体映射

| MEMU Stage | 对应 NEMU PA | NEMU 对齐验收 |
| --- | --- | --- |
| Stage 0 | PA0 | macOS 本体可构建；Linux/Docker/Lima 构建 guest artifact 的路线说清楚 |
| Stage 1 | PA1 最简单的计算机 | raw image、PC、寄存器、内存、trap 跑通；能执行最小 TRM 程序 |
| Stage 2 | PA1 调试基础设施 | monitor、表达式、watchpoint 可用于定位 guest 状态 |
| Stage 3 | PA2 指令执行 | 跑通 `cpu-tests` 的无 IO 子集，至少覆盖算术、访存、分支、跳转 |
| Stage 4 | PA2 运行时与 AM | 跑通 AM hello/dummy/trap，能加载 NEMU PA 构建出的 ELF/raw artifact |
| Stage 5 | PA2 IOE | 跑通 AM IO tests，并能运行 slider、typing-game、demo、Bad Apple、snake、LiteNES/FCEUX 的合理子集 |
| Stage 6 | PA3 Nanos-lite/syscall | 跑通 Nanos-lite 最小批处理和基础 syscall 用户程序 |
| Stage 7 | PA3 文件系统与应用 | 跑通 Navy-apps 简单程序、NSlider、Flappy Bird；PAL 至少进入可见画面 |
| Stage 8 | PA4 多道程序/虚存/中断 | 跑通 `yield-os`、上下文切换、虚存映射、timer interrupt；保持 PA3 应用不回退 |
| Compatibility Track | PA2-PA4 收口 | 按 `docs/nemu-compatibility.md` 把真实 artifact 纳入回归 |

## PA2 在 MEMU 中的边界

NEMU 的 PA2 结束时已经不是“只会算数”的机器。PA2 的后半段完整实现 IOE 后，可以运行一批 AM 程序，包括：

- `am-kernels/kernels/slider`
- `am-kernels/kernels/typing-game`
- `am-kernels/kernels/demo`
- `am-kernels/kernels/bad-apple`
- `am-kernels/kernels/snake`
- `am-kernels/kernels/litenes`
- FCEUX

其中 LiteNES 只能运行超级玛丽，FCEUX 则是更完整的红白机模拟器。声卡相关能力可以先作为增强项；无音频运行游戏和 demo 是第一阶段验收，音频稳定播放是后续验收。

在 MEMU 的 stage 划分里，PA2 被拆成：

```text
Stage 3: RV32I 指令
Stage 4: loader / runtime / AM trap
Stage 5: IOE / devices / AM apps
```

所以“PA2 完成可以跑 Mario”对应 MEMU 的 Stage 5 完成，而不是 Stage 3 完成。

## PA3 在 MEMU 中的边界

PA3 的关键不是再加设备，而是把程序放到一个小 OS 和应用生态中运行。验收重点应从 AM 程序转向：

- Nanos-lite 是否能加载用户程序。
- syscall 参数、返回值、错误路径是否正确。
- ramdisk 和固定文件表是否可用。
- Navy-apps 的 libc、libos、NDL、miniSDL 是否能支撑图形应用。
- NSlider 是否能翻页显示。
- PAL/仙剑是否能进入画面并响应输入。

PA3 阶段的最终综合目标是 PAL 类应用；如果 PAL 未完全跑通，必须明确卡在 miniSDL、文件系统、输入、timer、像素格式还是运行时初始化。

## PA4 在 MEMU 中的边界

PA4 不应该把 PA3 跑通的应用弄坏。它新增的是：

- 多个执行流同时存在。
- 上下文切换。
- 虚存和地址翻译。
- timer interrupt 驱动的抢占。

验收时不仅要跑 `yield-os` 这类小测试，也要确认 Stage 7 已经跑通的 Navy/PAL 目标仍然可运行。否则 PA4 的新机制可能只是“自测能过”，但破坏了真实软件栈。
