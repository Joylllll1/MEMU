CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic -Werror -Iinclude
BUILD_DIR ?= build
CMAKE_BUILD_DIR ?= build
SDL_CFLAGS ?= $(shell sdl2-config --cflags 2>/dev/null)
SDL_LIBS ?= $(shell sdl2-config --libs 2>/dev/null)
FAST_RUN_CFLAGS ?= -O3 -DMEMU_FAST_RUN
STAGE1_IMAGE ?= tests/images/stage1-trap.bin
STAGE3_IMAGES := \
  tests/images/rv32i-add.bin \
  tests/images/rv32i-load-store.bin \
  tests/images/rv32i-branch-sum.bin \
  tests/images/rv32i-jump.bin \
  tests/images/rv32m-mul-div.bin \
  tests/images/rv32-system-csr.bin
STAGE4_IMAGES := \
  tests/images/good.bin \
  tests/images/bad.bin \
  tests/images/infinite-loop.bin \
  tests/images/invalid.bin \
  tests/images/good.elf
STAGE5_IMAGES := \
  tests/images/hello-serial.bin \
  tests/images/timer.bin \
  tests/images/keyboard.bin \
  tests/images/fb-clear.bin
STAGE6_IMAGES := \
  tests/images/sys-write.bin \
  tests/images/sys-brk.bin \
  tests/images/prog-a.bin \
  tests/images/prog-b.bin \
  tests/images/unknown-syscall.bin
STAGE7_IMAGES := \
  tests/images/ramdisk.img
TOOLCHAIN_IMAGES := \
  tests/images/toolchain-basic.elf
IMAGE ?= $(STAGE1_IMAGE)
RUN_ARGS ?=
PA_HOME ?=
PAL_NANOS_DATA ?= .local/pal-data
MEMU := $(BUILD_DIR)/memu
MEMU_SDL := $(BUILD_DIR)/memu-sdl

SRCS := \
  src/main.c \
  src/common/log.c \
  src/device/device.c \
  src/loader/image.c \
  src/os/batch.c \
  src/os/fs.c \
  src/os/ramdisk.c \
  src/os/syscall.c \
  src/monitor/expr.c \
  src/monitor/monitor.c \
  src/monitor/watchpoint.c \
  src/memory/memory.c \
  src/memory/mmu.c \
  src/cpu/cpu.c \
  src/isa/rv32i.c

.PHONY: all help clean distclean test smoke stage1-test monitor-test expr-test rv32i-test \
  stage4-test stage5-test stage6-test stage7-test stage8-test toolchain-test runner-test run monitor batch self-test dump-regs \
  mario bad-apple-sdl memu-sdl snake-sdl typing-sdl nslider-sdl bird-sdl pal-sdl nwm-sdl pa-cpu-tests pa-am-tests pa-app-tests pa-fceux-test pa-cte-os-tests pa-nanos-tests pa-nanos-libc-test pa-navy-ndl-test pa-ndl-test pa-bird-test pa-pal-probe pa-pal-test pa-execve-test pa-execve-args-test pa-vfork-test pa-fd-test pa-fork-test pa-memfd-test pa-nwm-test pa-vme-test \
  gen-stage1-image gen-rv32i-images gen-runtime-images gen-device-images gen-syscall-images gen-fs-images \
  gen-toolchain-images \
  cmake-configure cmake-build cmake-test

all: $(BUILD_DIR)/memu

