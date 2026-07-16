# MEMU NEMU Compatibility Target

这份文档定义 MEMU 的最终验收目标：MEMU 不是只运行几个自制 demo 的玩具 emulator，而是要沿着 NEMU PA 的 riscv32 路线，逐步运行 NEMU PA 软件栈中具有代表性的程序。

## 目标边界

NEMU 支持多种 ISA，PA 课程中常见路线包括 x86、mips32、riscv32/riscv64。MEMU 第一阶段不追求同时兼容所有 ISA；它的兼容目标是：

```text
host: macOS
guest ISA: riscv32
guest software stack: AM / am-kernels / Nanos-lite / Navy-apps
```

也就是说，“达到 NEMU 的要求”在 MEMU 里先解释为：

1. 能加载并运行 NEMU PA riscv32 路线会生成的裸机程序。
2. 能运行 `am-kernels` 中用于检验 CPU、TRM、IO 的测试。
3. 能支撑 Nanos-lite 的 loader、syscall、ramdisk、文件系统。
4. 能运行 Navy-apps 中依赖 NDL、miniSDL、libc 子集的代表性应用。
5. 最终能跑到类似 PAL/仙剑奇侠传这样的综合应用。

如果将来要支持 `riscv64`、x86 或 mips32，应作为新的 ISA track，而不是把第一条 riscv32 主线拖复杂。

## 为什么要单独定义兼容性目标

前 8 个 stage 解决的是“从零理解并实现一台计算机”的教学路线。它们会让 MEMU 拥有 CPU、内存、loader、设备、syscall、文件系统、多任务和虚存这些模块。

但 stage 做完不等于自然兼容 NEMU 软件包。真实兼容还需要面对很多工程细节：

- AM 程序对启动约定、trap 约定、设备地址有明确期待。
- `cpu-tests` 会覆盖很多平时 demo 不会踩到的指令角落。
- Nanos-lite 不只需要 syscall，还需要 loader、ramdisk、资源打包和进程入口约定。
- Navy-apps 会把 libc、NDL、miniSDL、事件、framebuffer、timer 和文件系统串在一起。
- PAL 这类程序会同时考验正确性、性能、输入、显示和文件访问。

所以 MEMU 需要在教学主线之后加一条“兼容性收口线”。这条线不引入全新的计算机概念，而是把前面实现过的模块打磨到能承载 NEMU PA 软件栈。

## 软件包验收表

| 兼容层级 | 参考 NEMU 软件包 | MEMU 需要具备的能力 | 通过标准 |
| --- | --- | --- | --- |
| CPU 基础 | `am-kernels/tests/cpu-tests` | RV32I 指令、寄存器、内存访问、分支跳转、trap | 常用 cpu-tests 全部通过；失败时能定位到具体指令 |
| 裸机运行时 | `abstract-machine` 示例、`am-kernels/kernels/hello` | 启动入口、栈、halt/trap、putch | hello 类程序能稳定输出并退出 |
| AM IO | `am-kernels/tests/am-tests` | timer、keyboard、framebuffer、serial 的 AM 抽象 | timer/display/input 相关测试可运行 |
| 批处理 OS | `nanos-lite` 基础程序 | ELF loader、syscall、进程入口、用户栈 | 能加载用户程序并处理 `exit/write/brk` 等基础 syscall |
| 文件系统 | `nanos-lite` ramdisk、fixed file table | ramdisk、open/read/write/lseek/close | 用户程序能读取打包资源和普通文件 |
| Navy 基础库 | `navy-apps/libs/libos`, `libc`, `libndl` | libc 子集、NDL event/timer/canvas API | 小型 Navy app 能运行 |
| miniSDL 应用 | `navy-apps/libs/libminiSDL`，如 `NSlider` | surface、blit、update rect、事件循环 | `NSlider` 这类图形 demo 可交互运行 |
| 综合应用 | PAL/仙剑奇侠传等 | 稳定 CPU、文件系统、timer、keyboard、framebuffer、性能 | 游戏进入主循环，可显示、响应按键、读资源 |

