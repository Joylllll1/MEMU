cmake_minimum_required(VERSION 3.20)

project(MEMU C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(memu
  src/main.c
  src/common/log.c
  src/device/device.c
  src/loader/image.c
  src/os/batch.c
  src/os/fs.c
  src/os/ramdisk.c
  src/os/syscall.c
  src/monitor/expr.c
  src/monitor/monitor.c
  src/monitor/watchpoint.c
  src/memory/memory.c
  src/memory/mmu.c
  src/cpu/cpu.c
  src/isa/rv32i.c
)

target_include_directories(memu PRIVATE include)

target_compile_options(memu PRIVATE
  -Wall
  -Wextra
  -Wpedantic
  -Werror
)

enable_testing()

add_test(
  NAME smoke
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke.sh $<TARGET_FILE:memu>
)

add_test(
  NAME stage1-trm
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/stage1/run_stage1.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME stage2-monitor
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke/run_monitor_commands.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}/tests/images/stage1-trap.bin
)

add_test(
  NAME stage2-expr-generated
  COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tests/smoke/run_expr_generated.py
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}/tests/images/stage1-trap.bin
)

add_test(
  NAME stage3-rv32i
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/isa/run_rv32i.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME stage4-runtime-loader
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/runtime/run_stage4.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME stage5-devices
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/devices/run_stage5.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME stage6-syscall-batch
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/syscall/run_stage6.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME stage7-filesystem
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/fs/run_stage7.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME toolchain-elf
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tests/toolchain/run_toolchain.sh
          $<TARGET_FILE:memu> ${CMAKE_CURRENT_SOURCE_DIR}
)

add_test(
  NAME memu-runner
  COMMAND /bin/sh ${CMAKE_CURRENT_SOURCE_DIR}/tools/run-tests.sh
          $<TARGET_FILE:memu>
)

set_tests_properties(
  smoke
  stage1-trm
  stage2-monitor
  stage2-expr-generated
  stage3-rv32i
  stage4-runtime-loader
  stage5-devices
  stage6-syscall-batch
  stage7-filesystem
  toolchain-elf
  memu-runner
  PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
