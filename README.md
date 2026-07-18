# MEMU

MEMU is a teaching emulator inspired by the NEMU PA route. The first target is a small RV32I emulator that can grow toward the AM / Nanos-lite / Navy-apps stack.

The current local scaffold is Stage 7: ramdisk, simple file system, and fs
loader. Strict NEMU alignment has passed the real PA CPU gate and AM/CTE/IOE
smoke gate, including interrupt/yield, audio/devscan, plus bounded real AM app
runs including slider, typing-game, demo, snake, bad-apple, and LiteNES/Mario.
A minimal real Nanos-lite + Navy-apps hello+dummy batch smoke also passes
through `make pa-nanos-tests`, and the official Navy `tests/hello` now passes
through real newlib libc with `make pa-nanos-libc-test`; full PA3 NDL/Navy app
coverage is still active work. MEMU also has an SDL-backed LiteNES/Mario path with keyboard for local
interactive play. MEMU's audio device is implemented and verified by AM
audio/bad-apple paths, but this PA checkout's LiteNES/Mario source does not
generate NES APU audio. FCEUX now has a bounded real-artifact smoke through
`make pa-fceux-test` using public `nestest.nes`; the historical PA Box ROM URL
currently returns a login page, so this does not claim a commercial game ROM.

## Requirements

On macOS, install:

- Apple clang, usually from Xcode Command Line Tools: `xcode-select --install`
- CMake 3.20 or newer
- Ninja or Make
- SDL2, only needed for `make mario`: `brew install sdl2`

The RISC-V toolchain is optional in Stage 0. Later stages can build guest programs on Linux, Docker, Lima, UTM, or a remote machine, then copy the resulting raw or ELF artifacts into `tools/artifacts/` with notes about the exact source and build command.

MEMU is intended to match NEMU PA outcomes. The generated tests in this repo are
local scaffold checks; strict completion requires the NEMU-aligned targets in
`docs/nemu-stage-acceptance.md` and `docs/nemu-strict-alignment.md`.

## Build

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

If `cmake` is not installed yet, use the small fallback Makefile:

```sh
make
make test
```

For day-to-day work, the Makefile also provides shortcuts:

```sh
make run             # enter monitor with the default Stage 1 image
make batch           # run the default image to completion
make dump-regs       # run the default image and print registers
make self-test       # run the built-in smoke program
make test            # run all Makefile tests
make expr-test       # run generated expression tests
make rv32i-test      # run the Stage 3 RV32I image suite
make stage4-test     # run trap, max-instr, invalid instruction, and ELF tests
make stage5-test     # run serial, timer, keyboard, and framebuffer tests
make stage6-test     # run syscall write/brk/exit and batch-list tests
make stage7-test     # run ramdisk, fs syscall, and fs loader tests
make gen-toolchain-images # build the RV32 GCC toolchain ELF smoke image
make toolchain-test  # build and run the RV32 GCC toolchain ELF smoke image
make pa-cpu-tests    # build and run real PA cpu-tests; set PA_HOME if needed
make pa-am-tests     # build and run real PA AM hello/timer/intr/kbd/display/devscan/audio tests
make pa-app-tests    # build and run real PA slider/typing/demo/snake/bad-apple/LiteNES tests
make pa-fceux-test   # build and run real PA FCEUX with a NES test ROM
make pa-cte-os-tests # build and run real PA yield-os/thread-os CTE tests
make pa-nanos-tests  # build and run real Nanos-lite with minimal Navy hello+dummy
make pa-nanos-libc-test # build and run official Navy hello through real libc/newlib
make mario           # build SDL MEMU and run LiteNES/Mario interactively
make runner-test     # run the default passing artifact runner
make cmake-test      # configure, build, and run CTest
```

To run a different raw guest image:

```sh
make run IMAGE=path/to/program.bin
make batch IMAGE=path/to/program.bin
```

## Run

