#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"

for image in \
  rv32i-add.bin \
  rv32i-load-store.bin \
  rv32i-branch-sum.bin \
  rv32i-jump.bin \
  rv32m-mul-div.bin \
  rv32-system-csr.bin
do
  path="${repo_root}/tests/images/${image}"
  echo "RUN ${path}"
  output="$("${memu}" --image "${path}" --batch)"
  printf '%s\n' "${output}" | grep -q "MEMU: HIT GOOD TRAP"
done