音频可以作为后续增强项。若某个目标应用在 NEMU PA 中把音频作为可选模块，MEMU 可以先做到无音频可玩，再补音频设备。

## 与 MEMU Stage 的对应关系

| MEMU 阶段 | 建议兼容目标 |
| --- | --- |
| Stage 3: RV32I 指令执行 | 先跑自制指令测试，再对齐 `cpu-tests` 的子集 |
| Stage 4: runtime/loader/tests | 跑 AM hello、dummy、yield 类裸机程序 |
| Stage 5: devices/AM | 跑 timer、keyboard、display 相关 AM tests |
| Stage 6: syscall/batch | 跑 Nanos-lite 最小用户程序 |
| Stage 7: filesystem/apps | 跑依赖文件系统的 Navy 小程序 |
| Stage 8: multiprogramming/vmem/interrupts | 跑上下文切换、timer interrupt、虚存相关测试 |
| Compatibility Track | 把上述软件包按 NEMU PA 的真实构建产物逐个跑通 |

## 兼容性 Track

Stage 0-8 是学习主线；Compatibility Track 是收口主线。建议拆成 5 个阶段，
与 `docs/roadmap.md` 和教材第 10 章保持一致。

### C1: AM 和 cpu-tests 兼容

目标：MEMU 能运行由 NEMU PA 工具链为 riscv32 生成的 AM 裸机程序。

要做的事：

1. 明确 MEMU 支持的 image 格式：raw binary 与 ELF 至少支持一种，建议两者都支持。
2. 明确 guest 物理内存布局：`CONFIG_MBASE`、内存大小、程序加载地址需要和构建产物一致。
3. 对齐 trap 约定：AM 的 halt/trap 应该能让 MEMU 以清晰状态退出。
4. 跑 `cpu-tests`，按失败指令补齐 RV32I 语义。
5. 建立回归脚本：每次修改 CPU，都自动跑一组指令测试。

验收：

```text
memu --image build/add-riscv32.bin
memu --image build/bit-riscv32.bin
memu --image build/branch-riscv32.bin
```

这些命令里的文件名只是示例，实际名称以 NEMU PA 仓库生成结果为准。关键是 MEMU 不再只跑自己手写的 image，而是能跑 AM 体系生成的测试程序。

常见坑：

- `jal` 和 `jalr` 写回地址错误。
- branch 立即数拼接错误。
- load 的符号扩展错误。
- store 写入宽度错误。
- x0 被写坏。
- trap 后 PC 又多走了一步。

### C2: AM IO 兼容

目标：MEMU 能运行 AM 的 timer、keyboard、display 等设备测试。

要做的事：

1. 对齐 AM 的设备抽象和 guest 地址布局。
2. 实现 timer、keyboard、serial、framebuffer 等 IOE 路径。
3. 验证设备状态读取、输入事件和显示刷新不会破坏 CPU 主循环。
4. 对 bounded AM tests 记录输出、trap 和设备检查结果。

验收：

```text
make pa-am-tests
```

验收标准是 timer、keyboard、display 等真实 AM 测试能够启动并完成各自
的 bounded smoke；音频和 devscan 作为同一层的扩展回归。

### C3: Nanos-lite 兼容

目标：MEMU 能支撑 Nanos-lite 运行基础用户程序。

要做的事：

1. 实现 syscall 分发路径，至少覆盖 `exit`、`write`、`brk`，之后补 `open/read/lseek/close`。
2. 实现用户程序 ELF loader。
3. 建立用户栈和入口跳转规则。
4. 对接 ramdisk 与固定文件表。
5. 在 MEMU 日志里区分 emulator trap、guest syscall、guest fault。

验收：

```text
memu --kernel nanos-lite-riscv32.elf
```

运行后应该看到用户程序输出，并能正常回到 monitor 或退出。

常见坑：

- syscall 参数寄存器约定写错。
- ELF program header 的 `p_offset/p_vaddr/p_filesz/p_memsz` 处理不完整。
- `.bss` 没有清零。
- 用户栈没有按 ABI 对齐。
- `brk` 只返回成功但没有维护 heap 边界，导致后续 malloc 随机坏。

