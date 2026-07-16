# Stage 5: 设备、MMIO 与抽象机器接口

## 参考 NEMU 的位置

对应 NEMU PA2 的输入输出和 AM。NEMU 使用设备抽象让程序可以访问串口、时钟、键盘和显示等外设，AM 则把不同平台的运行时接口统一起来。

## 为什么做

只会计算的机器无法和外界交互。IO 是程序从“算完就停”走向“能输出、能响应输入、能显示画面”的关键。这个阶段也会引入 memory mapped IO 的思想。

## 要实现什么

- MMIO address space 分发。
- serial：写某个地址时输出字符。
- timer：读取 uptime 或 cycle。
- keyboard：先提供轮询接口，可从宿主输入模拟。
- framebuffer：先实现内存缓冲，后续再接 SDL 或别的显示方式。
- mini AM：`halt()`、`putch()`、`uptime()`、`io_read/io_write()`。

## 怎么做

1. 在内存访问路径中加入 MMIO 判断。
2. 为每个设备定义基址、长度和读写回调。
3. serial 先最小化：写入一个 byte 就打印到 stdout。
4. timer 用宿主 monotonic clock 转换为微秒或毫秒。
5. keyboard 先做非阻塞输入的简化版本，后续再改 SDL。
6. framebuffer 先只支持固定宽高和像素数组。
7. 写 mini AM 头文件和库，让 guest 程序不要直接写魔法地址。

## 怎么验证

```sh
./build/memu --image tests/images/hello-serial.bin --batch
./build/memu --image tests/images/timer.bin --batch
./build/memu --image tests/images/fb-clear.bin --batch
```

期望结果：

- serial 程序在宿主终端输出 `Hello, MEMU`。
- timer 程序读到单调递增的时间。
- framebuffer 测试能写入像素缓冲，并通过 dump 或 checksum 验证。

## 常见坑

- 普通内存和 MMIO 的地址范围不能重叠。
- 设备寄存器宽度要明确，byte/half/word 访问行为不能混乱。
- timer 不应该依赖 CPU 执行速度。
- serial 输出要 flush，否则 batch 模式下可能看不到结果。
- framebuffer 的像素格式要固定，比如 ARGB8888 或 RGB565。

## 给 LLM 的提示

先做 serial 和 timer，不要一开始接图形窗口。MMIO 必须集成到统一访存路径，不能让指令实现直接调用设备函数。AM 接口要尽量小，先服务测试程序。

## 和 NEMU 对齐的验收

对应 NEMU PA2 的 IOE 收尾。这个阶段完成后，MEMU 才应该接近“PA2 完成可以跑小游戏”的状态。

必过验收：

- `am-tests` 中 timer、keyboard、display 相关测试可运行。
- `am-kernels/kernels/slider` 可以显示并切换图片。
- `am-kernels/kernels/typing-game` 可以显示画面并响应按键。
- `am-kernels/kernels/demo` 的图形版本可运行。
- `am-kernels/kernels/bad-apple` 至少能无音频播放画面；音频作为增强项。

挑战验收：

- `am-kernels/kernels/snake` 可交互运行。
- `am-kernels/kernels/litenes` 能运行超级玛丽。
- FCEUX 可运行；先无音频，后续再补声卡。

注意：用户说的“PA2 完成可以跑 Mario”应该落在这里。Stage 3 只是指令，Stage 4 是 AM runtime，Stage 5 的 IOE、VGA、keyboard 到位后，才具备跑 Mario/FCEUX 这类程序的条件。

## 完成标准

- guest 程序能通过 MMIO 输出字符。
- guest 程序能读取时间。
- 设备访问有日志可开关。
- mini AM 可以支持几个最小 demo。
