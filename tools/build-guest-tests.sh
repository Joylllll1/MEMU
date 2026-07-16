#!/bin/sh
set -eu

repo_root="${1:-.}"
cc="${RISCV_CC:-riscv64-unknown-elf-gcc}"
out_dir="${repo_root}/tests/images"
guest_dir="${repo_root}/tests/guest/toolchain"

if ! command -v "${cc}" >/dev/null 2>&1; then
  echo "SKIP: ${cc} not found; install riscv64-unknown-elf-gcc to build toolchain ELF tests"
  exit 0
fi

mkdir -p "${out_dir}"
"${cc}" \
  -march=rv32im_zicsr_zifencei \
  -mabi=ilp32 \
  -mcmodel=medany \
  -msmall-data-limit=0 \
  -ffreestanding \
  -fno-builtin \
  -fno-pic \
  -nostdlib \
  -nostartfiles \
  -Wl,--build-id=none \
  -Wl,-T,"${guest_dir}/linker.ld" \
  "${guest_dir}/start.S" \
  "${guest_dir}/toolchain_basic.c" \
  -o "${out_dir}/toolchain-basic.elf"

echo "built ${out_dir}/toolchain-basic.elf"