help:
	@printf '%s\n' 'MEMU Make targets:'
	@printf '%s\n' '  make                 Build memu with cc'
	@printf '%s\n' '  make run             Run IMAGE in monitor mode'
	@printf '%s\n' '  make monitor         Alias for make run'
	@printf '%s\n' '  make batch           Run IMAGE to completion with --batch'
	@printf '%s\n' '  make dump-regs       Run IMAGE with --batch --dump-regs'
	@printf '%s\n' '  make self-test       Run built-in smoke program'
	@printf '%s\n' '  make mario           Build and run LiteNES/Mario in an SDL window'
	@printf '%s\n' '  make bad-apple-sdl   Play Bad Apple video and audio in an SDL window'
	@printf '%s\n' '  make snake-sdl       Play AM snake in an SDL window'
	@printf '%s\n' '  make typing-sdl      Play AM typing-game in an SDL window'
	@printf '%s\n' '  make nslider-sdl     Browse NSlider slides in an SDL window'
	@printf '%s\n' '                       (NSLIDER_SLIDES=/path/to/images uses your own slides)'
	@printf '%s\n' '  make bird-sdl        Play Flappy Bird in an SDL window'
	@printf '%s\n' '  make pal-sdl         Play PAL with PAL_NANOS_DATA in an SDL window'
	@printf '%s\n' '  make test            Run all Makefile tests'
	@printf '%s\n' '  make expr-test       Run generated expression tests'
	@printf '%s\n' '  make gen-stage1-image Regenerate tests/images/stage1-trap.bin'
	@printf '%s\n' '  make gen-rv32i-images Regenerate Stage 3 RV32I images'
	@printf '%s\n' '  make gen-runtime-images Regenerate Stage 4 runtime images'
	@printf '%s\n' '  make gen-device-images Regenerate Stage 5 device images'
	@printf '%s\n' '  make gen-syscall-images Regenerate Stage 6 syscall images'
	@printf '%s\n' '  make gen-fs-images Regenerate Stage 7 ramdisk image'
	@printf '%s\n' '  make gen-toolchain-images Build RV32 toolchain ELF tests'
	@printf '%s\n' '  make stage5-test     Run MMIO serial/timer/kbd/fb tests'
	@printf '%s\n' '  make stage6-test     Run syscall and batch-list tests'
	@printf '%s\n' '  make stage7-test     Run ramdisk/fs loader tests'
	@printf '%s\n' '  make stage8-test     Run Sv32 mp-os and page-fault tests'
	@printf '%s\n' '  make toolchain-test  Build and run RV32 toolchain ELF tests'
	@printf '%s\n' '  make pa-cpu-tests    Build and run real PA cpu-tests with PA_HOME=/path/to/ICS-PA'
	@printf '%s\n' '  make pa-am-tests     Build and run real PA AM hello/timer/intr/kbd/display tests'
	@printf '%s\n' '  make pa-app-tests    Build and run real PA slider/typing/demo/snake/LiteNES tests'
	@printf '%s\n' '  make pa-fceux-test   Build and run real PA FCEUX with a NES test ROM'
	@printf '%s\n' '  make pa-cte-os-tests Build and run real PA yield-os/thread-os CTE tests'
	@printf '%s\n' '  make pa-nanos-tests  Build and run real Nanos-lite with Navy hello+dummy'
	@printf '%s\n' '  make pa-nanos-libc-test Build and run real Navy libc printf through Nanos-lite'
	@printf '%s\n' '  make pa-navy-ndl-test Build and run real Navy NSlider through NDL/miniSDL'
	@printf '%s\n' '  make pa-ndl-test     Build and run standalone NDL draw/event/timer test'
	@printf '%s\n' '  make pa-bird-test    Build and run Flappy Bird miniSDL game'
	@printf '%s\n' '  make pa-pal-probe    Build PAL and classify the missing-resource path'
	@printf '%s\n' '  make pa-pal-test     Run PAL with the local game data directory'
	@printf '%s\n' '  make pa-execve-test  Build and run execve program replacement test'
	@printf '%s\n' '  make pa-execve-args-test  Verify execve preserves argv across replacement'
	@printf '%s\n' '  make pa-vfork-test    Verify child execve returns control to the parent'
	@printf '%s\n' '  make pa-fd-test       Verify pipe, dup, and dup2 with per-process fd tables'
	@printf '%s\n' '  make pa-fork-test     Verify concurrent fork/exec/exit/wait with two children'
	@printf '%s\n' '  make pa-memfd-test    Verify memfd_create, ftruncate, mmap, and munmap'
	@printf '%s\n' '  make pa-nwm-test      Build and run official NWM event loop under Sv32'
	@printf '%s\n' '  make pa-vme-test     Build and run Navy hello under Nanos-lite Sv32 paging'
	@printf '%s\n' '  make runner-test     Run tools/run-tests.sh'
	@printf '%s\n' '  make cmake-build     Configure and build with CMake'
	@printf '%s\n' '  make cmake-test      Run CTest'
	@printf '%s\n' ''
	@printf '%s\n' 'Variables:'
	@printf '%s\n' '  IMAGE=path/to.bin    Guest raw image, default tests/images/stage1-trap.bin'
	@printf '%s\n' '  RUN_ARGS="..."       Extra memu arguments'
	@printf '%s\n' '  BUILD_DIR=dir        Make build directory'
	@printf '%s\n' '  NSLIDER_SLIDES=dir   Images to convert into NSlider slides (nslider-sdl)'
	@printf '%s\n' '  PAL_NANOS_DATA=dir    Licensed PAL game data directory (default .local/pal-data)'
	@printf '%s\n' '  MEMU_PA_FRESH=1      Force a clean rebuild of the cached PA trees'
	@printf '%s\n' '  MEMU_PA_CACHE_DIR=dir PA build cache location, default ~/.cache/memu-pa'

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(MEMU): $(SRCS) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SRCS) -o $@