### C4: Navy-apps 和 miniSDL 兼容

目标：MEMU 能运行依赖 NDL 和 miniSDL 的图形应用。

要做的事：

1. 实现 NDL 需要的 timer、event、canvas API。
2. 将 framebuffer MMIO 和显示刷新接到 macOS host 窗口或最小图像输出。
3. 实现 keyboard 事件队列。
4. 完成 libc 常用函数子集，尤其是字符串、内存、格式化输出、文件操作。
5. 跑一个非常小的 Navy app，再跑 `NSlider` 这类图形 demo。

验收：

```text
memu --kernel nanos-lite-riscv32.elf --app nslider
```

实际命令后续由 MEMU 工具链确定。验收标准不是命令字符串，而是：Nanos-lite 能加载 app，app 能打开资源，屏幕能刷新，按键/事件能被 app 感知。

常见坑：

- framebuffer 坐标和 pitch 计算错误。
- guest 像素格式和 host 显示格式不一致。
- 事件读取阻塞策略不对，导致程序卡死或 CPU 空转。
- `read` 返回值语义不对，导致上层库误判 EOF 或错误。
- `printf/sprintf` 子集过弱，库初始化阶段就失败。

### C5: PAL/仙剑兼容

目标：MEMU 跑通一个足够复杂的综合应用，用它作为最终冒烟测试。

要做的事：

1. 跑通资源文件读取。
2. 跑通主循环 timer。
3. 跑通 keyboard 输入。
4. 跑通 framebuffer 绘制。
5. 跑足够长时间，观察是否出现 PC 跑飞、内存越界、图像破碎或文件读取错误。
6. 增加性能统计：指令数、每秒 guest 指令、热点设备访问。

验收：

```text
memu --kernel nanos-lite-riscv32.elf --app pal
```

最低验收：

- 程序进入可见主画面。
- 能响应基本按键。
- 能持续运行至少 5 分钟。
- 退出或重启时 MEMU 不崩溃。
- 日志中没有未解释的非法指令、越界内存访问或 unknown syscall。

更高验收：

- 游戏可完成一段连续流程。
- 画面刷新稳定。
- 输入延迟可接受。
- 若音频实现，音频不会阻塞主循环。

## macOS 上的实践方式

MEMU 的 emulator 本体在 macOS 上开发和运行。但 NEMU PA 的部分软件包默认假设 GNU/Linux 工具链。推荐策略是：

1. MEMU 本体：macOS + clang + CMake。
2. guest 程序：使用 Docker、Lima、UTM 或远程 Linux 环境构建。
3. 构建产物：复制 ELF/raw binary 到 macOS，再交给 MEMU 加载。
4. 长期目标：为 MEMU 增加 `tools/import-nemu-pa-artifact` 脚本，记录每个 artifact 的来源、构建命令和校验信息。

不要为了在 macOS 上硬改 NEMU PA 的所有 Makefile 而打断主线。先把产物跑起来，再逐步改善构建体验。

## Definition of Done

当下面清单全部成立时，MEMU 才能说“达到 NEMU PA riscv32 路线的核心要求”：

- `cpu-tests` 的核心 RV32I 测试通过。
- AM hello/dummy/trap 类程序可运行。
- AM timer、keyboard、framebuffer 测试可运行。
- Nanos-lite 能加载并运行基础用户程序。
- syscall 日志可读，异常路径可定位。
- ramdisk 和固定文件表可用。
- Navy-apps 的至少一个文本程序和一个图形程序可运行。
- `NSlider` 或同等级 miniSDL demo 可运行。
- PAL/仙剑类综合应用进入主循环并可交互。
- 对尚未支持的 NEMU PA 功能有明确列表，而不是静默失败。

这份清单会随着实际接入 NEMU PA 仓库而细化。原则不变：MEMU 的最终目标不是“看起来像 emulator”，而是能真实承载 NEMU PA 软件栈。