```sh
./build/memu --help
./build/memu --version
./build/memu --self-test --batch
./build/memu --image tests/images/stage1-trap.bin --batch --dump-regs
./build/memu --image tests/images/stage1-trap.bin
./build/memu --image tests/images/rv32i-add.bin --batch
./build/memu --image tests/images/rv32i-load-store.bin --batch
./build/memu --image tests/images/rv32i-branch-sum.bin --batch
./build/memu --image tests/images/rv32i-jump.bin --batch
./build/memu --image tests/images/good.bin --batch
./build/memu --elf tests/images/good.elf --batch
./build/memu --image tests/images/hello-serial.bin --batch
./build/memu --image tests/images/timer.bin --batch
./build/memu --image tests/images/keyboard.bin --batch --trace-device
./build/memu --image tests/images/fb-clear.bin --batch --trace-device
./build/memu --image tests/images/sys-write.bin --batch --trace-syscall
./build/memu --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
./build/memu --ramdisk tests/images/ramdisk.img --run /bin/fs-cat --batch --trace-syscall
./build/memu --elf tests/images/toolchain-basic.elf --batch
```

Stage 3 supports common RV32I integer instructions, plus the RV32M multiply and
divide subset and minimal system instructions commonly emitted by RISC-V
toolchains and AM code:

- `lui`, `auipc`
- `jal`, `jalr`
- `addi`, `slti`, `sltiu`, `xori`, `ori`, `andi`, `slli`, `srli`, `srai`
- `add`, `sub`, `sll`, `slt`, `sltu`, `xor`, `srl`, `sra`, `or`, `and`
- `lb`, `lh`, `lw`, `lbu`, `lhu`
- `sb`, `sh`, `sw`
- `beq`, `bne`, `blt`, `bge`, `bltu`, `bgeu`
- `ebreak` as MEMU trap
- `mul`, `mulh`, `mulhsu`, `mulhu`, `div`, `divu`, `rem`, `remu`
- `fence`, `fence.i`, CSR read/write/set/clear, and `mret`

`ebreak` is treated as a MEMU trap. If `a0 == 0`, MEMU reports `HIT GOOD TRAP`; otherwise it reports `HIT BAD TRAP`.

The Stage 1 fixture can be regenerated with:

```sh
tools/mkbin/stage1_trap.py tests/images/stage1-trap.bin
```

The Stage 3 RV32I fixtures can be regenerated with:

```sh
make gen-rv32i-images
```

The Stage 4 runtime/loader fixtures can be regenerated with:

```sh
make gen-runtime-images
```

The Stage 5 device fixtures can be regenerated with:

```sh
make gen-device-images
```

The Stage 6 syscall fixtures can be regenerated with:

```sh
make gen-syscall-images
```

The Stage 7 ramdisk fixture can be regenerated with:

```sh
make gen-fs-images
```

The RV32 GCC toolchain ELF smoke fixture can be rebuilt with:

```sh
make gen-toolchain-images
make toolchain-test
```

This uses `riscv64-unknown-elf-gcc` with
`-march=rv32im_zicsr_zifencei -mabi=ilp32`. It verifies a real ELF produced by
the cross toolchain, but it is still a MEMU-local smoke test. NEMU-aligned
completion still requires real `am-kernels` and AM application artifacts.

To run the real NEMU PA CPU test gate:

```sh
make pa-cpu-tests PA_HOME=/path/to/ICS-PA
```

On this machine the default PA checkout is
`/Users/wjl/Projects/icspa2025/ICS-PA`, so `make pa-cpu-tests` works without
passing `PA_HOME`.

To run the real PA AM/IOE smoke gate:

```sh
make pa-am-tests PA_HOME=/path/to/ICS-PA
```

This builds `kernels/hello` plus `tests/am-tests` with `mainargs=h/t/i/k/v/d/a`.
`h` exits by good trap; `t`, `i`, `k`, and `v` are long-running AM tests and are
checked by bounded `--max-instr` runs plus expected timer, interrupt/yield,
keyboard, and framebuffer/FPS output. `d` runs devscan with a temporary PA
checkout patch for this checkout's missing riscv32-nemu
`AM_GPU_MEMCPY`/`AM_GPU_RENDER` handlers and disk config stub. `a` patches the
copied PA tree to enable NEMU MMIO audio and verifies that `AM_AUDIO_PLAY`
reaches MEMU.

To run the real PA AM app smoke gate:

```sh
make pa-app-tests PA_HOME=/path/to/ICS-PA
```

This builds and runs `slider`, `typing-game`, `demo` with `mainargs=1`, `snake`,
`bad-apple`, and `litenes` with the bundled Mario ROM. These are long-running
apps, so the test checks bounded runs for expected framebuffer/FPS/status
output or sustained execution to the instruction limit.