$(MEMU_SDL): $(SRCS) | $(BUILD_DIR)
	@command -v sdl2-config >/dev/null 2>&1 || { echo 'sdl2-config not found; install SDL2 first'; exit 1; }
	$(CC) $(CFLAGS) $(FAST_RUN_CFLAGS) -DMEMU_ENABLE_SDL $(SDL_CFLAGS) $(SRCS) -o $@ $(SDL_LIBS)

memu-sdl: $(MEMU_SDL)

$(STAGE1_IMAGE): tools/mkbin/stage1_trap.py
	tools/mkbin/stage1_trap.py $@

gen-stage1-image:
	tools/mkbin/stage1_trap.py $(STAGE1_IMAGE)

$(STAGE3_IMAGES): tools/mkbin/rv32i_programs.py
	tools/mkbin/rv32i_programs.py tests/images

gen-rv32i-images:
	tools/mkbin/rv32i_programs.py tests/images

$(STAGE4_IMAGES): tools/mkbin/runtime_programs.py
	tools/mkbin/runtime_programs.py tests/images

gen-runtime-images:
	tools/mkbin/runtime_programs.py tests/images

$(STAGE5_IMAGES): tools/mkbin/device_programs.py
	tools/mkbin/device_programs.py tests/images

gen-device-images:
	tools/mkbin/device_programs.py tests/images

$(STAGE6_IMAGES): tools/mkbin/syscall_programs.py
	tools/mkbin/syscall_programs.py tests/images

gen-syscall-images:
	tools/mkbin/syscall_programs.py tests/images

$(STAGE7_IMAGES): tools/mkbin/fs_programs.py tools/mkfs/mkfs.py
	tools/mkbin/fs_programs.py tests/fsimg
	tools/mkfs/mkfs.py tests/fsimg/MANIFEST $@

gen-fs-images:
	tools/mkbin/fs_programs.py tests/fsimg
	tools/mkfs/mkfs.py tests/fsimg/MANIFEST tests/images/ramdisk.img

$(TOOLCHAIN_IMAGES): tools/build-guest-tests.sh tests/guest/toolchain/start.S tests/guest/toolchain/toolchain_basic.c tests/guest/toolchain/linker.ld
	/bin/sh tools/build-guest-tests.sh .

gen-toolchain-images:
	/bin/sh tools/build-guest-tests.sh .

run monitor: $(MEMU) $(IMAGE)
	$(MEMU) --image $(IMAGE) $(RUN_ARGS)

batch: $(MEMU) $(IMAGE)
	$(MEMU) --image $(IMAGE) --batch $(RUN_ARGS)

dump-regs: $(MEMU) $(IMAGE)
	$(MEMU) --image $(IMAGE) --batch --dump-regs $(RUN_ARGS)

self-test: $(MEMU)
	$(MEMU) --self-test --batch $(RUN_ARGS)

mario: $(MEMU_SDL)
	/bin/sh tools/run-pa-mario.sh $(MEMU_SDL) $(PA_HOME)

bad-apple-sdl: $(MEMU_SDL)
	/bin/sh tools/run-pa-am-app-sdl.sh $(MEMU_SDL) bad-apple $(PA_HOME)

snake-sdl: $(MEMU_SDL)
	/bin/sh tools/run-pa-am-app-sdl.sh $(MEMU_SDL) snake $(PA_HOME)

