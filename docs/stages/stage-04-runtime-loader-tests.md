# Stage 4: 程序装载、运行时与测试基础设施

## 参考 NEMU 的位置

对应 NEMU PA2 的“程序、运行时环境与 AM”和基础设施。NEMU 的思路是：指令足够只是必要条件，程序还需要被加载到正确位置，并有结束运行的方式。

## 为什么做

一个 emulator 不能只跑手写机器码。它需要能加载程序，知道程序入口，处理 halt/trap，并提供足够的测试设施来持续验证 ISA 语义。

## 要实现什么

- raw binary loader：加载到 `MEM_BASE`。
- ELF loader：读取 ELF32 little endian RISC-V，可选但建议做。
- trap 约定：客户程序通过 `ebreak` 或指定 magic 指令退出。
- `HIT GOOD TRAP` / `HIT BAD TRAP` 区分。
- trace：instruction trace、memory trace、function trace 的雏形。
- 测试镜像生成脚本。

## 怎么做

1. 先保留 raw loader，确保 Stage 1 到 Stage 3 的测试不受影响。
2. 引入 ELF parser，只处理需要的 program headers，不做动态链接。
3. 入口地址来自 ELF header，raw binary 入口默认为 `MEM_BASE`。
4. 定义约定：`a0 == 0` 表示 good trap，非 0 表示 bad trap。
5. 增加 `--batch`、`--trace`、`--max-instr` 等 CLI 参数。
6. 建立 `tests/isa/`，用汇编或 C 生成小程序。

## 怎么验证

```sh
./build/memu --image tests/images/hello-trap.bin --batch
./build/memu --image tests/images/sum.elf --batch
./build/memu --image tests/images/bad-trap.bin --batch
```

期望结果：

- good 程序退出码为 0。
- bad 程序退出码非 0。
- ELF 程序从 ELF entry 开始执行。
- trace 中能看到出错前最后若干条指令。

## 常见坑

- ELF 的虚拟地址和文件偏移不是一回事。
- `p_filesz` 和 `p_memsz` 不同，`.bss` 要清零。
- 入口地址不要写死。
- trap 语义要稳定，后续 syscall 和 OS 会依赖它。
- trace 输出过多会影响调试，默认关闭，通过参数打开。

## 给 LLM 的提示

先完成 raw loader 和 trap 约定，再做 ELF loader。ELF loader 只处理静态、裸机、32-bit little endian RISC-V ELF，不要支持动态链接、共享库或操作系统 ABI。

## 和 NEMU 对齐的验收

对应 NEMU PA2 的“程序、运行时环境与 AM”。Stage 4 完成后，MEMU 应该开始运行 NEMU PA 工具链构建出来的 AM artifact：

- AM hello/dummy/trap 类程序能正常输出并退出。
- `cpu-tests` 不再依赖 MEMU 自己手写的 image，而是能加载真实构建产物。
- good trap / bad trap 语义和 AM 约定稳定。
- ELF/raw binary 的加载地址、入口地址和栈初始化有明确规则。

如果 AM hello 不能稳定运行，不要进入 Stage 5 的设备和小游戏。

## 完成标准

- MEMU 可以运行 raw binary 和简单 ELF。
- 测试程序可以表达成功和失败。
- 出错时能通过 trace 快速定位到 guest PC。
