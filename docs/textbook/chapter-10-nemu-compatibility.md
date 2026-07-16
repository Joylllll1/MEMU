# Chapter 10: NEMU PA Compatibility

本章的目标不是再引入一个新的抽象层，而是把前面实现过的 CPU、内存、设备、loader、syscall、文件系统、多任务和虚存，拉到 NEMU PA 软件栈面前接受检验。

如果说 Chapter 2 到 Chapter 9 是“自己造一台逐渐完整的计算机”，那这一章就是“让别人写的软件真的在这台计算机上跑起来”。

## 10.1 本章目标

完成本章后，你应该能回答三个问题：

1. MEMU 当前能运行 NEMU PA 软件栈里的哪些程序？
2. 不能运行的程序，卡在 ISA、AM、syscall、文件系统、设备还是性能？
3. 每次修复一个兼容性问题，是否有回归测试防止它再次坏掉？

本章的最终目标是：

```text
MEMU can run representative riscv32 NEMU PA artifacts:
cpu-tests -> AM tests -> Nanos-lite -> Navy-apps -> PAL-like application
```

注意，这里的兼容性默认指 riscv32 路线。不要同时追 x86、mips32、riscv64。教学项目最怕边界漂移，先把一条线跑穿。

## 10.2 为什么不能只跑自己写的 demo

自己写的 demo 通常会避开很多麻烦：

- 只用你已经实现的那几条指令。
- 不依赖真实 ABI。
- 不依赖复杂 linker script。
- 不做文件读取。
- 不处理事件循环。
- 不要求长时间稳定运行。

NEMU PA 软件栈不会这么客气。`cpu-tests` 会故意覆盖指令角落；AM 会要求你对齐启动、trap 和设备约定；Nanos-lite 会把 loader、syscall、ramdisk 串起来；Navy-apps 会继续要求 libc、NDL、miniSDL 和图形事件。

所以兼容性阶段不是“加几个程序试试”，而是把 MEMU 从实验环境推到更真实的软件生态里。

## 10.3 兼容路线图

本章把兼容性拆成四个 checkpoint：

```text
C1: AM + cpu-tests
C2: AM IO tests
C3: Nanos-lite
C4: Navy-apps + miniSDL
C5: PAL / 仙剑类综合应用
```

每个 checkpoint 都应该留下三样东西：

1. 运行命令或脚本。
2. 成功输出的记录。
3. 如果失败，最小复现 artifact 和定位笔记。

建议在项目里创建：

```text
tests/compat/
  README.md
  artifacts/
  scripts/
  logs/
```

其中：

- `artifacts/` 放从 NEMU PA/Linux 环境构建出来的 ELF 或 raw binary。
- `scripts/` 放 MEMU 的运行脚本。
- `logs/` 放失败样例和已知问题。

不要把大体积资源文件直接塞进 git。PAL 资源这类文件可以用下载脚本或本地路径说明管理。

## 10.4 准备 Linux 构建环境

MEMU 在 macOS 开发，但 NEMU PA 的软件包默认面向 GNU/Linux 环境。你可以选择 Docker、Lima、UTM 或远程 Linux 主机。关键是把“构建 guest 程序”和“运行 MEMU”分开：

```text
Linux environment:
  build AM / am-kernels / nanos-lite / navy-apps artifacts

macOS:
  run MEMU with those artifacts
```

推荐目录约定：

```text
~/Projects/
  MEMU/
  nemu-pa-workspace/
```

`nemu-pa-workspace` 用来放官方 PA 相关仓库或课程提供的代码。MEMU 不应该直接复制大段 NEMU 源码；它只需要读取构建产物，并根据公开约定实现兼容接口。

必答题：

1. 为什么 emulator 可以在 macOS 运行，但 guest 程序仍然需要 Linux 工具链构建？
2. 如果一个 ELF 在 Linux 构建，MEMU 在 macOS 加载，哪些信息必须保持一致？
3. linker script 的加载地址和 MEMU 的物理内存基地址有什么关系？

## 10.5 C1: 运行 cpu-tests

`cpu-tests` 是最适合做第一批兼容测试的程序。它们小、目标明确、失败时容易定位。

### 你要先确认什么

在运行 `cpu-tests` 前，先确认 MEMU 已经具备：

- raw binary 或 ELF loader。
- RV32I 基础整数指令。
- load/store 的 byte、half、word 支持。
- branch/jump 支持。
- trap/halt 支持。
- 指令 trace 或至少 PC trace。

如果这些还没有，不要直接跑大型程序。先回到 Chapter 4 和 Chapter 5。

