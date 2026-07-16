# MEMU Agent Guide

This file is the required starting point for any LLM or coding agent working on
MEMU. Read it before changing code.

## Project Root

The MEMU project root is:

```text
/Users/wjl/Projects/MEMU
```

If your current working directory is not this path, stop and switch to the
project root before reading, editing, building, or testing. Do not use similarly
named copies such as `/Users/wjl/Documents/MEMU` as the authoritative project.

## Project Mission

MEMU is a small teaching emulator inspired by the NEMU PA route. The first
target is a readable RV32I emulator that grows stage by stage toward AM,
Nanos-lite, Navy-apps, and representative NEMU PA artifacts.

Do not skip stages. Each stage should add one clear layer of the machine and
must leave the repository buildable and testable.

MEMU must strictly align with NEMU PA acceptance. Local smoke tests are useful
but are not enough to mark a stage complete. A stage is NEMU-aligned complete
only when the corresponding real NEMU PA artifacts are run and their status is
recorded in `docs/compat-status.md`.

## Required Reading Order

Before implementing a stage, read these files in order:

1. `docs/stage-progress.md`
2. `docs/roadmap.md`
3. `docs/README.md`
4. `docs/textbook/README.md`
5. The matching textbook chapter for the stage
6. `docs/stages/stage-XX-*.md` for the stage being implemented
7. `docs/nemu-stage-acceptance.md`
8. `docs/nemu-strict-alignment.md`
9. The relevant source files under `src/` and `include/`

The textbook chapter is the experiment instruction. The stage file is the
acceptance checklist. Do not treat `docs/stages/` as the full experiment guide.

For compatibility work after Stage 8, also read:

- `docs/nemu-compatibility.md`
- `docs/textbook/chapter-10-nemu-compatibility.md`

## Where To Find Experiment Instructions

If you are asked to "do Stage N" or "continue the experiment", find the
instructions like this:

| Work item | Primary instruction | Acceptance file |
| --- | --- | --- |
| Stage 0 | `docs/textbook/chapter-00-macos-and-linux.md` and `docs/textbook/chapter-01-project-skeleton.md` | `docs/stages/stage-00-project-setup.md` |
| Stage 1 | `docs/textbook/chapter-02-trm-core.md` | `docs/stages/stage-01-trm-core.md` |
| Stage 2 | `docs/textbook/chapter-03-debugger.md` | `docs/stages/stage-02-debugger.md` |
| Stage 3 | `docs/textbook/chapter-04-rv32i-exec.md` | `docs/stages/stage-03-rv32i-exec.md` |
| Stage 4 | `docs/textbook/chapter-05-runtime-loader-tests.md` | `docs/stages/stage-04-runtime-loader-tests.md` |
| Stage 5 | `docs/textbook/chapter-06-devices-am.md` | `docs/stages/stage-05-devices-am.md` |
| Stage 6 | `docs/textbook/chapter-07-syscall-batch.md` | `docs/stages/stage-06-syscall-batch.md` |
| Stage 7 | `docs/textbook/chapter-08-filesystem-apps.md` | `docs/stages/stage-07-filesystem-apps.md` |
| Stage 8 | `docs/textbook/chapter-09-multiprogramming-vmem-interrupts.md` | `docs/stages/stage-08-multiprogramming-vmem.md` |
| Compatibility | `docs/textbook/chapter-10-nemu-compatibility.md` | `docs/nemu-compatibility.md` |

If the user asks for a stage and you do not know which document applies, inspect
`docs/README.md`, `docs/textbook/README.md`, and `docs/roadmap.md`. If the
documents disagree, follow this priority:

1. `docs/stage-progress.md` for current status
2. The matching `docs/textbook/chapter-*.md` for implementation steps
3. The matching `docs/stages/stage-*.md` for completion criteria
4. `docs/nemu-stage-acceptance.md` for NEMU PA alignment
5. `docs/nemu-strict-alignment.md` for the rule that smoke tests are not enough
6. `docs/roadmap.md` for broad project direction

When still unsure, do not invent requirements. State the ambiguity, cite the
documents that conflict, and make the smallest implementation that satisfies
the current stage without skipping ahead.

## What "Doing An Experiment" Means

For MEMU, an experiment is not just writing code. A complete experiment cycle
means:

- Read the relevant textbook chapter completely.
- Identify the chapter checkpoints and required commands.
- Implement one checkpoint at a time when the chapter is structured that way.
- Run the checkpoint commands before moving to the next chunk.
- Finish with the matching stage acceptance checklist.
- Run or explicitly mark the NEMU-aligned artifact targets for that stage.
- Record the final result in `docs/stage-progress.md`.

If a textbook chapter includes required questions, answer them briefly in the
final report or add notes to `docs/stage-progress.md` when they affect later
work.

## Stage Workflow

For every stage:

1. Confirm the current completed stage from `docs/stage-progress.md`.
2. Read the matching textbook chapter completely.
3. Read the target stage document completely.
4. Inspect the current code before editing.
5. Implement only the target stage unless a small supporting cleanup is needed.
6. Add or update focused tests for the new behavior.
7. Run the documented verification commands.
8. Update `docs/stage-progress.md` with completed stage, verification commands,
   important files, and known limitations.
9. Update `docs/compat-status.md` for real NEMU PA artifacts. Do not write
   "complete" for a stage whose NEMU artifacts are still `not-started`.

## Engineering Rules

- Use C11.
- Keep the code small and readable.
- Prefer explicit state and simple functions over clever abstractions.
- Do not introduce heavy dependencies before the stage that needs them.
- Do not silently ignore unsupported instructions, invalid memory accesses, or
  guest traps. Report them clearly.
- Keep macOS as the primary host for MEMU itself.
- Build guest artifacts outside MEMU when needed, such as Linux, Docker, Lima,
  UTM, or a remote machine, and stage them under `tools/artifacts/`.

## Build And Verification

The preferred build path is CMake:

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The fallback build path is Make:

```sh
make
make test
```

For stage-specific commands, follow the target file under `docs/stages/`.

## Current Local Notes

- `docs/stage-progress.md` is the authoritative handoff file between sessions.
- Local scaffold is implemented through Stage 7: ramdisk, file system, fs
  loader, syscalls, MMIO devices, monitor, expression/watchpoint support, RV32I
  plus the compatibility instructions already recorded there.
- Strict NEMU-aligned progress has passed the real PA CPU gate, AM/IOE smoke
  gate, AM app gate, LiteNES/Mario bounded render gate, and real
  `yield-os`/`thread-os` CTE smoke.
- `make pa-nanos-tests` now passes a minimal real Nanos-lite + Navy
  hello-to-dummy batch gate. This is not full PA3 completion;
  libc/newlib/compiler-rt, NDL, miniSDL apps, PAL, and execve-style Nanos-lite
  behavior remain active work.
- FCEUX bounded execution passes through `make pa-fceux-test` with public
  `nestest.nes`; the historical PA Box ROM URL currently returns a login page.
- The authoritative project is `/Users/wjl/Projects/MEMU`. Ignore similarly
  named stale copies such as `/Users/wjl/Documents/MEMU`.
