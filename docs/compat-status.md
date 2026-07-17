# MEMU Compatibility Status

这张表记录 MEMU 对 NEMU PA riscv32 软件栈的真实运行状态。状态只能使用：

```text
not-started
blocked
fail
pass
```

不要写“差不多”。如果程序能启动但不能交互，就写 `fail`，并在 Notes 里说明卡在哪层。

Important: MEMU-local smoke rows may be `pass`, but they do not make the
corresponding NEMU PA stage complete. Stage completion follows
`docs/nemu-strict-alignment.md`.

Current strict summary:

```text
Local scaffold implemented through: Stage 7
NEMU-aligned complete through: Stage 5 AM app smoke gate
Active gate: PA2 FCEUX bounded execution passes with a public NES test ROM; PA3 real Navy libc hello, NSlider multi-slide navigation, Flappy Bird, and execve program replacement pass; PAL remains not-started.
```

| Program | Layer | Status | Last Run | Notes |
| --- | --- | --- | --- | --- |
| MEMU hello-serial.bin | Device smoke | pass | 2026-07-15 | `make stage5-test BUILD_DIR=/private/tmp/memu-stage5-build` |
| MEMU timer.bin | Device smoke | pass | 2026-07-15 | reads monotonic rtc low word until it changes |
| MEMU keyboard.bin | Device smoke | pass | 2026-07-15 | polling stub returns 0 and device trace verifies read |
| MEMU fb-clear.bin | Device smoke | pass | 2026-07-15 | writes framebuffer and validates sync checksum output |
| MEMU sys-write.bin | Syscall smoke | pass | 2026-07-15 | `write` and `exit` through ecall |
| MEMU sys-brk.bin | Syscall smoke | pass | 2026-07-15 | `brk(0)`, valid brk update, then write/exit |
| MEMU prog-a + prog-b batch-list | OS smoke | pass | 2026-07-15 | `--batch-list` loads two raw programs sequentially |
| MEMU fs-cat via ramdisk | FS smoke | pass | 2026-07-15 | `--ramdisk tests/images/ramdisk.img --run /bin/fs-cat`; open/read/lseek/close |
| MEMU fs-missing via ramdisk | FS smoke | pass | 2026-07-15 | missing file returns `0xffffffff` and program exits cleanly |
| MEMU rv32m-mul-div.bin | CPU smoke | pass | 2026-07-15 | RV32M local coverage; does not replace real `cpu-tests` |
| MEMU rv32-system-csr.bin | CPU/CSR smoke | pass | 2026-07-15 | fence, CSR, ecall-to-mtvec, and mret local coverage; does not replace real AM artifacts |
| MEMU toolchain-basic.elf | Toolchain ELF smoke | pass | 2026-07-15 | built by `riscv64-unknown-elf-gcc` for `rv32im_zicsr_zifencei`; does not replace real `am-kernels` |
| cpu-tests/all 35 tests | CPU | pass | 2026-07-15 | `make pa-cpu-tests BUILD_DIR=/private/tmp/memu-pa-loader-build`; real `am-kernels/tests/cpu-tests` for `riscv32-nemu` |
| AM kernel hello | AM | pass | 2026-07-15 | `make pa-am-tests`; real `kernels/hello` prints `Hello, AbstractMachine!` and good-traps |
| AM hello test | AM | pass | 2026-07-15 | `am-tests mainargs=h`; ten `Hello, AM World @ riscv32` lines and good trap |
| AM timer-test | Device | pass | 2026-07-15 | `am-tests mainargs=t`; bounded run prints one-second uptime/RTC output |
| AM keyboard-test | Device | pass | 2026-07-15 | `am-tests mainargs=k`; bounded run starts keyboard polling without aborting |
| AM display-test | Device | pass | 2026-07-15 | `am-tests mainargs=v`; bounded run produces framebuffer checksums and FPS output |
| AM interrupt/yield test | CTE | pass | 2026-07-15 | `make pa-am-tests`; temporary PA checkout patch fixes riscv32-nemu Context layout and maps machine ecall/yield to `EVENT_YIELD`, then bounded run prints `y` |
| AM devscan | Device | pass | 2026-07-15 | `make pa-am-tests`; temporary PA checkout patch supplies missing riscv32-nemu GPU accel handlers and disk config stub, then devscan reaches `Test End` |
| AM audio-test | Device | pass | 2026-07-15 | `make pa-am-tests`; temporary PA checkout patch enables NEMU MMIO audio, and `am-tests mainargs=a` prints `Already play` then good-traps |
| slider | AM app | pass | 2026-07-15 | `make pa-app-tests`; bounded run renders 400x300 framebuffer and reaches instruction limit |
| typing-game | AM app | pass | 2026-07-15 | `make pa-app-tests`; bounded run prints score line and renders framebuffer |
| demo mainargs=1 | AM app | pass | 2026-07-15 | `make pa-app-tests`; bounded ant demo renders framebuffer continuously |
| bad-apple | AM app | pass | 2026-07-15 | `make pa-app-tests`; ffmpeg generates video/audio resources, app builds and sustains execution to instruction limit |
| snake | AM app | pass | 2026-07-15 | `make pa-app-tests`; bounded run renders, reaches GAME OVER, then waits for Q |
| LiteNES / Mario | AM app | pass | 2026-07-15 | `make pa-app-tests`; boots bundled Mario ROM, renders frames, and prints FPS in bounded run |
| LiteNES / Mario SDL | AM app | pass | 2026-07-15 | `make mario`; SDL framebuffer window and host keyboard mapping for local interactive play; no Mario sound is expected because this LiteNES source has no NES APU/AM_AUDIO output |
| FCEUX | AM app | pass | 2026-07-15 | `make pa-fceux-test`; public `nestest.nes` is embedded, FCEUX starts, identifies mapper 0, renders framebuffer updates, and reaches the bounded instruction limit. The historical PA Box URL currently returns a login page. |
| MEMU `/dev/events` | Navy/NDL prep | pass | 2026-07-15 | `make stage7-test`; `/dev/events` returns 0 when no SDL key is queued and SDL builds can format queued AM keys as `kd/ku KEY` lines |
| Nanos-lite + Navy hello/dummy batch (direct syscall) | OS/Navy | pass | 2026-07-15 | `make pa-nanos-tests BUILD_DIR=/private/tmp/memu-pa-nanos-batch`; cloned real `nanos-lite` and `navy-apps`, patches only temp trees, boots Nanos-lite, loads Navy `tests/hello`, exits into `/bin/dummy`, prints `Dummy from Navy-apps`, and good-traps |
| Nanos-lite batch two programs | OS | pass | 2026-07-15 | Covered by `make pa-nanos-tests` for a minimal hello-to-dummy batch path; full Nanos process model and `execve` remain separate targets |
| Navy libc/newlib hello | Navy | pass | 2026-07-15 | `make pa-nanos-libc-test`; official Navy `tests/hello` builds with downloaded compiler-rt/newlib sources, prints through libc `printf` and libos syscalls under Nanos-lite, then reaches the bounded instruction limit. The temp compatibility patch excludes riscv32-incompatible `getpass.c`, `stat64r.c`, and `wcwidth.c`. |
| NDL draw app | Navy | pass | 2026-07-17 | `make pa-ndl-test`; standalone NDL test exercises NDL_Init, NDL_OpenCanvas, NDL_DrawRect, NDL_GetTicks, NDL_PollEvent, and NDL_Quit |
| NSlider | Navy/miniSDL | pass | 2026-07-17 | `make pa-navy-ndl-test`; official NSlider builds with real libc/libndl/libminiSDL/libbmp, renders real generated slides (gen_slides.py), keyboard navigation via --key-events injection verifies slide transitions with different framebuffer checksums |
| Flappy Bird | Navy/miniSDL | pass | 2026-07-17 | `make pa-bird-test`; bird builds with libminiSDL/libSDL_image/libfixedptc, loads PNG sprites via stb_image IMG_Load, renders title screen, runs 50M instructions without crashing |
| Nanos-lite execve | OS | pass | 2026-07-17 | `make pa-execve-test`; SYS_execve handler loads new ELF and replaces current program; execve-test calls execve("/bin/hello") and hello runs successfully |
| PAL / 仙剑 | Navy/miniSDL | not-started | - | Requires full Navy/NDL/miniSDL stack and game assets |
| yield-os | PA4 | pass | 2026-07-15 | `make pa-cte-os-tests`; real `am-kernels/kernels/yield-os` alternates A/B under CTE context switching |
| thread-os / timer preemption smoke | PA4 | pass | 2026-07-15 | `make pa-cte-os-tests`; real `thread-os` prints Thread-A and Thread-B with MEMU timer interrupt injection |
| virtual memory smoke | PA4 | not-started | - | Stage 8 target |

## Run Notes

每次运行失败时，补一条记录：

```text
date:
program:
artifact:
command:
symptom:
first bad pc:
suspected layer:
next action:
```
