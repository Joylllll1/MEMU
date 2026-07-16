# Chapter 6: MMIO、设备与 mini AM

## 6.1 为什么需要设备

到目前为止，guest 程序只能计算，然后通过 trap 告诉 MEMU 成功或失败。这样的机器已经能跑测试，但还不能和外界交互。

真实计算机需要输入输出：

- 输出字符。
- 读取时间。
- 接收键盘输入。
- 显示图像。

本章先实现最小设备模型，让 guest 能输出字符和读取时间。键盘和 framebuffer 先做教学版接口，不急着开窗口。

## 6.2 本章结束时应该看到什么

你应该能运行：

```sh
./build/memu --image tests/images/hello-serial.bin --batch
./build/memu --image tests/images/timer.bin --batch
./build/memu --image tests/images/fb-smoke.bin --batch
```

并看到：

```text
Hello, MEMU
HIT GOOD TRAP
```

timer 测试应能读到非零且单调递增的时间。

## 6.3 新增模块

```text
include/
  memu/
    device.h
    mmio.h
src/
  device/
    device.c
    serial.c
    timer.c
    keyboard.c
    framebuffer.c
  memory/
    mmio.c
guest/
  am/
    memu.h
    memu.c
```

`guest/am` 是给 guest 程序用的小库。它不是 host 代码，后面会用 RISC-V 工具链编译。

## 6.4 第一件事：MMIO 的概念

MMIO 是 memory mapped I/O。CPU 看起来还是在读写地址，但某些地址不对应普通内存，而是设备寄存器。

例如：

```text
0x80000000 - 0x87ffffff  普通内存
0xa0000000 - 0xa0000fff  设备寄存器
```

当 guest 执行：

```asm
sw a0, 0(t0)
```

如果 `t0` 是普通内存地址，就写 `pmem`。如果 `t0` 是 serial 地址，就输出字符。

## 6.5 第二件事：MMIO map

定义：

```c
typedef uint32_t (*MMIORead)(uint32_t addr, int len);
typedef void (*MMIOWrite)(uint32_t addr, int len, uint32_t data);

typedef struct {
  const char *name;
  uint32_t base;
  uint32_t size;
  MMIORead read;
  MMIOWrite write;
} MMIOMap;
```

接口：

```c
void mmio_init(void);
void mmio_add(const char *name, uint32_t base, uint32_t size,
              MMIORead read, MMIOWrite write);
bool mmio_contains(uint32_t addr, int len);
uint32_t mmio_read(uint32_t addr, int len);
void mmio_write(uint32_t addr, int len, uint32_t data);
```

修改 `mem_read()` 和 `mem_write()`：

```text
如果地址属于 MMIO -> 调用设备
否则 -> 普通 pmem
```

### Checkpoint 1

先注册一个 fake device：

```text
base = 0xa0000000
size = 4
write 时打印 data
```

用测试程序写这个地址，应看到 host 输出。

## 6.6 第三件事：serial 设备

约定：

```text
SERIAL_BASE = 0xa00003f8
SERIAL_SIZE = 8
```

最小行为：

```text
写 SERIAL_BASE 的低 8 位 -> putchar
```

实现：

```c
static void serial_write(uint32_t addr, int len, uint32_t data) {
  (void)addr;
  (void)len;
  putchar(data & 0xff);
  fflush(stdout);
}
```

### Checkpoint 2

guest 程序写：

```text
'H' 'i' '\n'
```

运行：

```sh
./build/memu --image tests/images/hello-serial.bin --batch
```

预期：

```text
Hi
HIT GOOD TRAP
```

如果字符不出现，检查：

- 地址是否落入 MMIO。
- store byte/word 是否都能触发 serial。
- stdout 是否 flush。

## 6.7 第四件事：timer 设备

约定：

```text
RTC_BASE      = 0xa0000048
RTC_LOW       = RTC_BASE
RTC_HIGH      = RTC_BASE + 4
```

返回 host monotonic time，单位可以是微秒。

macOS 上可以用：

```c
clock_gettime(CLOCK_MONOTONIC, &ts)
```

如果你的 macOS 目标环境不支持，换成 `mach_absolute_time()`，但先优先标准接口。