typing-sdl: $(MEMU_SDL)
	/bin/sh tools/run-pa-am-app-sdl.sh $(MEMU_SDL) typing-game $(PA_HOME)

nslider-sdl: $(MEMU_SDL)
	PA_NANOS_INTERACTIVE=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=nslider PA_NANOS_APP_DIR=apps/nslider PA_NANOS_APP_PATH=/bin/nslider \
	NSLIDER_SLIDES="$(NSLIDER_SLIDES)" \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU_SDL) $(PA_HOME)

bird-sdl: $(MEMU_SDL)
	PA_NANOS_INTERACTIVE=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=bird PA_NANOS_APP_DIR=apps/bird PA_NANOS_APP_PATH=/bin/bird \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU_SDL) $(PA_HOME)

pal-sdl: $(MEMU_SDL)
	@test -d "$(PAL_NANOS_DATA)" || { echo 'PAL_NANOS_DATA directory not found: $(PAL_NANOS_DATA)'; echo 'Put the PAL data under .local/pal-data or pass PAL_NANOS_DATA=/path/to/data'; exit 2; }
	PA_NANOS_INTERACTIVE=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=pal PA_NANOS_APP_DIR=apps/pal PA_NANOS_APP_PATH=/bin/pal \
	PAL_NANOS_DATA="$(PAL_NANOS_DATA)" \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU_SDL) $(PA_HOME)

nwm-sdl: $(MEMU_SDL)
	PA_NANOS_INTERACTIVE=1 PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=nwm PA_NANOS_APP_DIR=apps/nwm PA_NANOS_APP_PATH=/bin/nwm \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU_SDL) $(PA_HOME)

smoke: $(MEMU)
	/bin/sh tests/smoke.sh $(MEMU)

stage1-test: $(MEMU) $(STAGE1_IMAGE)
	/bin/sh tests/stage1/run_stage1.sh $(MEMU) .

monitor-test: $(MEMU) $(STAGE1_IMAGE)
	/bin/sh tests/smoke/run_monitor_commands.sh $(MEMU) $(STAGE1_IMAGE)

expr-test: $(MEMU) $(STAGE1_IMAGE)
	tests/smoke/run_expr_generated.py $(MEMU) $(STAGE1_IMAGE)

rv32i-test: $(MEMU) $(STAGE3_IMAGES)
	/bin/sh tests/isa/run_rv32i.sh $(MEMU) .

stage4-test: $(MEMU) $(STAGE4_IMAGES)
	/bin/sh tests/runtime/run_stage4.sh $(MEMU) .

stage5-test: $(MEMU) $(STAGE5_IMAGES)
	/bin/sh tests/devices/run_stage5.sh $(MEMU) .

stage6-test: $(MEMU) $(STAGE6_IMAGES)
	/bin/sh tests/syscall/run_stage6.sh $(MEMU) .

stage7-test: $(MEMU) $(STAGE7_IMAGES)
	/bin/sh tests/fs/run_stage7.sh $(MEMU) .

stage8-test: $(MEMU)
	/bin/sh tests/vm/run_stage8.sh $(MEMU) .

toolchain-test: $(MEMU) $(TOOLCHAIN_IMAGES)
	/bin/sh tests/toolchain/run_toolchain.sh $(MEMU) .

pa-cpu-tests: $(MEMU)
	/bin/sh tools/run-pa-cpu-tests.sh $(MEMU) $(PA_HOME)

pa-am-tests: $(MEMU)
	/bin/sh tools/run-pa-am-tests.sh $(MEMU) $(PA_HOME)

pa-app-tests: $(MEMU)
	/bin/sh tools/run-pa-app-tests.sh $(MEMU) $(PA_HOME)

pa-fceux-test: $(MEMU)
	/bin/sh tools/run-pa-fceux-test.sh $(MEMU) $(PA_HOME)

pa-cte-os-tests: $(MEMU)
	/bin/sh tools/run-pa-cte-os-tests.sh $(MEMU) $(PA_HOME)

