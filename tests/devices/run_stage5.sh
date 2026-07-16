#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"
images="${repo_root}/tests/images"

"${repo_root}/tools/mkbin/device_programs.py" "${images}"

serial_output="$("${memu}" --image "${images}/hello-serial.bin" --batch)"
printf '%s\n' "${serial_output}" | grep -q "Hello, MEMU"
printf '%s\n' "${serial_output}" | grep -q "MEMU: HIT GOOD TRAP"

"${memu}" --image "${images}/timer.bin" --batch --max-instr 1000000 | \
  grep -q "MEMU: HIT GOOD TRAP"

trace_output="$("${memu}" --image "${images}/keyboard.bin" --batch --trace-device)"
printf '%s\n' "${trace_output}" | grep -q "\[device\] read  keyboard"
printf '%s\n' "${trace_output}" | grep -q "MEMU: HIT GOOD TRAP"

fb_output="$("${memu}" --image "${images}/fb-clear.bin" --batch --trace-device)"
printf '%s\n' "${fb_output}" | grep -q "\[device\] write fb"
printf '%s\n' "${fb_output}" | grep -q "MEMU: framebuffer checksum"
printf '%s\n' "${fb_output}" | grep -q "MEMU: HIT GOOD TRAP"
