#!/bin/sh
set -eu

memu="${1:?memu binary required}"
image="${2:?image required}"

output="$("${memu}" --image "${image}" <<'EOF'
help
info r
si
info r
p 1 + 2 * 3
p (1 + 2) * 3
p 1 + 2 == 3
p $a1
x 3 0x80000000
p *0x80000000
q
EOF
)"

watch_output="$("${memu}" --image "${image}" <<'EOF'
w $a1
c
info w
d 1
info w
q
EOF
)"

printf '%s\n' "${output}" | grep -q "help"
printf '%s\n' "${output}" | grep -q "pc   0x80000000"
printf '%s\n' "${output}" | grep -q "a1   0x0000002a"
printf '%s\n' "${output}" | grep -q "7 (0x00000007)"
printf '%s\n' "${output}" | grep -q "9 (0x00000009)"
printf '%s\n' "${output}" | grep -q "1 (0x00000001)"
printf '%s\n' "${output}" | grep -q "42 (0x0000002a)"
printf '%s\n' "${output}" | grep -q "0x80000000: 0x02a00593"
printf '%s\n' "${output}" | grep -q "0x80000004: 0x00000513"
printf '%s\n' "${output}" | grep -q "0x80000008: 0x00100073"
printf '%s\n' "${output}" | grep -q "44041619 (0x02a00593)"
printf '%s\n' "${watch_output}" | grep -q "Watchpoint 1:"
printf '%s\n' "${watch_output}" | grep -q "Watchpoint 1 triggered"
printf '%s\n' "${watch_output}" | grep -q "old value = 0x00000000"
printf '%s\n' "${watch_output}" | grep -q "new value = 0x0000002a"
printf '%s\n' "${watch_output}" | grep -q "No watchpoints"
