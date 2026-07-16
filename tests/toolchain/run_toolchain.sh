#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"

"${repo_root}/tools/build-guest-tests.sh" "${repo_root}"

if [ ! -e "${repo_root}/tests/images/toolchain-basic.elf" ]; then
  echo "SKIP: toolchain-basic.elf was not built"
  exit 0
fi

output="$("${memu}" --elf "${repo_root}/tests/images/toolchain-basic.elf" --batch)"
printf '%s\n' "${output}" | grep -q "MEMU: HIT GOOD TRAP"
