#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
snake_max_instr="${PA_APP_SNAKE_MAX_INSTR:-200000000}"
bad_apple_max_instr="${PA_APP_BAD_APPLE_MAX_INSTR:-150000000}"
litenes_max_instr="${PA_APP_LITENES_MAX_INSTR:-300000000}"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make pa-app-tests PA_HOME=/path/to/ICS-PA" >&2
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

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "missing ffmpeg; bad-apple requires ffmpeg to generate resources" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-pa-app-tests.$$"
shim_dir="${tmp_root}/shim"
mkdir -p "${tmp_root}" "${shim_dir}"
trap 'rm -rf "${tmp_root}"' EXIT

printf '#!/bin/sh\nexec python3 "$@"\n' > "${shim_dir}/python"
chmod +x "${shim_dir}/python"

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
    sed -n '1,60p' "${tmp_root}/run-${name}.log"
    exit 1
  fi
}

build_kernel() {
  name="$1"
  make -s -C "${kernels}/${name}" ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}"
}

build_insert_arg_kernel() {
  name="$1"
  mainargs="$2"
  PATH="${shim_dir}:$PATH" make -s -C "${kernels}/${name}" insert-arg \
    ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}" mainargs="${mainargs}"
}

build_kernel slider
run_and_capture slider "${memu}" --image "${kernels}/slider/build/slider-riscv32-nemu.bin" --batch --max-instr 20000000 || true
require_log slider "framebuffer checksum"
require_log slider "instruction limit reached"
echo "PASS slider"

build_kernel typing-game
run_and_capture typing-game "${memu}" --image "${kernels}/typing-game/build/typing-game-riscv32-nemu.bin" --batch --max-instr 30000000 || true
require_log typing-game "Type 'ESC' to exit"
require_log typing-game "Hit:"
require_log typing-game "framebuffer checksum"
require_log typing-game "instruction limit reached"
echo "PASS typing-game"

build_insert_arg_kernel demo 1
run_and_capture demo "${memu}" --image "${kernels}/demo/build/demo-riscv32-nemu.bin" --batch --max-instr 40000000 || true
require_log demo "framebuffer checksum"
require_log demo "instruction limit reached"
echo "PASS demo"

build_kernel snake
run_and_capture snake "${memu}" --image "${kernels}/snake/build/snake-riscv32-nemu.bin" --batch --max-instr "${snake_max_instr}" || true
require_log snake "GAME OVER"
require_log snake "Press Q to Exit"
require_log snake "instruction limit reached"
echo "PASS snake"

build_kernel bad-apple
run_and_capture bad-apple "${memu}" --image "${kernels}/bad-apple/build/bad-apple-riscv32-nemu.bin" --batch --max-instr "${bad_apple_max_instr}" || true
require_log bad-apple "instruction limit reached"
echo "PASS bad-apple"

build_kernel litenes
run_and_capture litenes "${memu}" --image "${kernels}/litenes/build/litenes-riscv32-nemu.bin" --batch --max-instr "${litenes_max_instr}" || true
require_log litenes "LiteNES Emulator"
require_log litenes "FPS ="
require_log litenes "framebuffer checksum"
require_log litenes "instruction limit reached"
echo "PASS litenes-mario"

echo "SUMMARY pass=6 fail=0"
