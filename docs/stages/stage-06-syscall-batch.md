# Stage 6: 系统调用与最小批处理系统

## 参考 NEMU 的位置

对应 NEMU PA3 的最简单操作系统、用户程序和系统调用。PA3 的核心变化是：程序不再只是独占机器的裸机程序，而是通过 OS 提供的机制运行和退出。

## 为什么做

批处理系统的关键是程序执行结束后能回到后台程序，由后台程序加载下一个程序。为此需要 trap/syscall、执行流切换和 loader 的配合。这是从 bare-metal 进入 OS 世界的第一步。

## 要实现什么

- syscall trap 路径。
- syscall ABI：参数从寄存器读取，返回值写回寄存器。
- 最小 syscall：`exit`、`write`、`brk` 可先 stub。
- mini OS：加载一个用户程序，处理退出，再加载下一个。
- 用户/内核暂时不做特权隔离，先把控制流跑通。

## 怎么做

1. 在 RV32I system 指令中区分 `ecall` 和 `ebreak`。
2. `ecall` 进入 MEMU 的 trap handler 或 mini OS handler。
3. 定义 syscall number 放在哪个寄存器，例如 RISC-V 常用 `a7`。
4. 实现 `SYS_exit`，让用户程序回到 mini OS。
5. 实现 `SYS_write`，fd 1/2 输出到 serial 或 stdout。
6. mini OS 维护程序列表，当前程序结束后加载下一个。
7. 所有程序结束后 good trap。

## 怎么验证

```sh
./build/memu --kernel tests/images/batch-os.elf --batch
```

期望结果：

- 程序 A 输出并 exit。
- mini OS 加载程序 B。
- 程序 B 输出并 exit。
- 所有程序完成后 MEMU good trap。

## 常见坑

- `ecall` 后 PC 应该指向下一条指令还是 trap 入口，要在模型中统一。
- syscall 参数寄存器和返回值寄存器要固定。
- 用户程序退出不能直接终止 MEMU，而应该先回到 mini OS。
- loader 覆盖内存时要小心 OS 自己的位置。
- 当前阶段可以不做权限保护，但文档里要标注这是简化。

## 给 LLM 的提示

先用同一地址空间实现批处理，不要引入虚存和进程隔离。目标是理解“用户程序结束后回到 OS，OS 加载下一个程序”的控制流。

## 和 NEMU 对齐的验收

对应 NEMU PA3 的 Nanos-lite 起步。Stage 6 的目标不是跑完整 Navy-apps，而是让最小 OS 控制流成立：

- Nanos-lite 或 MEMU mini OS 能加载一个用户程序。
- 用户程序能通过 `write` 输出，通过 `exit` 返回 OS。
- `brk` 至少有稳定语义，不能永远假装成功。
- 两个基础用户程序可以按顺序运行。
- syscall trace 能显示 syscall number、参数、返回值。

完成 Stage 6 后，才进入文件系统和 Navy 应用。

## 完成标准

- 至少两个用户程序可以按顺序运行。
- syscall write 能输出字符串。
- syscall exit 能把控制权交回 mini OS。
