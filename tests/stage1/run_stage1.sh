#!/bin/sh
set -eu

memu_bin="${1:-./build/memu}"
repo_root="${2:-.}"
image="${repo_root}/tests/images/stage1-trap.bin"

if [ ! -f "${image}" ]; then
  "${repo_root}/tools/mkbin/stage1_trap.py" "${image}"
fi

output="$("${memu_bin}" --image "${image}" --batch)"

printf '%s\n' "${output}" | grep -q "MEMU: loaded"
printf '%s\n' "${output}" | grep -q "MEMU: HIT GOOD TRAP"
printf '%s\n' "${output}" | grep -q "pc  0x80000008"
printf '%s\n' "${output}" | grep -q "a0  0x00000000"
printf '%s\n' "${output}" | grep -q "a1  0x0000002a"

