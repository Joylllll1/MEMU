#!/bin/sh
set -eu

memu="${1:-./build/memu}"

run_raw() {
  image="$1"
  echo "RUN raw $image"
  "$memu" --image "$image" --batch --max-instr 100000
}

run_elf() {
  elf="$1"
  echo "RUN elf $elf"
  "$memu" --elf "$elf" --batch --max-instr 100000
}

run_raw tests/images/good.bin
run_raw tests/images/stage1-trap.bin

for image in tests/images/rv32i-*.bin; do
  [ -e "$image" ] || continue
  run_raw "$image"
done

for image in tests/images/rv32m-*.bin; do
  [ -e "$image" ] || continue
  run_raw "$image"
done

for image in tests/images/rv32-system-*.bin; do
  [ -e "$image" ] || continue
  run_raw "$image"
done

for image in \
  tests/images/hello-serial.bin \
  tests/images/timer.bin \
  tests/images/keyboard.bin \
  tests/images/fb-clear.bin
do
  [ -e "$image" ] || continue
  run_raw "$image"
done

for image in \
  tests/images/sys-write.bin \
  tests/images/sys-brk.bin
do
  [ -e "$image" ] || continue
  run_raw "$image"
done

if [ -e tests/images/prog-a.bin ] && [ -e tests/images/prog-b.bin ]; then
  echo "RUN batch-list tests/images/prog-a.bin tests/images/prog-b.bin"
  "$memu" --max-instr 100000 --batch-list tests/images/prog-a.bin tests/images/prog-b.bin
fi

if [ -e tests/images/ramdisk.img ]; then
  echo "RUN fs /bin/fs-cat"
  "$memu" --ramdisk tests/images/ramdisk.img --run /bin/fs-cat --batch --max-instr 100000
  echo "RUN fs /bin/fs-missing"
  "$memu" --ramdisk tests/images/ramdisk.img --run /bin/fs-missing --batch --max-instr 100000
fi

for elf in tests/images/*.elf; do
  [ -e "$elf" ] || continue
  run_elf "$elf"
done