读取：

```text
RTC_LOW  -> time_us low 32 bits
RTC_HIGH -> time_us high 32 bits
```

### Checkpoint 3

guest 连续读两次 timer：

```text
t1 = uptime()
t2 = uptime()
assert(t2 >= t1)
```

预期 good trap。

## 6.8 第五件事：keyboard 设备

本章先做最小接口，不要求真实键盘事件。

约定：

```text
KBD_BASE = 0xa0000060
```

行为：

- batch 模式：读到 0，表示没有按键。
- 交互模式：可以后续从 host 输入队列取事件。

现在只要保证读 keyboard 不崩溃。

### Checkpoint 4

guest 读取 keyboard 寄存器，得到 0，然后 good trap。

## 6.9 第六件事：framebuffer 教学版

先定义：

```text
FB_BASE   = 0xa1000000
FB_WIDTH  = 400
FB_HEIGHT = 300
FB_BYTES  = width * height * 4
```

guest 写 framebuffer 时，MEMU 只写一个 host buffer，不开窗口。

另外定义一个 sync 寄存器：

```text
FB_SYNC = 0xa0000100
```

guest 写 `FB_SYNC` 时，MEMU 打印 framebuffer checksum：

```text
fb checksum = 0x...
```

这样可以验证 guest 确实写了图像。

### Checkpoint 5

guest 清屏为某种颜色，然后写 sync。MEMU 输出 checksum 并 good trap。

## 6.10 第七件事：mini AM

直接在 guest 程序里散落 MMIO 地址不利于维护。建立一个很小的 guest 侧 AM：

```c
void halt(int code);
void putch(char ch);
uint64_t uptime(void);
void fb_write(int x, int y, uint32_t color);
```

例如：

```c
void putch(char ch) {
  *(volatile uint8_t *)SERIAL_BASE = ch;
}
```

注意：这是 guest 代码。它会被编译成 RISC-V，然后在 MEMU 里运行。

## 6.11 设备 trace

加入可选日志：

```sh
./build/memu --image hello.bin --batch --trace-device
```

输出：

```text
device write serial addr=0xa00003f8 data=0x48
device read rtc_low addr=0xa0000048 data=...
```

默认关闭，否则输出太多。

## 6.12 常见坑

### 普通内存和 MMIO 重叠

如果 `MEMU_MEM_SIZE` 太大，把 `0xa0000000` 包进普通内存范围，设备永远不会触发。检查内存范围。

### store word 到 serial 输出多个字符吗

先定义清楚。建议无论 len 是 1 还是 4，只输出最低 8 位。后续需要更精细再扩展。

### timer 不单调

检查 high/low 读取是否跨越了 32-bit 溢出。第一版测试只要求 `t2 >= t1`，避免复杂一致性问题。

### framebuffer 地址太大

`FB_BASE` 不属于普通 memory，所以必须被 MMIO 捕获。

## 6.13 必答题

1. 为什么设备可以通过访存指令访问？
2. MMIO 和普通内存的分发应该放在指令实现里，还是 `mem_read/mem_write` 里？
3. serial 为什么需要 flush？
4. timer 应该基于 host time，还是 guest 指令数？两者有什么差别？
5. mini AM 为什么是 guest 侧库，而不是 host 侧库？

## 6.14 给 LLM 的提示

建议分任务：

```text
1. 实现 MMIO map，并接入 mem_read/mem_write。
2. 实现 serial，跑 hello-serial。
3. 实现 timer，跑 timer smoke test。
4. 实现 keyboard stub 和 framebuffer checksum。
5. 写 mini AM 头文件和 guest 示例。
```

不要一开始接 SDL。先把设备模型跑通。

## 6.15 本章完成标准

必须通过：

```sh
./build/memu --image tests/images/hello-serial.bin --batch
./build/memu --image tests/images/timer.bin --batch
./build/memu --image tests/images/fb-smoke.bin --batch
```

并且：

- serial 能输出字符。
- timer 单调。
- framebuffer 写入可通过 checksum 验证。
- 普通内存测试没有回归。

通过后进入 Chapter 7。下一章会让 guest 通过 `ecall` 请求 OS 服务。

