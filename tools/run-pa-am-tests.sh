#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
timer_max_instr="${PA_AM_TIMER_MAX_INSTR:-150000000}"
intr_max_instr="${PA_AM_INTR_MAX_INSTR:-30000000}"
display_max_instr="${PA_AM_DISPLAY_MAX_INSTR:-80000000}"
devscan_max_instr="${PA_AM_DEVSCAN_MAX_INSTR:-150000000}"
audio_max_instr="${PA_AM_AUDIO_MAX_INSTR:-150000000}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make pa-am-tests PA_HOME=/path/to/ICS-PA" >&2
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

if ! command -v python3 >/dev/null 2>&1; then
  echo "missing python3; PA insert-arg requires Python" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-pa-am-tests.$$"
shim_dir="${tmp_root}/shim"
mkdir -p "${tmp_root}" "${shim_dir}"
trap 'rm -rf "${tmp_root}"' EXIT

printf '#!/bin/sh\nexec python3 "$@"\n' > "${shim_dir}/python"
chmod +x "${shim_dir}/python"

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/am-kernels/" "${tmp_root}/am-kernels/"

am_home="${tmp_root}/abstract-machine"
hello_home="${tmp_root}/am-kernels/kernels/hello"
amtest_home="${tmp_root}/am-kernels/tests/am-tests"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"

run_and_check() {
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
    sed -n '1,40p' "${tmp_root}/run-${name}.log"
    exit 1
  fi
}

make -s -C "${hello_home}" ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}"
run_and_check hello "${memu}" --elf "${hello_home}/build/hello-riscv32-nemu.elf" --batch
require_log hello "Hello, AbstractMachine"
require_log hello "MEMU: HIT GOOD TRAP"
echo "PASS am-kernel-hello"

build_amtest() {
  mainargs="$1"
  PATH="${shim_dir}:$PATH" make -s -C "${amtest_home}" insert-arg \
    ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}" mainargs="${mainargs}"
}

build_amtest h
run_and_check amtest-h "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch
require_log amtest-h "Hello, AM World @ riscv32"
require_log amtest-h "MEMU: HIT GOOD TRAP"
echo "PASS am-tests-hello"

build_amtest t
run_and_check amtest-t "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr "${timer_max_instr}" || true
require_log amtest-t "GMT (1 second)"
require_log amtest-t "instruction limit reached"
echo "PASS am-tests-timer"

build_amtest i
run_and_check amtest-i "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr "${intr_max_instr}" || true
require_log amtest-i "Hello, AM World @ riscv32"
require_log amtest-i "  t = timer, d = device, y = yield"
require_log amtest-i "y"
require_log amtest-i "instruction limit reached"
echo "PASS am-tests-interrupt-yield"

build_amtest k
run_and_check amtest-k "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr 2000000 || true
require_log amtest-k "Try to press any key"
require_log amtest-k "instruction limit reached"
echo "PASS am-tests-keyboard"

build_amtest v
run_and_check amtest-v "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr "${display_max_instr}" || true
require_log amtest-v "framebuffer checksum"
require_log amtest-v "FPS ="
require_log amtest-v "instruction limit reached"
echo "PASS am-tests-display"

build_amtest d
run_and_check amtest-d "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr "${devscan_max_instr}" || true
require_log amtest-d "Input device test skipped"
require_log amtest-d "Storage: 128 blocks of 512 size"
require_log amtest-d "Test End"
require_log amtest-d "instruction limit reached"
echo "PASS am-tests-devscan"

build_amtest a
run_and_check amtest-a "${memu}" --image "${amtest_home}/build/amtest-riscv32-nemu.bin" --batch --max-instr "${audio_max_instr}" || true
require_log amtest-a "Already play"
require_log amtest-a "MEMU: HIT GOOD TRAP"
echo "PASS am-tests-audio"

echo "SUMMARY pass=8 fail=0"
