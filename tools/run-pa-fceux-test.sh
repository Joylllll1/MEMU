#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"
max_instr="${PA_FCEUX_MAX_INSTR:-20000000}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
fi

if [ ! -d "${pa_home}/abstract-machine" ] ||
   [ ! -d "${pa_home}/fceux-am" ]; then
  echo "invalid PA_HOME: expected abstract-machine and fceux-am" >&2
  exit 1
fi

if ! command -v "${cross}gcc" >/dev/null 2>&1; then
  echo "missing ${cross}gcc; set RISCV_CROSS_COMPILE=... if needed" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "missing python3; FCEUX ROM generation requires Python" >&2
  exit 1
fi

if ! find "${pa_home}/fceux-am/nes/rom" -type f -name '*.nes' -print -quit |
   grep -q .; then
  echo "no .nes ROM found under ${pa_home}/fceux-am/nes/rom" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-pa-fceux.$$"
shim_dir="${tmp_root}/shim"
mkdir -p "${tmp_root}" "${shim_dir}"
trap 'rm -rf "${tmp_root}"' EXIT

printf '#!/bin/sh\nexec python3 "$@"\n' > "${shim_dir}/python"
chmod +x "${shim_dir}/python"

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/fceux-am/" "${tmp_root}/fceux-am/"

am_home="${tmp_root}/abstract-machine"
fceux_home="${tmp_root}/fceux-am"

# macOS ships GNU Make 3.81, and the current AM source needs the platform
# sources appended after the RISC-V startup sources.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi
sed -i.bak 's/^AM_SRCS := platform\/nemu/AM_SRCS += platform\/nemu/' \
  "${am_home}/scripts/platform/nemu.mk"
python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"

PATH="${shim_dir}:$PATH" make -s -C "${fceux_home}" insert-arg \
  ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}" \
  mainargs=nestest

output="$("${memu}" --image "${fceux_home}/build/fceux-riscv32-nemu.bin" \
  --batch --max-instr "${max_instr}" 2>&1)" || status=$?
: "${status:=0}"
printf '%s\n' "${output}"

printf '%s\n' "${output}" | grep -q "Starting FCEUX"
printf '%s\n' "${output}" | grep -q "Mapper #:"
printf '%s\n' "${output}" | grep -q "framebuffer checksum"
printf '%s\n' "${output}" | grep -q "instruction limit reached"

echo "PASS fceux-nestest"
echo "SUMMARY pass=1 fail=0"
