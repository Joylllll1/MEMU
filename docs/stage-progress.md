# MEMU Stage Progress

This file is the handoff point between Codex sessions. Read it first, then read
the current stage document under `docs/stages/`, and finally inspect the code.

## Project Root

```text
/Users/wjl/Projects/MEMU
```

If a session starts somewhere else, switch to this directory before making
changes.

## Current Status

- Local scaffold implemented through: Stage 8, Sv32 virtual memory and the
  mp-os two-process preemption scaffold.
- NEMU-aligned complete through: Stage 8 per the
  `docs/nemu-strict-alignment.md` stage completion rules; real PA4
  yield/context/vmem/timer tests pass while the PA3 apps still work.
- Additional CTE/PA4 prework: real `yield-os` and `thread-os` pass with
  `make pa-cte-os-tests`; MEMU now has minimal machine timer interrupt
  injection for `mstatus.MIE` + `mtvec`.
- Stage 7/Navy prep: `/dev/events` now returns NDL-style `kd/ku KEY` lines for
  SDL key events and returns 0 when no event is queued.
- PA3 minimal real-artifact gate: `nanos-lite`, `navy-apps`, and
  `newlib-navy` sources are now present under
  `/Users/wjl/Projects/icspa2025/ICS-PA`; `make pa-nanos-tests` boots real
  Nanos-lite, loads minimal Navy `tests/hello` and `tests/dummy` programs,
  prints through sys_write, exercises yield/exit, and good-traps after the
  second program exits.
- Interactive LiteNES/Mario path: `make mario` builds an SDL-enabled MEMU,
  patches PA AM audio glue, builds the PA LiteNES artifact, opens a 400x300
  window, and maps host keys to AM keyboard events. No Mario sound is expected
  in this PA checkout because LiteNES does not generate NES APU samples.
- Active strict gate: FCEUX bounded execution passes with public `nestest.nes`
  under `/Users/wjl/Projects/icspa2025/ICS-PA/fceux-am/nes/rom/`; the historical
  PA Box download URL currently returns a login page.
- Full PA3 now substantially complete: Nanos/Navy has the minimal
  direct-syscall hello-to-dummy smoke, official Navy libc/newlib hello smoke,
  NSlider multi-slide navigation with real generated slide assets and keyboard
  injection, standalone NDL draw/event/timer test, Flappy Bird miniSDL game
  running under batch mode, and execve-style program replacement. PAL and
  interactive SDL input for Navy apps remain future work.
- The full libc smoke uses downloaded compiler-rt/newlib sources and excludes
  three riscv32-incompatible newlib sources in the temporary tree:
  `getpass.c`, `stat64r.c`, and `wcwidth.c`.
- Stage 8 virtual memory is complete: MEMU implements real Sv32 translation
  (satp CSR, two-level walk, page-fault diagnostics), the local mp-os
  scaffold demonstrates same-VA isolation with timer preemption, and the
  real PA4 path runs official Navy hello under Nanos-lite HAS_VME paging
  through `make pa-vme-test`.

## Strict NEMU Alignment Rule

MEMU's goal is to complete what NEMU can complete. Local smoke tests are not
stage completion. They are scaffold verification only.

The authoritative rule is:

```text
local smoke pass != NEMU-aligned stage complete
```

See `docs/nemu-strict-alignment.md` and `docs/nemu-stage-acceptance.md`.

The current PA2 strict order is:

```text
cpu-tests no-IO subset
AM hello/dummy/trap
AM timer/keyboard/display tests
slider / typing-game / demo
bad-apple or snake
LiteNES/Mario status
```

Current strict progress:

```text
cpu-tests no-IO subset: pass, 35/35 real am-kernels/tests/cpu-tests
AM hello/dummy/trap: pass for AM hello/halt trap
AM timer/interrupt/keyboard/display/devscan/audio tests: pass for real am-tests h/t/i/k/v/d/a
slider / typing-game / demo: pass for bounded real AM app runs
bad-apple or snake: both pass in bounded real AM app runs
LiteNES/Mario status: pass for bounded bundled Mario ROM render/FPS; SDL path added for interactive play with keyboard via `make mario`; no LiteNES/Mario audio output in this PA source
FCEUX status: pass for bounded execution of public `nestest.nes`; the official
PA Box URL currently returns a login page rather than the historical archive
yield-os/thread-os status: pass for real am-kernels CTE/context-switch smoke
Nanos-lite/Navy status: direct-syscall hello-to-dummy batch, official Navy libc/newlib hello, NSlider multi-slide navigation with real slides, standalone NDL draw/event/timer test, Flappy Bird miniSDL game, and execve program replacement pass under real Nanos-lite; PAL remains not-started
PA4 virtual memory status: pass; MEMU Sv32 translation drives the local mp-os two-process scaffold (`make stage8-test`) and official Navy hello under Nanos-lite HAS_VME paging (`make pa-vme-test`)
```

