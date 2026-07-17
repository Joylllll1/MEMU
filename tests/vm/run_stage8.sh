#!/bin/sh
set -eu

memu="${1:?memu binary required}"
repo_root="${2:-.}"
cc="${RISCV_CC:-riscv64-unknown-elf-gcc}"
guest_dir="${repo_root}/tests/guest/vm"
out_dir="${repo_root}/tests/images"

if ! command -v "${cc}" >/dev/null 2>&1; then
  echo "SKIP: ${cc} not found; install riscv64-unknown-elf-gcc to run Stage 8 tests"
  exit 0
fi

mkdir -p "${out_dir}"

build_kernel() {
  src="$1"
  out="$2"
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
    "${src}" \
    -o "${out}"
}

build_kernel "${guest_dir}/mp_os.c" "${out_dir}/mp-os.elf"
build_kernel "${guest_dir}/vm_fault.c" "${out_dir}/vm-fault.elf"

echo "RUN mp-os"
output="$("${memu}" --elf "${out_dir}/mp-os.elf" --batch --max-instr 10000000 2>&1)" || {
  printf '%s\n' "${output}"
  echo "FAIL mp-os: memu exited nonzero"
  exit 1
}

if ! printf '%s\n' "${output}" | grep -q "PASS: mp-os"; then
  printf '%s\n' "${output}"
  echo "FAIL mp-os: missing PASS: mp-os"
  exit 1
fi

if ! printf '%s\n' "${output}" | grep -q "MEMU: HIT GOOD TRAP"; then
  printf '%s\n' "${output}"
  echo "FAIL mp-os: missing good trap"
  exit 1
fi

seq="$(printf '%s\n' "${output}" | grep -E '^[AB]+$' | head -1 | tr -s 'AB' || true)"
if [ "${#seq}" -lt 6 ]; then
  printf '%s\n' "${output}"
  echo "FAIL mp-os: expected at least 6 alternating A/B timeslices, got '${seq}'"
  exit 1
fi
case "${seq}" in
  *ABAB*|*BABA*)
    ;;
  *)
    printf '%s\n' "${output}"
    echo "FAIL mp-os: A/B timeslices do not alternate: '${seq}'"
    exit 1
    ;;
esac
echo "mp-os timeslices: ${seq}"

echo "RUN vm-fault"
status=0
fault_output="$("${memu}" --elf "${out_dir}/vm-fault.elf" --batch --max-instr 1000000 2>&1)" || status=$?

if [ "${status}" -eq 0 ]; then
  printf '%s\n' "${fault_output}"
  echo "FAIL vm-fault: expected nonzero exit for unmapped access"
  exit 1
fi

if printf '%s\n' "${fault_output}" | grep -q "FAIL: survived unmapped access"; then
  printf '%s\n' "${fault_output}"
  echo "FAIL vm-fault: unmapped access did not fault"
  exit 1
fi

if ! printf '%s\n' "${fault_output}" | grep -q "page fault"; then
  printf '%s\n' "${fault_output}"
  echo "FAIL vm-fault: missing page fault diagnostic"
  exit 1
fi

if ! printf '%s\n' "${fault_output}" | grep -q "vaddr=0x50000000"; then
  printf '%s\n' "${fault_output}"
  echo "FAIL vm-fault: page fault diagnostic missing vaddr"
  exit 1
fi

echo "PASS stage8"
echo "SUMMARY pass=2 fail=0"
