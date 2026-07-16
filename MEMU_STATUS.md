# MEMU Project Handoff Status

Last updated: 2026-07-16

This file is the cross-device handoff for MEMU. Read it before changing code.
The authoritative checkout is:

```text
/Users/wjl/Projects/MEMU
```

Do not use `/Users/wjl/Documents/MEMU`; that is an older copy.

## One-line Status

The local teaching emulator scaffold is implemented through Stage 7. Real NEMU
PA compatibility has passed the CPU, AM/IOE, AM app, LiteNES/Mario bounded, and
CTE smoke gates. PA3/Navy work is active: real Nanos-lite direct-syscall batch,
full Navy libc/newlib hello, and a bounded NSlider first-frame render pass;
full NDL interaction, real slide assets, Flappy Bird, PAL, execve-style program
replacement, and Stage 8 virtual memory remain incomplete.

## Stage Status

| Area | Status | Meaning |
| --- | --- | --- |
| Stage 0 | complete | macOS/Linux setup, CMake/Make skeleton, documented workflow |
| Stage 1 | complete | TRM core, RV32 register state, memory, good/bad trap |
| Stage 2 | complete | monitor, commands, expression evaluator, watchpoints |
| Stage 3 | complete | RV32I execution plus local RV32M/CSR extensions used by later guests |
| Stage 4 | complete | runtime loop, raw/ELF loader, instruction limit, trap/error reporting |
| Stage 5 | complete locally | serial, timer, keyboard, framebuffer, audio, SDL/Mario support |
| Stage 6 | complete locally | ecall/syscalls, brk, batch-list, program handoff |
| Stage 7 | complete locally | ramdisk, SFS/fixed file table, fd operations, user fs loader |
| Stage 8 | not started | multiprogramming, virtual memory, interrupts as a full stage |

Important: “complete locally” means the MEMU scaffold and focused tests pass. It
does not automatically mean the corresponding NEMU PA stage is complete.
Strict acceptance is recorded in `docs/compat-status.md` and governed by
`docs/nemu-strict-alignment.md` and `docs/nemu-stage-acceptance.md`.

## NEMU PA Compatibility

Passed real artifact gates:

- Real `am-kernels/tests/cpu-tests`: 35/35 tests pass.
- Real AM hello, timer, keyboard, display, interrupt/yield, devscan, and audio
  smoke tests pass through `make pa-am-tests`.
- Real AM apps slider, typing-game, demo, bad-apple, snake, and LiteNES/Mario
  bounded runs pass through `make pa-app-tests`.
- Public FCEUX `nestest.nes` bounded execution passes through
  `make pa-fceux-test`.
- Real `yield-os` and `thread-os` CTE/context-switch smoke passes through
  `make pa-cte-os-tests`.
- Real Nanos-lite with Navy `tests/hello` -> `tests/dummy` direct-syscall batch
  passes through `make pa-nanos-tests`.
- Real Navy libc/newlib/compiler-rt `tests/hello` passes through
  `make pa-nanos-libc-test`.
- Official Navy `apps/nslider` builds with real libc, libbmp, libminiSDL, and
  libndl, renders a bounded first frame through `/dev/fb`, and reaches the
  instruction limit through `make pa-navy-ndl-test`.

Not complete under strict acceptance:

- NSlider keyboard navigation and real slide assets. The current smoke copies
  `projectn.bmp` into placeholder slide files because the PA checkout has no
  generated NSlider slide assets.
- A standalone NDL draw app.
- Full interactive miniSDL behavior, Flappy Bird, and PAL/仙剑.
- Full Nanos-lite process model and execve-style program replacement.
- Stage 8 virtual memory and full PA4 integration.

The current strict summary is intentionally conservative: NSlider is recorded
as `fail` in `docs/compat-status.md` because it renders only a bounded first
frame and has not yet demonstrated interaction.

## Most Useful Commands

Build the emulator:

```sh
cd /Users/wjl/Projects/MEMU
make
```

Run the complete local regression:

```sh
make test
```

Run with the Makefile helpers:

```sh
make run IMAGE=tests/images/stage1-trap.bin
make batch IMAGE=tests/images/stage1-trap.bin
make monitor IMAGE=tests/images/stage1-trap.bin
make stage7-test
```

