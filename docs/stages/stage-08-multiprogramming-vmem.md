# Stage 8: 多道程序、虚存与中断

## 参考 NEMU 的位置

对应 NEMU PA4。PA4 从批处理进入多任务系统：多个进程同时存在于内存，系统在合适时机切换执行流；随后引入虚存和中断，让程序拥有独立地址空间并支持分时。

## 为什么做

批处理一次只运行一个程序。多道程序的目标是在一个程序等待 IO 或主动 yield 时切换到另一个程序。虚存解决多个程序加载地址冲突和隔离问题，中断则让系统不依赖程序主动让出 CPU。

## 要实现什么

- Context：保存通用寄存器、PC、必要状态。
- 进程控制块 PCB：状态、栈、上下文、地址空间。
- cooperative yield：通过 syscall 主动切换进程。
- 简化页表和地址翻译。
- timer interrupt：按指令数或宿主时间触发抢占。
- 多进程 demo：两个程序交替输出。

## 怎么做

1. 先实现 cooperative multitasking：用户程序调用 `yield` syscall。
2. trap 时保存当前 CPUState 到当前 PCB。
3. scheduler 选择下一个 runnable PCB。
4. 从下一个 PCB 恢复 CPUState。
5. 给每个进程分配独立栈。
6. 加入虚存前，先用不同物理区域加载不同程序。
7. 实现简化 MMU：guest virtual address 通过页表翻译到 physical address。
8. loader 为每个进程建立页表，把相同虚拟地址映射到不同物理页。
9. timer interrupt 先用指令计数模拟，再考虑真实时间。

## 怎么验证

```sh
./build/memu --kernel tests/images/mp-os.elf --batch
```

期望结果：

- 两个 yield 程序交替输出，例如 `ABABAB`。
- 两个程序使用相同虚拟地址但互不覆盖。
- timer interrupt 打开后，不调用 yield 的程序也会被切走。
- 进程退出后资源被标记释放，不再被调度。

## 常见坑

- 上下文切换的本质是保存和恢复完整状态，少一个寄存器都会出怪 bug。
- 每个进程必须有独立栈。
- 虚拟地址、物理地址、宿主指针三者必须严格区分。
- 页表权限一开始可以简化，但不可读写不存在页面。
- 抢占发生在任意指令边界，日志要能定位切换点。
- 中断和 syscall 都是 trap，但 cause 不同。

## 给 LLM 的提示

按顺序实现：先 cooperative yield，再 PCB 和独立栈，再虚存，最后 timer interrupt。不要一开始就做完整特权级、CSR 和异常返回；先用教学模型跑通控制流。

## 和 NEMU 对齐的验收

对应 NEMU PA4。PA4 的验收不只是“上下文切换 demo 能跑”，还要确认 PA3 已经跑通的应用没有被新机制破坏。

必过验收：

- `am-kernels` 的 `yield-os` 或同等级测试能交替输出。
- 两个执行流有独立栈，切换后寄存器和 PC 不串。
- 两个进程可使用相同虚拟地址，但映射到不同物理页。
- timer interrupt 可以触发抢占，不依赖用户程序主动 `yield`。
- page fault、非法访问、unknown interrupt 有清晰日志。

回归验收：

- Stage 5 的 AM IO demo 仍可运行。
- Stage 7 的 Navy 小程序仍可运行。
- PAL/仙剑类目标至少保持进入画面的能力；如果 PA4 改动导致回退，必须先修复兼容性。

## 完成标准

- 多个用户程序能交替运行。
- 相同虚拟地址可以映射到不同物理页。
- timer interrupt 可以触发抢占式切换。
- 出现 page fault 或非法访问时有清楚日志。
