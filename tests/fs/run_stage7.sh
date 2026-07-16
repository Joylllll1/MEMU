#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"
fsimg="${repo_root}/tests/fsimg"
ramdisk="${repo_root}/tests/images/ramdisk.img"

"${repo_root}/tools/mkbin/fs_programs.py" "${fsimg}"
"${repo_root}/tools/mkfs/mkfs.py" "${fsimg}/MANIFEST" "${ramdisk}"

cat_output="$("${memu}" --ramdisk "${ramdisk}" --run /bin/fs-cat --batch --trace-syscall)"
printf '%s\n' "${cat_output}" | grep -q "Hello from ramdisk"
printf '%s\n' "${cat_output}" | grep -q "Hello\\[syscall\\]"
printf '%s\n' "${cat_output}" | grep -q "\[syscall\].*open"
printf '%s\n' "${cat_output}" | grep -q "\[syscall\].*read"
printf '%s\n' "${cat_output}" | grep -q "\[syscall\].*lseek"
printf '%s\n' "${cat_output}" | grep -q "\[syscall\].*close"
printf '%s\n' "${cat_output}" | grep -q "MEMU: HIT GOOD TRAP"

missing_output="$("${memu}" --ramdisk "${ramdisk}" --run /bin/fs-missing --batch --trace-syscall)"
printf '%s\n' "${missing_output}" | grep -q "missing ok"
printf '%s\n' "${missing_output}" | grep -q "\[syscall\].*open"
printf '%s\n' "${missing_output}" | grep -q -- "-> 0xffffffff"
printf '%s\n' "${missing_output}" | grep -q "MEMU: HIT GOOD TRAP"

devices_output="$("${memu}" --ramdisk "${ramdisk}" --run /bin/fs-devices --batch --trace-syscall)"
printf '%s\n' "${devices_output}" | grep -q "WIDTH:400"
printf '%s\n' "${devices_output}" | grep -q "HEIGHT:300"
printf '%s\n' "${devices_output}" | grep -q "events empty"
printf '%s\n' "${devices_output}" | grep -q "\[syscall\].*read"
printf '%s\n' "${devices_output}" | grep -q "MEMU: HIT GOOD TRAP"