Run real PA compatibility gates. The default PA checkout is expected at
`/Users/wjl/Projects/icspa2025/ICS-PA`; otherwise provide `PA_HOME`:

```sh
make pa-cpu-tests PA_HOME=/path/to/ICS-PA
make pa-am-tests PA_HOME=/path/to/ICS-PA
make pa-app-tests PA_HOME=/path/to/ICS-PA
make pa-fceux-test PA_HOME=/path/to/ICS-PA
make pa-cte-os-tests PA_HOME=/path/to/ICS-PA
make pa-nanos-tests PA_HOME=/path/to/ICS-PA
make pa-nanos-libc-test PA_HOME=/path/to/ICS-PA
make pa-navy-ndl-test PA_HOME=/path/to/ICS-PA
```

Use a separate build directory for repeatable verification:

```sh
make test BUILD_DIR=/private/tmp/memu-test
make pa-navy-ndl-test BUILD_DIR=/private/tmp/memu-pa-navy-ndl PA_HOME=/path/to/ICS-PA
```

Build and run interactive LiteNES/Mario locally:

```sh
make mario PA_HOME=/path/to/ICS-PA
```

The current LiteNES source does not produce NES APU samples, so no Mario sound
is expected even though MEMU's AM audio device exists and is tested separately.

## Current Compatibility Implementation

The real PA compatibility scripts copy the PA trees into a temporary directory
and patch only those copies. They do not modify the PA checkout:

- `tools/run-pa-nanos-tests.sh`: selects a Navy app/test, builds the temporary
  ramdisk, builds Nanos-lite, boots it on MEMU, and checks output.
- `tools/patch-pa-nanos-lite.py`: adapts temporary Nanos-lite/Navy trees to
  MEMU's current syscall, loader, and full-libc path.
- `tools/patch-pa-navy-ndl.py`: supplies the current syscall-backed NDL and
  miniSDL timer/event/video implementation for the bounded NSlider smoke.
- `Makefile`: exposes `pa-nanos-libc-test` and `pa-navy-ndl-test` in addition to
  the local stage targets.

Known build warnings from the Navy compatibility build include `realpath`
messages caused by the PA Makefiles on macOS and repeated `_GNU_SOURCE`
redefinition warnings. They do not currently fail the build.

## Files To Read First

Required agent instructions:

1. `AGENTS.md`
2. `docs/stage-progress.md`
3. `docs/roadmap.md`
4. `docs/README.md`
5. `docs/textbook/README.md`
6. The matching `docs/textbook/chapter-*.md`
7. The matching `docs/stages/stage-XX-*.md`
8. `docs/nemu-stage-acceptance.md`
9. `docs/nemu-strict-alignment.md`

For compatibility work, also read:

- `docs/compat-status.md`
- `docs/nemu-compatibility.md`
- `docs/textbook/chapter-10-nemu-compatibility.md`

`docs/stage-progress.md` remains the authoritative detailed handoff. This file
is the compact cross-device summary and should be updated whenever the current
stage, compatibility status, commands, or blockers change.

## Next Recommended Work

Continue compatibility work before starting Stage 8:

1. Replace placeholder NSlider slide assets with real generated assets, or add a
   documented artifact import step for them.
2. Add an automated input injection path and verify NSlider keyboard navigation
   through multiple slides.
3. Run a small standalone NDL draw app and an event/timer app.
4. Bring up Flappy Bird or another miniSDL application with real assets.
5. Implement full Nanos-lite program replacement/execve behavior.
6. Only then begin Stage 8 by reading
   `docs/textbook/chapter-09-multiprogramming-vmem-interrupts.md` and
   `docs/stages/stage-08-multiprogramming-vmem.md` completely.

Do not claim Stage 7 NEMU-aligned completion merely because local Stage 7 tests
pass. Do not claim PA3/C4 completion until a graphical Navy app is interactive.

## Git Handoff

The GitHub repository is `Joylllll1/MEMU`, with default branch `main`. The
initial local commit is `ff7fbc6` (`document MEMU project handoff status`).
Before continuing from another device:

```sh
cd /Users/wjl/Projects/MEMU
git remote -v
git status --short --branch
git log --oneline --decorate -5
```

Expected remote:

```text
https://github.com/Joylllll1/MEMU.git
```

The complete initial MEMU scaffold and this handoff file are committed on
`main`. Do not push the stale `/Users/wjl/Documents/MEMU` copy.
