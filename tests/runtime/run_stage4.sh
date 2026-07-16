#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"
images="${repo_root}/tests/images"

"${repo_root}/tools/mkbin/runtime_programs.py" "${images}"

"${memu}" --image "${images}/good.bin" --batch | grep -q "MEMU: HIT GOOD TRAP"

set +e
bad_output="$("${memu}" --image "${images}/bad.bin" --batch 2>&1)"
bad_status=$?
set -e
test "${bad_status}" -ne 0
printf '%s\n' "${bad_output}" | grep -q "MEMU: HIT BAD TRAP"

set +e
loop_output="$("${memu}" --image "${images}/infinite-loop.bin" --batch --max-instr 100 2>&1)"
loop_status=$?
set -e
test "${loop_status}" -ne 0
printf '%s\n' "${loop_output}" | grep -q "MEMU abort: instruction limit reached"
printf '%s\n' "${loop_output}" | grep -q "Recent guest instructions"

set +e
invalid_output="$("${memu}" --image "${images}/invalid.bin" --batch 2>&1)"
invalid_status=$?
set -e
test "${invalid_status}" -ne 0
printf '%s\n' "${invalid_output}" | grep -q "invalid instruction"
printf '%s\n' "${invalid_output}" | grep -q "Recent guest instructions"

"${memu}" --elf "${images}/good.elf" --batch | grep -q "MEMU: HIT GOOD TRAP"