pa-nanos-tests: $(MEMU)
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-nanos-libc-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 /bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-navy-ndl-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=nslider PA_NANOS_APP_DIR=apps/nslider PA_NANOS_APP_PATH=/bin/nslider \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-ndl-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 \
	PA_NANOS_APP_NAME=ndl-test PA_NANOS_APP_DIR=tests/ndl-test PA_NANOS_APP_PATH=/bin/ndl-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-bird-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 PA_NANOS_MAX_INSTR=50000000 \
	PA_NANOS_APP_NAME=bird PA_NANOS_APP_DIR=apps/bird PA_NANOS_APP_PATH=/bin/bird \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-pal-probe: $(MEMU)
	PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 PA_NANOS_MAX_INSTR=5000000 \
	PA_NANOS_APP_NAME=pal PA_NANOS_APP_DIR=apps/pal PA_NANOS_APP_PATH=/bin/pal \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-pal-test: $(MEMU)
	@test -d "$(PAL_NANOS_DATA)" || { echo 'PAL_NANOS_DATA directory not found: $(PAL_NANOS_DATA)'; echo 'Put the PAL data under .local/pal-data or pass PAL_NANOS_DATA=/path/to/data'; exit 2; }
	PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 PA_NANOS_MAX_INSTR=50000000 \
	PA_NANOS_APP_NAME=pal PA_NANOS_APP_DIR=apps/pal PA_NANOS_APP_PATH=/bin/pal \
	PAL_NANOS_DATA="$(PAL_NANOS_DATA)" \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-execve-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 \
	PA_NANOS_APP_NAME=execve-test PA_NANOS_APP_DIR=tests/execve-test PA_NANOS_APP_PATH=/bin/execve-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-execve-args-test: $(MEMU)
	PA_NANOS_FULL_LIBC=1 PA_NANOS_MAX_INSTR=5000000 \
	PA_NANOS_APP_NAME=execve-args-test PA_NANOS_APP_DIR=tests/exec-test PA_NANOS_APP_PATH=/bin/exec-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-vfork-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_MAX_INSTR=10000000 \
	PA_NANOS_APP_NAME=vfork-test PA_NANOS_APP_DIR=tests/vfork-test PA_NANOS_APP_PATH=/bin/vfork-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-fd-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_MAX_INSTR=10000000 \
	PA_NANOS_APP_NAME=fd-test PA_NANOS_APP_DIR=tests/fd-test PA_NANOS_APP_PATH=/bin/fd-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-fork-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_MAX_INSTR=10000000 \
	PA_NANOS_APP_NAME=fork-test PA_NANOS_APP_DIR=tests/fork-test PA_NANOS_APP_PATH=/bin/fork-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-memfd-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_MAX_INSTR=10000000 \
	PA_NANOS_APP_NAME=memfd-test PA_NANOS_APP_DIR=tests/memfd-test PA_NANOS_APP_PATH=/bin/memfd-test \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-nwm-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 PA_NANOS_NDL=1 PA_NANOS_MAX_INSTR=5000000 \
	PA_NANOS_APP_NAME=nwm PA_NANOS_APP_DIR=apps/nwm PA_NANOS_APP_PATH=/bin/nwm \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

pa-vme-test: $(MEMU)
	PA_NANOS_VME=1 PA_NANOS_FULL_LIBC=1 \
	/bin/sh tools/run-pa-nanos-tests.sh $(MEMU) $(PA_HOME)

runner-test: $(MEMU) $(STAGE1_IMAGE) $(STAGE3_IMAGES) $(STAGE4_IMAGES) $(STAGE5_IMAGES) $(STAGE6_IMAGES) $(STAGE7_IMAGES) $(TOOLCHAIN_IMAGES)
	/bin/sh tools/run-tests.sh $(MEMU)

test: smoke stage1-test monitor-test expr-test rv32i-test stage4-test stage5-test stage6-test stage7-test stage8-test toolchain-test runner-test

cmake-configure:
	cmake -S . -B $(CMAKE_BUILD_DIR)

cmake-build: cmake-configure
	cmake --build $(CMAKE_BUILD_DIR)

cmake-test: cmake-build
	ctest --test-dir $(CMAKE_BUILD_DIR) --output-on-failure

clean:
	rm -rf $(BUILD_DIR)

distclean: clean
	rm -rf $(CMAKE_BUILD_DIR)
