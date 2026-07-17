#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
max_instr="${PA_NANOS_MAX_INSTR:-200000000}"
full_libc="${PA_NANOS_FULL_LIBC:-0}"
app_name="${PA_NANOS_APP_NAME:-hello}"
app_dir="${PA_NANOS_APP_DIR:-tests/hello}"
app_path="${PA_NANOS_APP_PATH:-/bin/hello}"
ndl="${PA_NANOS_NDL:-0}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/nanos-lite ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/navy-apps ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make pa-nanos-tests PA_HOME=/path/to/ICS-PA" >&2
    exit 1
  fi
fi

if [ ! -d "${pa_home}/abstract-machine" ] ||
   [ ! -d "${pa_home}/nanos-lite" ] ||
   [ ! -d "${pa_home}/navy-apps" ]; then
  echo "invalid PA_HOME: ${pa_home}; need abstract-machine, nanos-lite, and navy-apps" >&2
  exit 1
fi

if [ ! -d "${pa_home}/navy-apps/libs/libc" ]; then
  echo "missing ${pa_home}/navy-apps/libs/libc; clone NJU-ProjectN/newlib-navy there first" >&2
  exit 1
fi

if ! command -v riscv64-unknown-elf-gcc >/dev/null 2>&1; then
  echo "missing riscv64-unknown-elf-gcc" >&2
  exit 1
fi

tmp_root="${TMPDIR:-/tmp}/memu-pa-nanos-tests.$$"
shim_dir="${tmp_root}/shim"
mkdir -p "${tmp_root}" "${shim_dir}"
trap 'rm -rf "${tmp_root}"' EXIT

for tool in gcc g++ ld ar as objcopy objdump ranlib strip; do
  src="$(command -v "riscv64-unknown-elf-${tool}" || true)"
  if [ -n "${src}" ]; then
    ln -s "${src}" "${shim_dir}/riscv64-linux-gnu-${tool}"
  fi
done

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/nanos-lite/" "${tmp_root}/nanos-lite/"
rsync -a --exclude .git "${pa_home}/navy-apps/" "${tmp_root}/navy-apps/"

am_home="${tmp_root}/abstract-machine"
nanos_home="${tmp_root}/nanos-lite"
navy_home="${tmp_root}/navy-apps"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi
if grep -q '^define LIB_TEMPLATE =' "${navy_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${navy_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"
if [ "${full_libc}" = 1 ]; then
  MEMU_NANOS_APP="${app_path}" python3 "${script_dir}/patch-pa-nanos-lite.py" "${nanos_home}" "${navy_home}" full-libc
else
  MEMU_NANOS_APP="${app_path}" python3 "${script_dir}/patch-pa-nanos-lite.py" "${nanos_home}" "${navy_home}"
fi
if [ "${ndl}" = 1 ]; then
  python3 "${script_dir}/patch-pa-navy-ndl.py" "${navy_home}"
fi

ramdisk_apps=""
ramdisk_tests="dummy"
key_events_file=""
case "${app_dir}" in
  apps/*)
    ramdisk_apps="${app_dir#apps/}"
    mkdir -p "${navy_home}/fsimg/share/slides"
    python3 "${script_dir}/mkbin/gen_slides.py" "${navy_home}/fsimg/share/slides" 10
    ;;
  tests/*)
    ramdisk_tests="dummy ${app_dir#tests/}"
    ;;
  *)
    echo "unsupported Navy app directory: ${app_dir}" >&2
    exit 1
    ;;
esac

PATH="${shim_dir}:$PATH" make -s -C "${navy_home}/${app_dir}" ISA=riscv32 NAVY_HOME="${navy_home}" install
PATH="${shim_dir}:$PATH" make -s -C "${navy_home}" ISA=riscv32 NAVY_HOME="${navy_home}" \
  APPS="${ramdisk_apps}" TESTS="${ramdisk_tests}" ramdisk
PATH="${shim_dir}:$PATH" make -s -C "${nanos_home}" update \
  ARCH=riscv32-nemu CROSS_COMPILE=riscv64-unknown-elf- \
  AM_HOME="${am_home}" NAVY_HOME="${navy_home}" HAS_NAVY=1
PATH="${shim_dir}:$PATH" make -s -C "${nanos_home}" \
  ARCH=riscv32-nemu CROSS_COMPILE=riscv64-unknown-elf- \
  AM_HOME="${am_home}" NAVY_HOME="${navy_home}" HAS_NAVY=1

key_args=""
case "${app_name}" in
  nslider)
    key_events_file="${tmp_root}/key-events.txt"
    printf 'kd DOWN\nku DOWN\nkd J\nku J\n' > "${key_events_file}"
    key_args="--key-events ${key_events_file}"
    ;;
esac

status=0
output="$("${memu}" --image "${nanos_home}/build/nanos-lite-riscv32-nemu.bin" --batch --max-instr "${max_instr}" ${key_args} 2>&1)" || status=$?
printf '%s\n' "${output}" > "${tmp_root}/run-nanos.log"

require_output() {
  pattern="$1"
  if ! grep -q "${pattern}" "${tmp_root}/run-nanos.log"; then
    echo "FAIL nanos-lite: missing pattern: ${pattern}"
    sed -n '1,120p' "${tmp_root}/run-nanos.log"
    exit 1
  fi
}

case "${app_name}" in
  hello)
    require_output "Hello World"
    require_output "Hello World from Navy-apps"
    if [ "${full_libc}" = 1 ]; then
      require_output "instruction limit reached"
    else
      require_output "Dummy from Navy-apps"
      require_output "HIT GOOD TRAP"
    fi
    ;;
  file-test)
    require_output "PASS!!!"
    ;;
  nslider)
    require_output "framebuffer checksum"
    require_output "instruction limit reached"
    checksum_count=$(grep -c 'framebuffer checksum' "${tmp_root}/run-nanos.log" || true)
    if [ "${checksum_count}" -lt 2 ]; then
      echo "FAIL nanos-lite-nslider: expected at least 2 framebuffer checksums (slide navigation), got ${checksum_count}"
      sed -n '1,120p' "${tmp_root}/run-nanos.log"
      exit 1
    fi
    first_cs=$(grep 'framebuffer checksum' "${tmp_root}/run-nanos.log" | head -1 | sed 's/.*checksum //')
    second_cs=$(grep 'framebuffer checksum' "${tmp_root}/run-nanos.log" | head -2 | tail -1 | sed 's/.*checksum //')
    if [ "${first_cs}" = "${second_cs}" ]; then
      echo "FAIL nanos-lite-nslider: framebuffer checksums unchanged after key injection (both ${first_cs})"
      sed -n '1,120p' "${tmp_root}/run-nanos.log"
      exit 1
    fi
    echo "NSlider navigation OK: checksums differ (${first_cs} vs ${second_cs})"
    ;;
  event-test)
    require_output "instruction limit reached"
    ;;
  *)
    echo "no output checks defined for Navy app: ${app_name}" >&2
    exit 1
    ;;
esac

if [ "${full_libc}" = 1 ] && [ "${app_name}" = hello ]; then
  echo "PASS nanos-lite-libc-hello"
elif [ "${app_name}" = hello ]; then
  echo "PASS nanos-lite-hello-batch"
else
  echo "PASS nanos-lite-${app_name}"
fi
echo "SUMMARY pass=1 fail=0"