### 建议任务

任务 1：建立 artifact 记录文件。

创建：

```text
tests/compat/README.md
```

记录每个测试 artifact：

```text
name: add
source: am-kernels/tests/cpu-tests
arch: riscv32
format: ELF or raw binary
build_env: Linux / Docker / Lima
build_command: ...
memu_command: ...
expected_result: HIT GOOD TRAP or equivalent
```

任务 2：先挑 3 个最小测试。

建议顺序：

```text
add
shift
branch
```

不要第一次就全跑。一个 emulator 同时失败 40 个测试时，日志会变成噪音。

任务 3：为每个失败建立定位笔记。

笔记格式：

```text
symptom:
  PC reaches 0x...

first_bad_instruction:
  pc=...
  inst=...
  decoded_as=...

expected:
  ...

actual:
  ...

fix:
  ...

regression:
  tests/compat/scripts/run-cpu-add.sh
```

### 怎么验证

每个测试都应该能独立运行：

```text
build/memu --image tests/compat/artifacts/add-riscv32.elf
```

成功标准：

- 程序到达 good trap。
- MEMU 退出码可被脚本判断。
- 日志里没有 unknown instruction。
- 如果打开 itrace，最后 20 条指令能解释为什么到达 trap。

### 常见坑

- `srai` 和 `srli` 混淆。
- `sltiu` 的立即数符号扩展做错。
- `auipc` 使用了错误的 PC。
- `jalr` 没有清除最低位。
- `lb/lh` 没有符号扩展，`lbu/lhu` 又错误地符号扩展。
- store 指令立即数拼接顺序写错。
- x0 写保护只在部分路径生效。

## 10.6 C2: 运行 AM IO tests

当 `cpu-tests` 稳定后，开始跑 AM 层测试。AM 会开始检查“机器”而不是只检查“CPU”。

### 你要实现的接口

至少需要：

- `putch` 或 serial 输出。
- `halt` 或 trap。
- `uptime` 或 timer。
- keyboard 事件读取。
- framebuffer 写入。

这些接口在 MEMU 内部可以是 MMIO，也可以先做成更简单的 host 回调。但对 guest 来说，行为要像一台有设备的机器。

### 建议任务

任务 1：先跑 hello/dummy。

如果 hello 都不能跑，不要碰图形。

任务 2：跑 timer test。

timer 失败通常有两类：

- 时间单位错了。
- guest 读 timer 时看到的值不单调。

任务 3：跑 keyboard test。

在 macOS 上你需要决定输入来源：

- 先用 terminal stdin 模拟按键。
- 之后再用 SDL 或 Cocoa 窗口事件。

任务 4：跑 display test。

先允许最朴素的显示策略：

- guest 写 framebuffer。
- MEMU 定期把 framebuffer dump 成 PPM。
- 确认图像正确后，再接实时窗口。

### 怎么验证

成功标准：

- hello 输出完整字符串。
- timer 测试能看到递增时间。
- keyboard 测试能读到按下和释放事件。
- display 测试能产生可检查的图像。

### 常见坑

- MMIO 地址范围和普通内存重叠。
- 设备读取有副作用，但实现成了普通内存读取。
- framebuffer 的宽高来自 guest 配置，但 host 侧写死。
- 键盘事件没有区分 keydown/keyup。
- timer 使用 wall clock 时被 host sleep 或调试断点影响，导致测试不稳定。

## 10.7 C3: 运行 Nanos-lite

Nanos-lite 是本章的分水岭。从这里开始，MEMU 不再只是跑裸机程序，而是跑一个小 OS。

### 你要先确认什么

MEMU 需要支持：

- ELF loader。
- 用户程序入口。
- guest 栈初始化。
- syscall 分发。
- ramdisk。
- 基础文件表。

Nanos-lite 侧通常包含 loader、syscall、fs、ramdisk、proc 等模块。MEMU 不需要复制它们，但必须提供它们期待的机器行为。

### 建议任务

任务 1：只运行一个最小用户程序。

这个程序只做：

```c
write(1, "hello\n", 6);
exit(0);
```

如果它失败，优先检查 syscall 参数和返回值。

任务 2：加入 `brk`。

很多 libc 初始化或 malloc 会依赖 `brk`。即使先做一个简化版本，也要维护 heap 边界，不要永远假装成功。

任务 3：加入文件 syscall。

顺序：

```text
open -> read -> lseek -> close
```

`write` 先支持 stdout/stderr，再支持特殊设备文件。

任务 4：接入 ramdisk。

