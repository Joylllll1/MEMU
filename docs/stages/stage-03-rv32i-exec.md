# Stage 3: RV32I 指令执行核心

## 参考 NEMU 的位置

对应 NEMU PA2 的“取指、译码、执行”。PA2 开始，emulator 从能执行几条玩具指令，变成可以运行真实编译器生成的程序。

## 为什么做

只有实现足够多的 ISA 语义，运行时、测试程序和 OS 才有基础。这个阶段的重点不是快，而是准确：每条指令的操作数、立即数、写回和 PC 更新都必须符合手册。

## 要实现什么

覆盖 RV32I 常用整数指令：

- U-type：`lui`、`auipc`
- J-type：`jal`
- I-type：`jalr`、`addi`、`slti`、`sltiu`、`xori`、`ori`、`andi`、`slli`、`srli`、`srai`、loads
- S-type：stores
- B-type：`beq`、`bne`、`blt`、`bge`、`bltu`、`bgeu`
- R-type：`add`、`sub`、`sll`、`slt`、`sltu`、`xor`、`srl`、`sra`、`or`、`and`
- system：先保留 `ebreak` 作为 trap

## 怎么做

1. 建立统一 decode helper，抽取 `rd`、`rs1`、`rs2`、`funct3`、`funct7`、各类 immediate。
2. 每种指令格式先写单元测试，尤其是立即数符号扩展。
3. 访存统一走 `mem_read(addr, len)` 和 `mem_write(addr, len, data)`。
4. load 处理符号扩展和零扩展。
5. branch 和 jump 明确区分 `snpc` 和 `dnpc`：顺序下一条 PC 与动态下一条 PC。
6. 每条指令执行后强制 `x0 = 0`。

## 怎么验证

```sh
./build/memu --image tests/images/rv32ui-add.bin --batch
./build/memu --image tests/images/rv32ui-branch.bin --batch
./build/memu --image tests/images/rv32ui-load-store.bin --batch
```

如果还没有 riscv 工具链，先用手写机器码测试以下类别：

- 算术：`addi/add/sub/and/or/xor`
- 分支：循环累加到 5050
- 访存：store 后 load 回来比较
- 跳转：`jal/jalr` 返回地址正确

## 常见坑

- B-type 和 J-type immediate 的位段不连续，非常容易拼错。
- `jalr` 的目标地址最低位要清 0。
- signed/unsigned 比较必须分清。
- `srai` 与 `srli` 的右移语义不同。
- load byte/half 的符号扩展不能忘。
- 未实现指令要打印 opcode、pc、inst，方便定位。

## 给 LLM 的提示

每次只实现一组指令，例如先 R/I 算术，再 branch，再 load/store。每组指令都要补测试。遇到不确定的语义，先查 RISC-V ISA manual，不要凭感觉写。

## 和 NEMU 对齐的验收

对应 NEMU PA2 前半段：让机器能持续执行真实编译器生成的指令。Stage 3 的 NEMU 对齐目标是 `am-kernels/tests/cpu-tests` 的无 IO 子集：

- 第一批：`add`、`sub`、`shift`、`bit`、`cmp`。
- 第二批：`load/store`、`branch`、`jump`。
- 第三批：能暴露立即数、符号扩展、x0 写保护问题的测试。

这一阶段不要求跑 Mario、Bad Apple 或图形 demo。那些程序依赖 AM runtime 和 IOE，应该放到 Stage 4/5。

## 完成标准

- 常用 RV32I 指令通过指令测试。
- 未实现或非法指令有明确报错。
- 指令 trace 能显示 `pc`、原始指令和简单反汇编信息。
