# MEMU Project Handoff Status

Last updated: 2026-07-17

This file is the cross-device handoff for MEMU. Read it before changing code.
The authoritative checkout is:

```text
/Users/wjl/Projects/MEMU
```

Do not use `/Users/wjl/Documents/MEMU`; that is an older copy.

## One-line Status

The local teaching emulator scaffold is implemented through Stage 8, and the
strict NEMU alignment gates are complete through Stage 8: real CPU, AM/IOE,
AM app, LiteNES/Mario and FCEUX bounded, CTE yield-os/thread-os, Nanos-lite
batch, full Navy libc hello, NSlider multi-slide navigation, standalone NDL,
Flappy Bird, execve program replacement, and Sv32 virtual memory (local mp-os
plus Navy hello under Nanos-lite HAS_VME paging) all pass. PAL/仙剑 remains
the outstanding optional PA3 app.

## Stage Status

| Area | Status | Meaning |
| --- | --- | --- |
| Stage 0 | complete | macOS/Linux setup, CMake/Make skeleton, documented workflow |
| Stage 1 | complete | TRM core, RV32 register state, memory, good/bad trap |
| Stage 2 | complete | monitor, commands, expression evaluator, watchpoints |
| Stage 3 | complete | RV32I execution plus local RV32M/CSR extensions used by later guests |
| Stage 4 | complete | runtime loop, raw/ELF loader, instruction limit, trap/error reporting |
| Stage 5 | complete | serial, timer, keyboard, framebuffer, audio, SDL/Mario support; real AM IOE tests and AM apps pass |
| Stage 6 | complete | ecall/syscalls, brk, batch-list, program handoff; real Nanos-lite batch users pass |
| Stage 7 | complete | ramdisk, SFS/fixed file table, fd operations, user fs loader; real Navy apps and NSlider pass |
| Stage 8 | complete | Sv32 virtual memory, mp-os multiprogramming scaffold, timer preemption; strict PA4 gate passes via `make pa-vme-test` |

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
  libndl, renders real generated slides, and verifies keyboard navigation via
  `--key-events` injection through `make pa-navy-ndl-test`.
- Standalone NDL draw/event/timer test passes through `make pa-ndl-test`.
- Flappy Bird builds with libminiSDL/libSDL_image/libfixedptc, loads PNG
  sprites through stb_image, and runs bounded through `make pa-bird-test`.
- execve program replacement passes through `make pa-execve-test`.
- Sv32 virtual memory: the local mp-os two-process scaffold passes through
  `make stage8-test`, and official Navy hello runs under Nanos-lite HAS_VME
  paging in USER_SPACE 0x40000000 through `make pa-vme-test`.

Not complete under strict acceptance:

- PAL/仙剑, which needs the full miniSDL stack plus game assets.

The compatibility tables in `docs/compat-status.md` record per-program status
and commands; `docs/nemu-strict-alignment.md` remains the completion rule.

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
make pa-ndl-test PA_HOME=/path/to/ICS-PA
make pa-bird-test PA_HOME=/path/to/ICS-PA
make pa-execve-test PA_HOME=/path/to/ICS-PA
make pa-vme-test PA_HOME=/path/to/ICS-PA
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

Other interactive SDL-window targets (close the window to stop; closing the
window is a clean exit, not an error):

```sh
make snake-sdl     # AM snake, arrow keys + Q
make typing-sdl    # AM typing-game, type falling letters
make nslider-sdl   # NSlider slides, J/Down next, K/Up previous, digits+G goto
make bird-sdl      # Flappy Bird, any key to flap (title screen appears after
                   # a short PNG-decoding delay)
```

Show your own slides in NSlider (images are resized to 400x300 via sips and
converted to the BMP format libbmp expects):

```sh
make nslider-sdl NSLIDER_SLIDES=/path/to/images
```

The PA compatibility builds are cached per configuration under
`~/.cache/memu-pa` (override with `MEMU_PA_CACHE_DIR`), so repeated runs skip
the newlib rebuild and take seconds. The cache is invalidated automatically
when the patch tooling changes; `MEMU_PA_FRESH=1` forces a clean rebuild.

The current LiteNES source does not produce NES APU samples, so no Mario sound
is expected even though MEMU's AM audio device exists and is tested separately.

## Current Compatibility Implementation

The real PA compatibility scripts sync the PA trees into a persistent
per-configuration cache directory (`~/.cache/memu-pa`) and patch only those
copies. They do not modify the PA checkout, and library builds (newlib in
particular) are reused across runs:

- `tools/run-pa-nanos-tests.sh`: selects a Navy app/test, builds the temporary
  ramdisk, builds Nanos-lite, boots it on MEMU, and checks output.
- `tools/patch-pa-nanos-lite.py`: adapts cached Nanos-lite/Navy trees to
  MEMU's current syscall, loader, and full-libc path.
- `tools/patch-pa-navy-ndl.py`: supplies the current syscall-backed NDL and
  miniSDL timer/event/video implementation. NDL centers the canvas on the
  400x300 display and scales oversized canvases down to fit (Flappy Bird's
  287x400 canvas renders letterboxed at 215x300).
- `tools/mkbin/convert_slides.py`: converts user images into
  libbmp-compatible 400x300 slides for `NSLIDER_SLIDES`.
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

Stage 8 is complete under the strict rules. Remaining and optional work:

1. PAL/仙剑 bring-up on the Navy/miniSDL stack, including game assets.
2. Optional performance work: a small software TLB in `src/memory/mmu.c` if
   long VME-enabled runs become slow (translation currently walks the page
   tables on every access).
3. Optional PA4 depth: run more programs under `MEMU_NANOS_VME=1` (file-test,
   NSlider) and a scheduler with multiple resident user processes.

Do not regress the non-VME test paths: `MEMU_NANOS_VME` defaults to unset and
all pre-Stage-8 targets must keep passing unchanged.

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
git@github.com:Joylllll1/MEMU.git
https://github.com/Joylllll1/MEMU.git
```

The current checkout uses the SSH URL. On another device, use SSH if a
GitHub key is configured; otherwise use the HTTPS URL after `gh auth login` or
another credential helper is configured.

The complete initial MEMU scaffold and this handoff file are committed on
`main`. Do not push the stale `/Users/wjl/Documents/MEMU` copy.
