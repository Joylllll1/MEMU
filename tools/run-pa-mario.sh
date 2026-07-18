#!/bin/sh
set -eu

memu="${1:?SDL-enabled memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
max_instr="${MARIO_MAX_INSTR:-18446744073709551615}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make mario PA_HOME=/path/to/ICS-PA" >&2
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
  echo "missing python3; PA audio patch requires Python" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-mario.$$"
mkdir -p "${tmp_root}"
trap 'rm -rf "${tmp_root}"' EXIT

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/am-kernels/" "${tmp_root}/am-kernels/"

am_home="${tmp_root}/abstract-machine"
litenes_home="${tmp_root}/am-kernels/kernels/litenes"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"
python3 "${script_dir}/patch-pa-litenes-audio.py" "${litenes_home}"

make -s -C "${litenes_home}" ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}"

echo "MEMU Mario controls: W/A/S/D direction, U SELECT, I START, J A, K B."
echo "MEMU Mario audio: LiteNES APU bridge enabled (pulse/triangle/noise)."
echo "Close the SDL window to stop MEMU."
status=0
if [ -n "${MARIO_KEY_EVENTS:-}" ]; then
  "${memu}" --image "${litenes_home}/build/litenes-riscv32-nemu.bin" --batch --sdl \
    --key-events "${MARIO_KEY_EVENTS}" --max-instr "${max_instr}" || status=$?
else
  "${memu}" --image "${litenes_home}/build/litenes-riscv32-nemu.bin" --batch --sdl \
    --max-instr "${max_instr}" || status=$?
fi
if [ "${status}" -ne 0 ]; then
  echo "MEMU Mario stopped (exit ${status})."
fi
if [ "${MARIO_STRICT:-0}" = 1 ]; then
  exit "${status}"
fi
exit 0
