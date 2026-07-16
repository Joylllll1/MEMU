#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
yield_max_instr="${PA_CTE_YIELD_OS_MAX_INSTR:-60000000}"
thread_max_instr="${PA_CTE_THREAD_OS_MAX_INSTR:-60000000}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make pa-cte-os-tests PA_HOME=/path/to/ICS-PA" >&2
    exit 1
  fi
fi

if [ ! -d "${pa_home}/abstract-machine" ] || [ ! -d "${pa_home}/am-kernels" ]; then
  echo "invalid PA_HOME: ${pa_home}" >&2
  exit 1
fi

if ! command -v "${cross}gcc" >/dev/null 2>&1; then
  echo "missing ${cross}gcc; set RISCV_CROSS_COMPILE=... if needed" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-pa-cte-os-tests.$$"
mkdir -p "${tmp_root}"
trap 'rm -rf "${tmp_root}"' EXIT

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/am-kernels/" "${tmp_root}/am-kernels/"

am_home="${tmp_root}/abstract-machine"
kernels="${tmp_root}/am-kernels/kernels"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"

run_and_capture() {
  name="$1"
  shift
  status=0
  output="$("$@" 2>&1)" || status=$?
  printf '%s\n' "${output}" > "${tmp_root}/run-${name}.log"
  return "${status}"
}

require_log() {
  name="$1"
  pattern="$2"
  if ! grep -q "${pattern}" "${tmp_root}/run-${name}.log"; then
    echo "FAIL ${name}: missing pattern: ${pattern}"
    sed -n '1,80p' "${tmp_root}/run-${name}.log"
    exit 1
  fi
}

build_kernel() {
  name="$1"
  make -s -C "${kernels}/${name}" ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}"
}

build_kernel yield-os
run_and_capture yield-os "${memu}" --image "${kernels}/yield-os/build/yield-os-riscv32-nemu.bin" --batch --max-instr "${yield_max_instr}" || true
require_log yield-os "A"
require_log yield-os "B"
require_log yield-os "instruction limit reached"
echo "PASS yield-os"

build_kernel thread-os
run_and_capture thread-os "${memu}" --image "${kernels}/thread-os/build/thread-os-riscv32-nemu.bin" --batch --max-instr "${thread_max_instr}" || true
require_log thread-os "Thread-A on CPU #0"
require_log thread-os "Thread-B on CPU #0"
require_log thread-os "instruction limit reached"
echo "PASS thread-os"

echo "SUMMARY pass=2 fail=0"
