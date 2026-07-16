# MEMU Strict NEMU Alignment

This project must target the real NEMU PA software stack, not only local smoke
programs. A MEMU stage is complete only when its NEMU-aligned acceptance targets
have run and are recorded in `docs/compat-status.md`.

## Status Vocabulary

Use these terms consistently:

- `local scaffold`: MEMU-local code and smoke tests for a stage exist.
- `NEMU-aligned complete`: the corresponding NEMU PA artifacts have run with
  the expected behavior.
- `blocked`: a real artifact was attempted and the blocking layer is known.
- `not-started`: no real artifact attempt has been made.

Never call a stage "complete" without saying which meaning is intended. In
handoff files, prefer these explicit fields:

```text
Local scaffold implemented through: Stage N
NEMU-aligned complete through: Stage M
Active strict gate: ...
```

## Current Strict Position

Current local scaffolds exist through Stage 7, but strict NEMU alignment has not
passed PA2 yet. The project must return to the PA2 acceptance chain before
claiming Stage 5 completion.

The active strict gate is:

```text
Stage 3 cpu-tests
-> Stage 4 AM hello/dummy/trap
-> Stage 5 AM IOE tests
-> Stage 5 apps: slider, typing-game, demo, bad-apple/snake
-> Stage 5 challenge: LiteNES/Mario
```

Stage 6 and Stage 7 local scaffolds are useful, but they do not prove PA3
alignment until real Nanos-lite and Navy-apps artifacts run.

## Stage Completion Rules

| Stage | Local Scaffold Is Not Enough Until |
| --- | --- |
| Stage 3 | Real `am-kernels/tests/cpu-tests` no-IO subset passes |
| Stage 4 | Real AM hello/dummy/trap artifacts pass |
| Stage 5 | Real AM IOE tests and representative AM apps pass |
| Stage 6 | Real Nanos-lite minimal syscall/batch users pass |
| Stage 7 | Real Navy text/draw apps and NSlider-class app pass |
| Stage 8 | Real PA4 yield/context/vmem/timer tests pass while PA3 apps still work |

## PA2 Must-Have Targets

Stage 5 must not be called NEMU-aligned complete until these are attempted and
recorded:

```text
am-tests timer-test
am-tests keyboard-test
am-tests display-test
slider
typing-game
demo
bad-apple or snake
LiteNES/Mario status: pass, fail, or blocked with layer
```

Mario does not need to be the first PA2 app, but if Stage 5 is claimed complete,
Mario/LiteNES must at least have a recorded status and a known blocker if not
passing.

## Required Artifact Discipline

When using a real NEMU artifact, record:

```text
program:
source repo/path:
build command:
artifact path:
MEMU command:
result:
first failing layer:
next action:
```

Store local copies or notes under `tools/artifacts/` when the artifact cannot be
checked into the repository.