## 6.16 NEMU PA2 对齐路线

本章对应 NEMU PA2 的 IOE 收尾。也就是说，完成本章后，MEMU 不应该只会跑 `hello-serial`，而应该具备运行一批 AM 程序的条件。

建议把 PA2 对齐拆成 5 组：

```text
Group 1: hello / dummy / trap
Group 2: timer / keyboard / display tests
Group 3: slider / typing-game / demo
Group 4: bad-apple / snake
Group 5: litenes / FCEUX
```

不要跳组。比如 `litenes` 失败时，可能是 CPU、timer、keyboard、framebuffer、AM API 任意一层有问题。如果前四组没有通过，直接调 LiteNES 会非常痛苦。

### Group 1: 最小 AM 程序

目标是确认 guest 程序的启动、输出和退出都对：

```sh
./build/memu --image tests/compat/artifacts/am-hello-riscv32.elf --batch
./build/memu --image tests/compat/artifacts/am-dummy-riscv32.elf --batch
```

期望：

```text
Hello
HIT GOOD TRAP
```

如果失败，先回 Chapter 5，不要调设备。

### Group 2: IOE 测试

目标是确认 AM 的 IO 抽象可用：

```text
timer-test
keyboard-test
display-test
```

每个测试只看一个设备。timer test 不应该依赖 keyboard；keyboard test 不应该依赖 framebuffer。你写自己的 smoke test 时也要遵守这个原则。

建议日志格式：

```text
[device] read timer.low  addr=0xa0000048 value=0x...
[device] read timer.high addr=0xa000004c value=0x...
[device] read kbd        addr=0xa0000060 value=0x...
[device] write fb        addr=0xa1000000 len=4 value=0x...
```

### Group 3: 小型图形 AM 程序

目标是确认多个设备可以一起工作。

推荐顺序：

```text
slider
typing-game
demo
```

验收标准：

- `slider` 能显示图片，按键能切换。
- `typing-game` 能显示字符，按键能改变游戏状态。
- `demo` 能持续刷新画面，不会几秒后 trap。

如果画面颜色不对，优先检查像素格式。如果画面错位，优先检查 width、height、pitch 和 framebuffer 写入地址。

### Group 4: Bad Apple 和 Snake

`bad-apple` 更偏显示吞吐和 timer；`snake` 更偏输入和事件循环。

最低标准：

- `bad-apple` 能无音频播放画面。
- `snake` 能显示地图，按方向键能改变移动方向。

这一步开始要关注性能。可以先加入简单统计：

```text
guest instructions: ...
host elapsed ms: ...
guest instr/sec: ...
frame updates: ...
mmio reads/writes: ...
```

性能不够时，不要立刻重写 CPU。先看是否 device trace 默认开着、framebuffer 是否每个像素都 flush、timer 是否导致过多 host 调用。

### Group 5: LiteNES / FCEUX / Mario

这组就是用户常说的“PA2 完成可以跑 Mario”的位置。

先跑 LiteNES，再考虑 FCEUX：

- LiteNES 只需要支撑较小的红白机模拟器路径。
- FCEUX 更完整，压力更大。
- 第一阶段可以无音频运行。
- 音频稳定作为增强验收。

最低验收：

```text
Mario title screen visible
keyboard can start the game
player can move or jump
MEMU does not crash within 5 minutes
```

如果 Mario 画面出来但输入无效，先查 keyboard event 编码和 keydown/keyup。  
如果输入有效但速度不正常，先查 timer 单位。  
如果几秒后非法指令，打开 itrace，确认是不是 CPU 指令语义仍有角落没过。

## 6.17 PA2 完成标准

本章真正完成时，应该满足：

- `cpu-tests` 核心子集仍然通过。
- AM hello/dummy/trap 通过。
- timer、keyboard、display 单项测试通过。
- slider、typing-game、demo 至少两个通过。
- bad-apple 或 snake 至少一个通过。
- LiteNES/FCEUX/Mario 有明确状态：`pass`、`fail` 或 `blocked`，并记录原因。

如果 LiteNES 暂时没跑通，可以进入 Chapter 7，但必须把它写入 `docs/compat-status.md`。不要把失败藏起来。