To run the real AM context-switching smoke gate:

```sh
make pa-cte-os-tests PA_HOME=/path/to/ICS-PA
```

This builds and runs `yield-os` and `thread-os` from `am-kernels`. MEMU injects
a minimal machine timer interrupt when `mstatus.MIE` and `mtvec` are set, and
the temporary PA checkout patch supplies riscv32-nemu `kcontext`, trap return
context switching, timer/yield event mapping, and a single-core `atomic_xchg`.

To run the minimal real Nanos-lite + Navy-apps smoke gate:

```sh
make pa-nanos-tests PA_HOME=/path/to/ICS-PA
```

This copies the PA checkout to a temp directory, patches only the temp
Nanos-lite/Navy trees, builds small Navy `tests/hello` and `tests/dummy`
programs for `riscv32`, installs them into the ramdisk, and boots them through
real Nanos-lite on MEMU. The scope validates loader, ramdisk, syscall dispatch,
write/exit/yield, and a simple exit-to-next-program batch path.

To exercise the official Navy hello with real libc/newlib instead of the small
direct-syscall test program:

```sh
make pa-nanos-libc-test PA_HOME=/path/to/ICS-PA
```

This builds the downloaded compiler-rt and Navy libc sources in the temp tree,
links `printf` through libos syscalls, and runs until MEMU's instruction limit.
The compatibility patch excludes three riscv32-incompatible newlib sources
(`getpass.c`, `stat64r.c`, and `wcwidth.c`). NDL drawing apps, miniSDL apps,
PAL, and `execve`-style program replacement have separate compatibility
targets; use `make pa-pal-probe` for the PAL missing-resource probe and
`make pa-pal-test PAL_NANOS_DATA=/path/to/legal/game-data` for licensed data.

To run Mario yourself in a window:

```sh
make mario
```

This builds an SDL-enabled `build/memu-sdl`, patches the copied PA AM audio glue,
builds the PA LiteNES artifact from `PA_HOME`, and opens a 400x300 framebuffer
window. On this machine `PA_HOME` defaults to
`/Users/wjl/Projects/icspa2025/ICS-PA`; elsewhere pass it explicitly:

```sh
make mario PA_HOME=/path/to/ICS-PA
```

Audio note: no Mario sound is expected with this LiteNES source. Its `psg.c`
only implements controller strobe/read behavior for `0x4016`; it does not
produce NES APU samples or call `AM_AUDIO_PLAY`. MEMU audio is still exercised
by `make pa-am-tests` and the bad-apple app path.

Controls are:

```text
W/A/S/D or arrow keys: D-pad
U: SELECT
I: START
J: A
K: B
Esc: escape key event
```

Close the SDL window to stop MEMU. If you want a bounded strict run for testing,
use `MARIO_MAX_INSTR=N MARIO_STRICT=1 make mario`.

`tools/run-tests.sh ./build/memu` runs the default passing raw and ELF artifacts.
Bad trap, infinite loop, and invalid instruction fixtures are checked by
`make stage4-test` rather than the default pass runner.

Use `--trace` to print each executed guest instruction:

```sh
make batch IMAGE=tests/images/rv32i-branch-sum.bin RUN_ARGS=--trace
```

Use `--trace-device` to print MMIO reads and writes:

```sh
make batch IMAGE=tests/images/fb-clear.bin RUN_ARGS=--trace-device
```

Use `--trace-syscall` to print syscall number, arguments, and return value:

```sh
./build/memu --image tests/images/sys-write.bin --batch --trace-syscall
```

Use `--batch-list` to run raw user programs through the minimal batch runtime.
Because it accepts a variable-length program list, put other options before it:

```sh
./build/memu --trace-syscall --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
```

Use `--ramdisk` and `--run` to load a raw user program from MEMU SFS:

```sh
./build/memu --ramdisk tests/images/ramdisk.img --run /bin/fs-cat --batch
```

Without `--batch`, MEMU enters the monitor. The Stage 2 monitor supports:

- `help`, `q`, `c`, `si`
- `info r`, `info w`
- `x N EXPR`
- `p EXPR`
- `w EXPR`, `d N`

Expressions support decimal and hex numbers, registers such as `$pc` and `$a1`,
parentheses, `+ - * / == != &&`, unary `-`, and guest memory dereference with
`*EXPR`.
