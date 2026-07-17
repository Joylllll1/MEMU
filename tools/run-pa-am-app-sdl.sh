#!/bin/sh
set -eu

memu="${1:?SDL-enabled memu binary required}"
app="${2:?AM kernel name required}"
pa_home="${3:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
max_instr="${PA_AM_SDL_MAX_INSTR:-18446744073709551615}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make ${app}-sdl PA_HOME=/path/to/ICS-PA" >&2
    exit 1
  fi
fi

if [ ! -d "${pa_home}/abstract-machine" ] || [ ! -d "${pa_home}/am-kernels" ]; then
  echo "invalid PA_HOME: ${pa_home}" >&2
  exit 1
fi

if [ ! -d "${pa_home}/am-kernels/kernels/${app}" ]; then
  echo "unknown AM kernel: ${app}" >&2
  exit 1
fi

if ! command -v "${cross}gcc" >/dev/null 2>&1; then
  echo "missing ${cross}gcc; set RISCV_CROSS_COMPILE=... if needed" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-am-sdl.$$"
mkdir -p "${tmp_root}"
trap 'rm -rf "${tmp_root}"' EXIT

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/am-kernels/" "${tmp_root}/am-kernels/"

am_home="${tmp_root}/abstract-machine"
kernel_home="${tmp_root}/am-kernels/kernels/${app}"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"

make -s -C "${kernel_home}" ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}"

case "${app}" in
  snake)
    echo "Snake controls: arrow keys to steer, Q to exit after GAME OVER."
    ;;
  typing-game)
    echo "Typing game controls: type the falling letters, ESC to exit."
    ;;
esac
echo "Close the SDL window to stop MEMU."
status=0
"${memu}" --image "${kernel_home}/build/${app}-riscv32-nemu.bin" --batch --sdl --max-instr "${max_instr}" || status=$?
if [ "${status}" -ne 0 ]; then
  echo "MEMU ${app} stopped (exit ${status})."
fi
exit 0
