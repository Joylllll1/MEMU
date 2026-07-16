#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"
images="${repo_root}/tests/images"

"${repo_root}/tools/mkbin/syscall_programs.py" "${images}"

write_output="$("${memu}" --image "${images}/sys-write.bin" --batch --trace-syscall)"
printf '%s\n' "${write_output}" | grep -q "sys write"
printf '%s\n' "${write_output}" | grep -q "\[syscall\].*write"
printf '%s\n' "${write_output}" | grep -q "\[syscall\].*exit"
printf '%s\n' "${write_output}" | grep -q "MEMU: HIT GOOD TRAP"

brk_output="$("${memu}" --image "${images}/sys-brk.bin" --batch --trace-syscall)"
printf '%s\n' "${brk_output}" | grep -q "brk ok"
printf '%s\n' "${brk_output}" | grep -q "\[syscall\].*brk"
printf '%s\n' "${brk_output}" | grep -q "MEMU: HIT GOOD TRAP"

batch_output="$("${memu}" --trace-syscall --batch-list "${images}/prog-a.bin" "${images}/prog-b.bin")"
printf '%s\n' "${batch_output}" | grep -q "program A"
printf '%s\n' "${batch_output}" | grep -q "program B"
printf '%s\n' "${batch_output}" | grep -q "MEMU batch: loaded program 1/2"
printf '%s\n' "${batch_output}" | grep -q "MEMU batch: loaded program 2/2"
printf '%s\n' "${batch_output}" | grep -q "MEMU: HIT GOOD TRAP"

set +e
unknown_output="$("${memu}" --image "${images}/unknown-syscall.bin" --batch 2>&1)"
unknown_status=$?
set -e
test "${unknown_status}" -ne 0
printf '%s\n' "${unknown_output}" | grep -q "unknown syscall"