## Stage 0 Verification

The following commands passed on macOS after installing CMake through Homebrew:

```sh
cmake -S . -B build
cmake --build build
./build/memu --help
ctest --test-dir build --output-on-failure
```

Additional Makefile fallback verification also passed:

```sh
make -B BUILD_DIR=/private/tmp/memu-stage0-verify all
make test
make test BUILD_DIR=/private/tmp/memu-stage0-verify
```

## Stage 1 Verification

The following commands passed:

```sh
cmake -S . -B build
cmake --build build
./build/memu --image tests/images/stage1-trap.bin --batch
ctest --test-dir build --output-on-failure
make test
```

## Stage 2 Verification

The following commands passed:

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
make test BUILD_DIR=/private/tmp/memu-stage2-make-final
./build/memu --image tests/images/stage1-trap.bin
```

## Stage 3 Local Scaffold Verification

The following commands passed:

```sh
tools/mkbin/rv32i_programs.py tests/images
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
make test BUILD_DIR=/private/tmp/memu-stage3-make-final
./build/memu --image tests/images/rv32i-add.bin --batch
./build/memu --image tests/images/rv32i-load-store.bin --batch
./build/memu --image tests/images/rv32i-branch-sum.bin --batch
./build/memu --image tests/images/rv32i-jump.bin --batch
```

Strict NEMU status: Stage 3 CPU gate passed after the real `cpu-tests` run
recorded below. The later Stage 4/5 real AM smoke gate covers AM hello plus
timer/keyboard/display.

Strict NEMU CPU gate update:

```sh
make pa-cpu-tests BUILD_DIR=/private/tmp/memu-pa-loader-build
```

This copied the local PA checkout from `/Users/wjl/Projects/icspa2025/ICS-PA`
to `/private/tmp`, built all 35 `am-kernels/tests/cpu-tests` as
`riscv32-nemu` ELF images with `riscv64-unknown-elf-*`, and ran them on MEMU.
Result: `SUMMARY pass=35 fail=0`.

Before this passed, real `dummy-riscv32-nemu.elf` exposed an ELF loader bug:
some PA ELFs contain an empty `PT_LOAD` segment at `vaddr=0, memsz=0`. MEMU now
skips zero-sized loadable segments instead of checking them as guest memory.

Additional PA2 compatibility improvement:

```sh
make rv32i-test BUILD_DIR=/private/tmp/memu-rv32m-build
make test BUILD_DIR=/private/tmp/memu-rv32m-build
cmake -S . -B /private/tmp/memu-rv32m-cmake
cmake --build /private/tmp/memu-rv32m-cmake
ctest --test-dir /private/tmp/memu-rv32m-cmake --output-on-failure
```

This added local RV32M coverage for `mul`, `mulh`, `mulhsu`, `mulhu`, `div`,
`divu`, `rem`, and `remu`, including divide-by-zero and signed overflow cases.
The later strict CPU gate run confirms real `cpu-tests` pass on top of this
local coverage.

Additional AM/system-instruction compatibility improvement:

```sh
make rv32i-test BUILD_DIR=/private/tmp/memu-csr-build
make test BUILD_DIR=/private/tmp/memu-csr-build
cmake -S . -B /private/tmp/memu-csr-cmake
cmake --build /private/tmp/memu-csr-cmake
ctest --test-dir /private/tmp/memu-csr-cmake --output-on-failure
```

This added local coverage for `fence`, `fence.i`, CSR instructions, minimal
machine CSRs (`mstatus`, `mtvec`, `mscratch`, `mepc`, `mcause`, `mhartid`,
`mcycle`, `minstret`), `ecall` to `mtvec` when `mtvec` is configured, and
`mret`. The later real AM smoke gate confirms AM hello/timer/keyboard/display
artifacts pass. CTE yield is now covered by the real AM smoke gate with a
temporary PA checkout patch for riscv32-nemu Context layout and EVENT_YIELD
mapping.

Additional toolchain ELF compatibility improvement:

```sh
make toolchain-test BUILD_DIR=/private/tmp/memu-toolchain-elf-build
make runner-test BUILD_DIR=/private/tmp/memu-toolchain-elf-build
make test BUILD_DIR=/private/tmp/memu-toolchain-elf-build
cmake -S . -B /private/tmp/memu-toolchain-elf-cmake
cmake --build /private/tmp/memu-toolchain-elf-cmake
ctest --test-dir /private/tmp/memu-toolchain-elf-cmake --output-on-failure
```

This added a real `riscv64-unknown-elf-gcc` RV32 ELF smoke image built with
`-march=rv32im_zicsr_zifencei -mabi=ilp32`. The guest checks data/bss setup,
RV32M arithmetic, CSR reads, and `fence/fence.i`, then exits by MEMU good trap.
Strict NEMU status still depends on real AM artifacts after the real
`cpu-tests` gate.

## Stage 4/5 Real AM Smoke Gate

The following real PA AM/IOE command passed:

```sh
make pa-am-tests BUILD_DIR=/private/tmp/memu-pa-am-script-build
```

It copies `/Users/wjl/Projects/icspa2025/ICS-PA` to `/private/tmp`, builds
`kernels/hello` and `tests/am-tests` for `riscv32-nemu`, and runs:

```text
am-kernel-hello: pass, good trap with "Hello, AbstractMachine!"
am-tests h: pass, good trap with ten "Hello, AM World @ riscv32" lines
am-tests t: pass, bounded run prints one-second RTC/uptime output
am-tests k: pass, bounded run starts keyboard polling without aborting
am-tests v: pass, bounded run produces framebuffer checksums and FPS output
am-tests d: pass, bounded devscan reaches storage dump and Test End
am-tests a: pass, audio payload is accepted and good-traps
```

Known real PA gaps after this gate:

```text
am-tests i: pass after patching copied PA riscv32-nemu Context layout and yield event mapping
AM patch note: this PA checkout's riscv32-nemu AM leaves audio disabled, omits AM_GPU_MEMCPY/AM_GPU_RENDER handlers, leaves disk config incomplete, and has incomplete CTE yield handling, so tools/patch-pa-nemu-ioe.py patches only copied temp PA trees before building real artifacts
```

## Stage 5 Real AM App Gate

The following real PA AM app command passed after changing MEMU's VGA config
from the early 64x48 smoke size to the PA/NEMU-compatible 400x300 framebuffer:

```sh
make pa-app-tests BUILD_DIR=/private/tmp/memu-pa-app-script-build
```

It copies `/Users/wjl/Projects/icspa2025/ICS-PA` to `/private/tmp`, builds AM
apps for `riscv32-nemu`, and runs:

```text
slider: pass, bounded run renders 400x300 framebuffer
typing-game: pass, bounded run renders and prints score state
demo mainargs=1: pass, bounded ant demo renders continuously
snake: pass, bounded run renders, reaches GAME OVER, then waits for Q
bad-apple: pass, ffmpeg generates resources and bounded run sustains execution
LiteNES/Mario: pass, boots bundled Mario ROM, renders frames, prints FPS
```

Remaining PA2 gaps after this gate:

```text
default non-SDL keyboard remains a polling stub; SDL Mario path has host keyboard input
FCEUX bounded execution passes with `nestest.nes` in this checkout's
`fceux-am/nes/` ROM directory; this validates FCEUX integration but is not a
claim that a commercial game ROM was redistributed
SDL audio output is implemented in MEMU and verified by AM audio/bad-apple paths; current LiteNES/Mario does not feed it audio
```

## PA3 Minimal Nanos-lite/Navy Smoke

The following real PA3 smoke gate passed:

```sh
make pa-nanos-tests BUILD_DIR=/private/tmp/memu-pa-nanos-batch
```

Before this gate, the missing source blocker was resolved by adding:

```text
/Users/wjl/Projects/icspa2025/ICS-PA/nanos-lite
/Users/wjl/Projects/icspa2025/ICS-PA/navy-apps
/Users/wjl/Projects/icspa2025/ICS-PA/navy-apps/libs/libc
```

The target copies `abstract-machine`, `nanos-lite`, and `navy-apps` to a temp
directory, applies MEMU compatibility patches only to those temp copies, builds
minimal Navy `tests/hello` and `tests/dummy` programs for `riscv32`, installs
them into the ramdisk, boots real Nanos-lite on MEMU, and checks for
`Hello World`, `Hello World from Navy-apps`, `Dummy from Navy-apps`, and a final
good trap.

Current scope:

```text
Nanos-lite boot path: pass
Nanos-lite ramdisk loader: pass for hello and dummy Navy programs
Navy direct sys_write/sys_yield path: pass
Nanos-lite SYS_exit to next program: pass for hello -> dummy
Full Navy libc/newlib/compiler-rt hello path: pass through `make pa-nanos-libc-test`;
the temporary compatibility patch excludes `getpass.c`, `stat64r.c`, and
`wcwidth.c` for riscv32
NSlider multi-slide navigation: pass through `make pa-navy-ndl-test`; real
generated slides plus `--key-events` injection verify slide transitions with
different framebuffer checksums
NDL draw app: pass through `make pa-ndl-test`; standalone test exercises
NDL_Init/OpenCanvas/DrawRect/GetTicks/PollEvent/Quit
Flappy Bird miniSDL game: pass through `make pa-bird-test`; PNG sprites load
via stb_image IMG_Load and the game runs 50M instructions without crashing
Nanos-lite execve-style program replacement: pass through `make pa-execve-test`
PAL: not-started
```

## CTE OS Smoke

The following target validates real AM context switching beyond `am-tests i`:

```sh
make pa-cte-os-tests
```

It copies the PA checkout to a temp directory, applies the same compatibility
patches, builds `am-kernels/kernels/yield-os` and
`am-kernels/kernels/thread-os`, and runs bounded MEMU executions. This required
three compatibility pieces: riscv32-nemu `kcontext`, using the trap handler's
returned Context in `trap.S`, and MEMU machine timer interrupt injection when
`mstatus.MIE` and `mtvec` are set.

## Interactive LiteNES/Mario

The following path was added for the user-facing Mario run:

```sh
make mario
```

It builds `build/memu-sdl` with `sdl2-config`, copies the PA checkout to a temp
directory, patches the copied PA AM audio glue, builds
`am-kernels/kernels/litenes` as `riscv32-nemu`, and runs the result with
`--sdl`. Controls are W/A/S/D or arrow keys for the D-pad, U for SELECT, I for
START, J for A, and K for B. On this machine, the PA checkout defaults to
`/Users/wjl/Projects/icspa2025/ICS-PA`; otherwise pass `PA_HOME=/path/to/ICS-PA`.

Audio note: the MEMU audio device exists, but this LiteNES/Mario target has no
sound in the current PA checkout. `am-kernels/kernels/litenes/src/psg.c`
implements only controller reads/writes around `0x4016`; it does not call
`AM_AUDIO_PLAY` or synthesize NES APU samples.

The non-window CI-style smoke for this path passed:

```sh
SDL_VIDEODRIVER=dummy MARIO_MAX_INSTR=2000000 make mario BUILD_DIR=/private/tmp/memu-mario-dummy
```

It rebuilt LiteNES/Mario, printed the LiteNES control banner, and stopped at the
bounded instruction limit as expected.

## Stage 4 Local Scaffold Verification

The following commands passed:

```sh
tools/mkbin/runtime_programs.py tests/images
cmake -S . -B build
cmake --build build
./build/memu --image tests/images/good.bin --batch
./build/memu --image tests/images/bad.bin --batch
./build/memu --image tests/images/infinite-loop.bin --batch --max-instr 100
./build/memu --elf tests/images/good.elf --batch
tools/run-tests.sh ./build/memu
ctest --test-dir build --output-on-failure
make test BUILD_DIR=/private/tmp/memu-stage4-make-final
```

Strict NEMU status: not complete. Real AM hello/dummy/trap artifacts have not
been run yet.

## Stage 4 Required Questions

1. Raw binaries need a MEMU load address convention because they carry no entry
   or segment metadata.
2. ELF loaders use program headers because they describe runtime loadable
   segments; section headers are mainly for linking/debug metadata.
3. `p_filesz` is bytes present in the file; `p_memsz` is bytes needed in guest
   memory, with the extra tail zero-filled for `.bss`-like data.
4. `p_vaddr` is a guest virtual/physical address in this teaching model, not a
   host C pointer, so it must go through `guest_to_host()`.
5. Good trap maps to host exit code 0; bad trap and abort map to nonzero.
6. Bad tests should stay out of the default pass runner because their expected
   host exit code is failure.

## Stage 5 Local Scaffold Verification

The following commands passed:

```sh
tools/mkbin/device_programs.py tests/images
make stage5-test BUILD_DIR=/private/tmp/memu-stage5-build
make test BUILD_DIR=/private/tmp/memu-stage5-build
cmake -S . -B /private/tmp/memu-stage5-cmake
cmake --build /private/tmp/memu-stage5-cmake
ctest --test-dir /private/tmp/memu-stage5-cmake --output-on-failure
```

Strict NEMU status: the later real AM/IOE and app gates pass for bounded
hello/timer/keyboard/display, slider, typing-game, demo, snake, and
LiteNES/Mario runs. Stage 5 has a recorded strict PA2 state: CPU, AM/CTE/IOE,
AM apps, LiteNES/Mario, and bounded FCEUX execution pass; the historical PA
Box ROM archive URL currently returns a login page.

The Stage 5 smoke artifacts are:

```text
tests/images/hello-serial.bin
tests/images/timer.bin
tests/images/keyboard.bin
tests/images/fb-clear.bin
```

## Stage 5 Required Questions

1. MMIO dispatch belongs in `mem_read()` and `mem_write()` so every load/store
   instruction sees the same device behavior.
2. The first device map follows NEMU-style addresses:
   serial `0xa00003f8`, rtc `0xa0000048`, keyboard `0xa0000060`,
   vgactl `0xa0000100`, framebuffer `0xa1000000`.
3. Serial writes flush stdout immediately so batch-mode test output is visible
   without waiting for process exit buffering.
4. Timer uses host monotonic time instead of guest instruction count so guest
   code can observe time even when CPU speed changes.
5. Keyboard is currently a polling stub that returns 0; real host input belongs
   in a later SDL/windowed device pass.
6. Framebuffer is an in-memory ARGB8888 buffer; writing vgactl sync prints a
   checksum so tests can verify display writes without opening a host window.

## Stage 6 Local Scaffold Verification

The following commands passed:

```sh
tools/mkbin/syscall_programs.py tests/images
make stage6-test BUILD_DIR=/private/tmp/memu-stage6-build
make test BUILD_DIR=/private/tmp/memu-stage6-build
cmake -S . -B /private/tmp/memu-stage6-cmake
cmake --build /private/tmp/memu-stage6-cmake
ctest --test-dir /private/tmp/memu-stage6-cmake --output-on-failure
```

Strict NEMU status: not complete. Real Nanos-lite artifacts now pass both the
minimal direct-syscall Navy hello-to-dummy smoke and the official libc/newlib
hello smoke; full Nanos-lite syscall/batch coverage has not been completed yet.

The Stage 6 smoke artifacts are:

```text
tests/images/sys-write.bin
tests/images/sys-brk.bin
tests/images/prog-a.bin
tests/images/prog-b.bin
tests/images/unknown-syscall.bin
```

## Stage 6 Required Questions

1. In MEMU, `ebreak` is the bare-metal good/bad trap, while `ecall` enters the
   syscall handler using the RISC-V ABI registers.
2. User `exit` should not always terminate MEMU because the batch runtime may
   need to load the next user program first.
3. Syscall arguments live in guest registers because the guest ABI is defined
   in guest machine state; host stack addresses are unrelated.
4. The batch runtime can reuse `0x80000000` because only one user program is
   resident at a time in this teaching model.
5. Skipping user/kernel privilege separation keeps control flow simple, but it
   means user code is not isolated from OS memory or device state.

## Stage 7 Local Scaffold Verification

The following commands passed:

```sh
tools/mkbin/fs_programs.py tests/fsimg
tools/mkfs/mkfs.py tests/fsimg/MANIFEST tests/images/ramdisk.img
make stage7-test BUILD_DIR=/private/tmp/memu-stage7-build
make test BUILD_DIR=/private/tmp/memu-stage7-build
cmake -S . -B /private/tmp/memu-stage7-cmake
cmake --build /private/tmp/memu-stage7-cmake
ctest --test-dir /private/tmp/memu-stage7-cmake --output-on-failure
```

Strict NEMU status: PA3 Navy/NDL/miniSDL coverage now includes real Navy libc
hello, NSlider multi-slide navigation with generated slides and key injection,
the standalone NDL test, Flappy Bird with PNG sprite loading, and execve
program replacement. PAL remains unrun and is the outstanding PA3 gap.

The Stage 7 smoke artifacts are:

```text
tests/images/ramdisk.img
tests/fsimg/bin/fs-cat.bin
tests/fsimg/bin/fs-missing.bin
tests/fsimg/share/message.txt
```

## Stage 8 Sv32 Virtual Memory

MEMU implements real RISC-V Sv32 address translation instead of the simplified
linear lookup that `docs/textbook/chapter-09` suggested for the teaching
scaffold. This is a deliberate deviation: strict NEMU alignment requires real
`satp`-based two-level page tables because the real AM `vme.c` programs `satp`
directly, and maintaining a second translation mechanism only for the scaffold
would double the emulator surface. The scaffold and the real PA4 stack share
one MMU.

Emulator changes:

- `satp` CSR (0x180) and `sfence.vma` (a no-op; there is no TLB, tables are
  walked on every access) in `src/isa/rv32i.c`.
- `src/memory/mmu.c` implements the Sv32 walk: two levels, 4 KiB pages, PTE
  format `ppn << 10 | X/W/R/V`. Page-table entries are read through a physical
  reader that bypasses translation. Invalid or permission-violating accesses
  panic with vaddr, pc, access type, level, and PTE value.
- `mem_read`/`mem_write` translate when `satp.MODE = 1` and split unaligned
  accesses that cross a page boundary; `inst_fetch` translates the PC.

Local scaffold verification:

```sh
make stage8-test
```

- `tests/guest/vm/mp_os.c` builds two address spaces that map the same user VA
  (0x40000000 code, 0x40001000 data) to different physical pages, copies the
  same position-independent user loop into both code pages, and alternates the
  two processes on MEMU machine timer interrupts. Each process prints the
  letter it reads from the shared VA, so the alternating output proves same-VA
  isolation plus preemption without any yield or syscall in the user loop.
- `tests/guest/vm/vm_fault.c` enables satp and touches an unmapped VA; the
  test requires the page-fault diagnostic including the vaddr.
- Verified output: 16 alternating timeslices `ABABABABABABABAB`, then
  `PASS: mp-os` and a good trap.

Strict PA4 path:

```sh
make pa-vme-test
```

- `tools/patch-pa-nemu-ioe.py` implements AM `vme.c` `map()` (real Sv32 PTE
  writes with on-demand second-level tables) and `ucontext()`, calls
  `__am_get_cur_as`/`__am_switch` around `user_handler` in `__am_irq_handle`,
  and grows the trap frame `CONTEXT_SIZE` to `(NR_REGS + 4) * XLEN` so the
  Context `pdir` slot lives inside the frame instead of clobbering the
  interrupted stack.
- `tools/patch-pa-nanos-lite.py` gains a VME mode (`MEMU_NANOS_VME=1`):
  `HAS_VME` is enabled, `mm_brk` maps heap pages on demand, and the loader
  `protect()`s a user address space, loads ELF segments into physical pages
  via `map()`, maps an 8-page user stack below 0x80000000, and enters the
  user program with a satp switch.
- Navy user programs link at 0x40000000 through the stock
  `LNK_ADDR = $(if $(VME), 0x40000000, 0x83000000)` logic in
  `navy-apps/scripts/riscv/common.mk`; the runner passes `VME=1` when
  `PA_NANOS_VME=1`, and libos `_sbrk` starts the heap at the linker-provided
  `end` symbol instead of a fixed physical address.
- Verified: official Navy `tests/hello` with full newlib libc prints through
  `printf` while running under Sv32 paging and reaches the bounded
  instruction limit.

## Stage 8 Required Questions

1. A context switch must save at minimum the program counter (mepc), the 31
   general-purpose registers, and the identity of the address space (the satp
   or page-directory pointer). mp-os saves x1-x31 plus mepc per process; the
   AM Context adds `pdir` for the address space.
2. Each process needs an independent stack because the stack holds live call
   frames; if two processes shared one stack, the resumed process would find
   its frames overwritten by the other's pushes and pops.
3. Without virtual memory every program must be linked at (or relocated to) a
   distinct physical range, and loading two builds of the same program at the
   same address is impossible. With paging every process can believe it runs
   at 0x40000000 while the kernel places it in any free physical pages.
4. A virtual address is what guest code issues before translation; a physical
   address is the guest address after the Sv32 walk; a host pointer is a C
   pointer into MEMU's `pmem` array. They convert only through explicit steps:
   `mmu_translate()` for VA to PA and `guest_to_host()` for PA to host.
5. Cooperative yield depends on the process voluntarily trapping into the
   kernel; timer preemption is driven by an external interrupt, so the kernel
   regains control even when a process never yields. The mp-os user loop
   contains no ecall at all and still gets switched.
6. The timer cannot rely on syscalls because a buggy, malicious, or simply
   compute-bound program may never issue one; only a hardware interrupt
   guarantees the kernel periodically regains the CPU.

## Stage 7 Required Questions

1. The ramdisk is the byte array loaded from a host image; the file system is
   the table and fd logic that maps names and offsets onto that byte array.
2. Each fd needs its own `open_offset` because the same file can be opened more
   than once and each handle has an independent read position.
3. Paths are guest strings in guest memory, so syscall handling must copy them
   with `mem_read()` instead of treating them as host pointers.
4. `read` returns the actual byte count and returns 0 at EOF.
5. The first SFS does not support create/delete because fixed file tables and
   immutable file sizes are enough for loader and read-only app resources.
6. Once the loader reads from `/bin` in the ramdisk, host paths are only needed
   to locate the ramdisk image, not individual guest programs.

## Stage 3 Required Questions

1. `snpc` is the sequential next PC and `dnpc` is the dynamically chosen next
   PC. Keeping both avoids mixing normal, branch, and jump PC updates.
2. B-type immediates are easy to get wrong because their bits are split across
   non-contiguous instruction fields and bit 0 is implicit zero.
3. For `0xffffffff` and `0`, `slt` sees `-1 < 0` and returns 1, while `sltu`
   sees `4294967295 < 0` and returns 0.
4. `lb` sign-extends an 8-bit byte; `lbu` zero-extends it.
5. `jalr` clears the target low bit because the RISC-V spec reserves it and
   requires an even target address.
6. Unsupported instructions must abort with context; treating them as `nop`
   hides bugs and lets guest state drift silently.

The monitor smoke test covers:

```text
help
info r
si
p 1 + 2 * 3
p $a1
x 3 0x80000000
p *0x80000000
w $a1
c
d 1
q
```

The generated expression test covers fixed precedence/associativity cases plus
deterministic random arithmetic, comparison, logical, register, and dereference
expressions:

```sh
tests/smoke/run_expr_generated.py ./build/memu tests/images/stage1-trap.bin
```

## Stage 2 Required Questions

1. GDB sees MEMU as a host process, but it does not naturally expose guest PC,
   guest registers, guest memory, or guest watchpoints.
2. `x` accepts expressions so addresses can be computed from registers such as
   `$pc + 8`, not only typed as numeric constants.
3. `*` is dereference when it appears at the start of an expression or after
   another operator or `(`; otherwise it is multiplication.
4. Watchpoints are checked after each instruction so they catch the first
   instruction that changes the expression value.
5. Expression failures should print an error and keep the monitor running.

## Stage 1 Required Questions

1. Guest address `0x80000000` is an address in the emulated machine, not a host
   C pointer. It must be translated to an offset inside `pmem`.
2. `mem_read()` avoids `*(uint32_t *)` so unaligned access and host byte order do
   not leak into the guest model.
3. `addi a1, zero, 42` changes `a1` and advances `pc`; `zero` remains 0.
4. `x0` must stay 0 because RV32I defines it as the hardwired zero register.
5. `ebreak` records `pc` as the trap instruction address, currently
   `0x80000008` for `stage1-trap.bin`.
6. A raw binary is just bytes loaded at a fixed address. ELF carries headers,
   segments, symbols, and metadata, so Stage 1 intentionally avoids it.

## Important Files

- `CMakeLists.txt`: C11 build, warning flags, and CTest smoke test.
- `Makefile`: fallback build path for systems without CMake.
- `tests/smoke.sh`: Stage 0 smoke test for CLI and built-in self-test.
- `include/memu/common.h`: common constants, panic, and assert helpers.
- `src/main.c`: CLI entry point.
- `src/loader/image.c`: raw image loader.
- `src/loader/image.c`: raw image loader and minimal ELF32 little-endian
  RISC-V loader.
- `include/memu/device.h`: Stage 5 MMIO addresses and device API.
- `src/device/device.c`: serial, rtc, keyboard stub, vgactl, framebuffer, and
  device trace implementation.
- `include/memu/syscall.h`: Stage 6 syscall numbers and ecall handler API.
- `include/memu/batch.h`: minimal batch runtime state.
- `include/memu/ramdisk.h`: host-side ramdisk byte array API.
- `include/memu/fs.h`: SFS file table, fd table, and fs loader API.
- `src/os/syscall.c`: `write`, `exit`, `brk`, syscall trace, and unknown
  syscall abort handling; Stage 7 also handles `open/openat`, `read`, `lseek`,
  and `close`.
- `src/os/batch.c`: batch-list loader and exit-to-next-program control flow.
- `src/os/ramdisk.c`: loads and bounds-checks the host ramdisk image.
- `src/os/fs.c`: parses MEMU SFS, implements fd operations, special files, and
  raw program loading from `/bin`.
- `src/memory/memory.c`: guest memory, MMIO dispatch, address checks, and
  little-endian access.
- `src/cpu/cpu.c`: CPU reset, execution loop, and register dump.
- `src/isa/rv32i.c`: minimal RV32I decode for `lui`, `addi`, `jal`, and `ebreak`.
- `src/isa/rv32i.c`: Stage 3 RV32I decode and execution for common integer,
  load/store, branch, jump, and system instructions.
- `tests/images/stage1-trap.bin`: raw Stage 1 guest image.
- `tests/stage1/run_stage1.sh`: Stage 1 regression test.
- `src/monitor/monitor.c`: monitor command loop and command handlers.
- `src/monitor/expr.c`: tokenizer and recursive expression evaluator.
- `src/monitor/watchpoint.c`: fixed-size watchpoint pool.
- `tests/smoke/run_monitor_commands.sh`: Stage 2 monitor regression test.
- `tests/smoke/run_expr_generated.py`: generated expression regression test.
- `tests/isa/run_rv32i.sh`: Stage 3 RV32I regression test.
- `tests/runtime/run_stage4.sh`: Stage 4 runtime/loader regression test.
- `tests/devices/run_stage5.sh`: Stage 5 MMIO device regression test.
- `tests/syscall/run_stage6.sh`: Stage 6 syscall and batch-list regression
  test.
- `tests/fs/run_stage7.sh`: Stage 7 ramdisk/fs regression test.
- `tests/toolchain/run_toolchain.sh`: builds and runs the RV32 GCC ELF smoke
  test when `riscv64-unknown-elf-gcc` is available.
- `tools/run-tests.sh`: default passing test runner for raw and ELF artifacts.
- `tools/run-pa-cpu-tests.sh`: copies a PA checkout, builds real
  `am-kernels/tests/cpu-tests` for `riscv32-nemu`, and runs them on MEMU.
- `tools/run-pa-am-tests.sh`: copies a PA checkout, builds real AM hello and
  `am-tests` h/t/k/v/d/a artifacts, patches this checkout's temp riscv32-nemu
  AM CTE/audio/devscan gaps, and validates them on MEMU.
- `tools/run-pa-app-tests.sh`: copies a PA checkout, builds real AM apps
  including slider, typing-game, demo, snake, bad-apple, and LiteNES/Mario, and
  validates bounded render/status output or sustained execution on MEMU.
- `tools/run-pa-cte-os-tests.sh`: copies a PA checkout, builds real
  `yield-os` and `thread-os`, applies CTE compatibility patches to the temp PA
  tree, and validates yield/context-switch/timer-interrupt behavior on MEMU.
- `tools/run-pa-nanos-tests.sh`: copies a PA checkout, builds real Nanos-lite
  with selected Navy apps/tests, and validates the Nanos loader/syscall/ramdisk
  path on MEMU. It supports the direct hello batch, full libc hello, and the
  bounded NSlider NDL/miniSDL smoke.
- `tools/patch-pa-nemu-ioe.py`: patches only copied PA temp trees to enable
  riscv32-nemu AM audio/devscan behavior needed by MEMU compatibility tests.
- `tools/patch-pa-nanos-lite.py`: patches only copied PA temp Nanos/Navy trees
  for the current minimal PA3 smoke gate.
- `tools/build-guest-tests.sh`: cross-compiles MEMU-local RV32 ELF smoke tests.
- `tools/mkbin/stage1_trap.py`: generator for the Stage 1 raw image.
- `tools/mkbin/rv32i_programs.py`: generator for Stage 3 raw RV32I images.
- `tools/mkbin/runtime_programs.py`: generator for Stage 4 good/bad/loop/ELF
  fixtures.
- `tools/mkbin/device_programs.py`: generator for Stage 5 serial/timer/kbd/fb
  fixtures.
- `tools/mkbin/syscall_programs.py`: generator for Stage 6 syscall/batch
  fixtures.
- `tools/mkbin/fs_programs.py`: generator for Stage 7 fs user programs and
  ramdisk manifest source tree.
- `tools/mkfs/mkfs.py`: packs a manifest into `tests/images/ramdisk.img`.
- `tests/guest/toolchain/`: source, linker script, and start code for the
  RV32 GCC ELF smoke image.
- `tools/artifacts/`: local staging area for later guest artifacts.

## Notes For Next Session

- Stage 8 is complete both as a local scaffold (`make stage8-test`) and under
  the strict NEMU alignment rules (`make pa-vme-test` plus the full pa-*
  regression). PAL/仙剑 is the remaining optional PA3 app target.
- SDL/interactive polish (2026-07-17): the MEMU SDL keymap now covers the full
  AM key list (letters, digits, symbols) so typing-game, NSlider digits+G goto,
  and Flappy Bird "any key" all work; closing the SDL window is a clean
  `MEMU_STATE_QUIT` exit (exit code 0, no ABORT register dump); the NDL shim
  centers small canvases and scales oversized ones to fit the 400x300 display
  (bird's 287x400 canvas letterboxes at 215x300 — this was why bird-sdl showed
  no graphics before); `NSLIDER_SLIDES=/path/to/images make nslider-sdl` shows
  user slides via `tools/mkbin/convert_slides.py` (sips resize + libbmp-format
  repack, patches nslider's slide count).
- PA compatibility builds are cached per configuration in `~/.cache/memu-pa`
  (`MEMU_PA_CACHE_DIR` overrides, `MEMU_PA_FRESH=1` forces clean); the cache
  auto-invalidates when the run/patch tooling changes, and each run re-rsyncs
  from PA_HOME and re-applies patches, so newlib is only rebuilt on the first
  run of a configuration.
- Stage 1 uses `a0 == 0` as good trap and keeps `a1 = 42` as the visible
  computation result.
- `ebreak` records `pc` as the trap instruction address, not the following PC.
- PA2 is recorded as pass with the public FCEUX test ROM. PA3 real
  Nanos-lite/Navy progress has direct-syscall hello-to-dummy, official Navy
  libc/newlib hello, NSlider multi-slide navigation, the standalone NDL test,
  Flappy Bird, and execve program replacement passes; PAL is the remaining
  PA3 app target.
- Real NEMU `am-tests` and graphics apps are still compatibility targets; the
  current Stage 5 package provides MEMU-local device fixtures and host-visible
  checksum/trace validation.
- Real Nanos-lite remains a compatibility target; the current Stage 6 package
  provides MEMU-local syscall and batch-list fixtures, and `make pa-nanos-tests`
  now validates one real Nanos-lite + Navy hello-to-dummy smoke.
- Real Navy-apps/miniSDL remain compatibility targets; the current Stage 7
  package provides MEMU-local ramdisk, fd, special-file, and fs-loader fixtures.
  The local checkout now has `navy-apps`; the official libc/newlib hello,
  NSlider multi-slide navigation, standalone NDL test, and Flappy Bird paths
  all pass through real NDL/miniSDL; PAL remains future work.
- `toolchain-basic.elf` is a real cross-compiled RV32 ELF smoke test, but it is
  not a substitute for AM `cpu-tests`, AM IOE tests, LiteNES, or Mario.
- New sessions should verify the current tree before implementing the next
  stage because memory may be summarized, but project files are authoritative.
