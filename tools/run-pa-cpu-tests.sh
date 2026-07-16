#!/bin/sh
set -eu

memu="${1:?memu binary required}"
pa_home="${2:-${PA_HOME:-}}"
cross="${RISCV_CROSS_COMPILE:-riscv64-unknown-elf-}"

if [ -z "${pa_home}" ]; then
  if [ -d /Users/wjl/Projects/icspa2025/ICS-PA/abstract-machine ] &&
     [ -d /Users/wjl/Projects/icspa2025/ICS-PA/am-kernels ]; then
    pa_home=/Users/wjl/Projects/icspa2025/ICS-PA
  else
    echo "PA_HOME is required; use: make pa-cpu-tests PA_HOME=/path/to/ICS-PA" >&2
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

tmp_root="${TMPDIR:-/tmp}/memu-pa-cpu-tests.$$"
mkdir -p "${tmp_root}"
trap 'rm -rf "${tmp_root}"' EXIT

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${tmp_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/am-kernels/" "${tmp_root}/am-kernels/"

am_home="${tmp_root}/abstract-machine"
cpu_home="${tmp_root}/am-kernels/tests/cpu-tests"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi

passed=0
failed=0

for src in "${cpu_home}"/tests/*.c; do
  name="$(basename "${src}" .c)"
  mk="${cpu_home}/Makefile.memu-${name}"
  build_log="${tmp_root}/build-${name}.log"
  run_log="${tmp_root}/run-${name}.log"

  {
    printf 'NAME = %s\n' "${name}"
    printf 'SRCS = tests/%s.c\n' "${name}"
    printf 'include $(AM_HOME)/Makefile\n'
  } > "${mk}"

  if make -s -C "${cpu_home}" -f "Makefile.memu-${name}" \
      ARCH=riscv32-nemu CROSS_COMPILE="${cross}" AM_HOME="${am_home}" >"${build_log}" 2>&1; then
    image="${cpu_home}/build/${name}-riscv32-nemu.elf"
    if "${memu}" --elf "${image}" --batch >"${run_log}" 2>&1 &&
       grep -q "MEMU: HIT GOOD TRAP" "${run_log}"; then
      printf 'PASS %s\n' "${name}"
      passed=$((passed + 1))
    else
      printf 'FAIL %s run\n' "${name}"
      sed -n '1,12p' "${run_log}"
      failed=$((failed + 1))
    fi
  else
    printf 'FAIL %s build\n' "${name}"
    sed -n '1,12p' "${build_log}"
    failed=$((failed + 1))
  fi
done

printf 'SUMMARY pass=%d fail=%d\n' "${passed}" "${failed}"
test "${failed}" -eq 0
