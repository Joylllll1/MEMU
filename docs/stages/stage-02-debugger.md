# Stage 2: 简易调试器

## 参考 NEMU 的位置

对应 NEMU PA1 的基础设施、表达式求值和监视点。NEMU 强调调试器是直接观察客户程序状态的工具，否则后续 bug 会非常难定位。

## 为什么做

emulator 调试有两层：宿主程序 MEMU 自己的 bug，以及客户程序在模拟机器里的状态。GDB 可以调 MEMU，但不能自然地观察 guest 寄存器、guest 内存和 guest PC。简易调试器就是为了观察 guest。

## 要实现什么

- 交互式 monitor。
- 命令：`help`、`c`、`q`、`si`、`info r`、`x N EXPR`。
- 表达式求值：十进制、十六进制、寄存器、括号、`+ - * / == != &&`。
- 指针解引用：`*EXPR` 读取 guest memory。
- 监视点：`w EXPR`、`d N`、表达式变化时停机。

## 怎么做

1. 先实现最简单的命令循环，用 `fgets()` 即可，不急着接 readline。
2. 命令解析采用空格切分，保留表达式原文。
3. 表达式先做 tokenizer，再递归求值。
4. 通过 `isa_reg_str2val()` 查询寄存器值。
5. `x N EXPR` 先求地址，再连续读 guest memory。
6. watchpoint 使用固定大小池，保存表达式字符串和上一次值。
7. 每执行一条指令后检查 watchpoint。

## 怎么验证

```text
./build/memu --image tests/images/stage1-addi.bin
(memu) info r
(memu) si 1
(memu) p 1 + 2 * 3
(memu) p $pc
(memu) x 4 0x80000000
(memu) w $a0 == 42
(memu) c
```

期望结果：

- `info r` 打印全部寄存器和 PC。
- `si` 能单步推进。
- `p` 能计算常量和寄存器表达式。
- `x` 能扫描 guest memory。
- watchpoint 值变化时停止并显示旧值、新值。

## 常见坑

- `*` 可能是乘法，也可能是指针解引用，需要根据前一个 token 判断。
- 一元负号和二元减号也要区分。
- 表达式求值失败必须返回错误，不要默默返回 0。
- watchpoint 保存表达式字符串时要注意长度和生命周期。
- `si 0`、空命令、非法命令都要有稳定行为。

## 给 LLM 的提示

先实现命令框架和 `info r`、`si`、`x`，再实现表达式，最后实现 watchpoint。不要为了表达式引入复杂 parser generator，当前阶段手写 tokenizer 和递归求值更可控。

## 和 NEMU 对齐的验收

对应 NEMU PA1 的 monitor、表达式求值和监视点。这个阶段的验收重点是调试能力：

- `help/c/q/si/info r/x/p/w/d` 的最小命令集可用。
- 表达式能引用寄存器和 guest memory。
- watchpoint 能在表达式变化时停下。
- 后续运行 `cpu-tests`、AM 程序或 Navy app 出错时，可以用 monitor 定位 guest PC、寄存器和内存。

Stage 2 完成不要求跑大型 NEMU 程序，但它必须成为后续所有 NEMU 对齐验收的调试工具。

## 完成标准

- 可以不用 GDB 观察 guest PC、寄存器和内存。
- 可以单步执行并在 watchpoint 命中时暂停。
- 表达式错误不会导致 MEMU 崩溃。