先用一个小文本文件做资源，确认用户程序能读到正确内容。再接入真实 Navy-apps 资源。

### 怎么验证

成功标准：

- Nanos-lite 能打印启动信息。
- 用户程序能输出文本。
- 用户程序调用 exit 后，MEMU 能给出明确退出原因。
- 文件读取结果和 host 侧原文件一致。

### 常见坑

- ELF 的虚拟地址没有正确映射到 guest 物理地址。
- `p_memsz > p_filesz` 的部分没有清零。
- syscall number 和参数寄存器使用错。
- `read` 到文件末尾时返回值错误。
- `lseek` 没有限制边界。
- stdout 写入路径和 framebuffer 设备路径混在一起。

## 10.8 C4: 运行 Navy-apps 和 miniSDL

Navy-apps 是应用层生态。这里的问题会比 Nanos-lite 更杂，因为应用会同时依赖 libc、libos、libndl、miniSDL、文件系统、timer 和事件。

### 先跑小程序

不要一上来跑 PAL。建议顺序：

```text
文本 hello app
读取文件的小 app
timer app
event app
简单 framebuffer app
NSlider
PAL
```

每个小程序都应该只测试一个方向。这样 PAL 失败时，你知道它更可能卡在哪层。

### miniSDL 最小需求

为了跑图形 demo，通常需要：

- 初始化 video。
- 创建 surface。
- 像素复制或 blit。
- 刷新 rectangle。
- 轮询事件。
- 读取 ticks。

不要一开始就实现完整 SDL。先做 Navy-apps 需要的最小子集。

### 怎么验证

对于 `NSlider` 这类程序，成功标准是：

- 窗口或 framebuffer 有稳定画面。
- 画面刷新没有明显撕裂或错位。
- 键盘事件能改变程序状态。
- 程序能持续运行，不会几秒后 trap。

对于 PAL 类程序，最低成功标准是：

- 能进入可见主画面。
- 能读取资源。
- 能响应基本按键。
- 能持续运行至少 5 分钟。

### 常见坑

- libc 的 `memmove` 没有正确处理重叠区域。
- `sprintf` 格式支持不足，导致路径或日志字符串生成错误。
- framebuffer 像素格式不匹配。
- event poll 语义错误，导致应用误以为没有输入或一直忙等。
- timer 精度太低，动画和输入体验很差。
- 文件系统路径处理和 Navy-apps 预期不一致。

## 10.9 建立兼容性仪表盘

兼容目标变多后，必须有一张表。建议创建：

```text
docs/compat-status.md
```

格式：

```markdown
| Program | Layer | Status | Last Run | Notes |
| --- | --- | --- | --- | --- |
| cpu-tests/add | CPU | pass | 2026-07-14 | - |
| cpu-tests/branch | CPU | fail | 2026-07-14 | jalr target wrong |
```

状态只用四种：

```text
not-started
blocked
fail
pass
```

不要写“差不多能跑”。emulator 的世界里，“差不多”通常等于还有一个难定位的 bug。

## 10.10 和 LLM 协作的提示

这一章特别适合让 LLM 做小范围定位，但不适合给它一个大而空的目标。

坏提示：

```text
帮我兼容 NEMU。
```

好提示：

```text
当前 MEMU 运行 cpu-tests/branch 失败。
请只阅读 src/isa/riscv32/decode.c、src/isa/riscv32/exec.c 和失败日志。
重点检查 B-type immediate 拼接、符号扩展和 PC 更新。
不要改 loader、memory 或 debugger。
修复后运行 tests/compat/scripts/run-cpu-branch.sh。
```

另一个好提示：

```text
Nanos-lite 用户程序调用 write(1, buf, len) 后没有输出。
请检查 syscall 分发和 a0/a1/a2 参数传递。
不要重构 syscall 表。
需要给出一个最小回归测试。
```

## 10.11 本章验收

完成本章时，至少要提交：

1. `docs/compat-status.md`。
2. 一组 `tests/compat/scripts/run-*.sh`。
3. 至少 5 个通过的 cpu-tests。
4. 至少 1 个 AM hello/trap 程序。
5. 至少 1 个 timer 或 display 测试。
6. 至少 1 个 Nanos-lite 用户程序。
7. 至少 1 个 Navy-apps 小程序。
8. PAL/仙剑类应用的当前状态记录，即使还没完全跑通，也要说明卡在哪一层。

当这些都完成后，MEMU 才算从“按课程章节实现 emulator”进入“对齐 NEMU PA 软件栈”的阶段。
