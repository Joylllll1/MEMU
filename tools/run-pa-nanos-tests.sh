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
vme="${PA_NANOS_VME:-0}"
interactive="${PA_NANOS_INTERACTIVE:-0}"
if [ "${interactive}" = 1 ]; then
  max_instr="${PA_NANOS_MAX_INSTR:-18446744073709551615}"
fi
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

# Persistent per-configuration build cache: newlib and other Navy libraries
# are only rebuilt from scratch when the patch tooling or PA_HOME changes.
cache_root="${MEMU_PA_CACHE_DIR:-${HOME}/.cache/memu-pa}"
work_root="${cache_root}/nanos-libc${full_libc}-ndl${ndl}-vme${vme}-${app_name}"
stamp_file="${work_root}/.memu-stamp"
fingerprint="$({ cat "$0" \
      "${script_dir}/patch-pa-nemu-ioe.py" \
      "${script_dir}/patch-pa-nanos-lite.py" \
      "${script_dir}/patch-pa-navy-ndl.py" \
      "${script_dir}/mkbin/gen_slides.py" \
      "${script_dir}/mkbin/convert_slides.py"; \
    echo "${pa_home}"; } | cksum)"
if [ "${MEMU_PA_FRESH:-0}" = 1 ] ||
   [ ! -f "${stamp_file}" ] ||
   [ "$(cat "${stamp_file}")" != "${fingerprint}" ]; then
  rm -rf "${work_root}"
  mkdir -p "${work_root}"
  printf '%s' "${fingerprint}" > "${stamp_file}"
else
  echo "MEMU: reusing cached PA build in ${work_root} (MEMU_PA_FRESH=1 forces a clean rebuild)"
fi
shim_dir="${work_root}/shim"
mkdir -p "${shim_dir}"

for tool in gcc g++ ld ar as objcopy objdump ranlib strip; do
  src="$(command -v "riscv64-unknown-elf-${tool}" || true)"
  if [ -n "${src}" ]; then
    ln -sf "${src}" "${shim_dir}/riscv64-linux-gnu-${tool}"
  fi
done

rsync -a --exclude .git "${pa_home}/abstract-machine/" "${work_root}/abstract-machine/"
rsync -a --exclude .git "${pa_home}/nanos-lite/" "${work_root}/nanos-lite/"
rsync -a --exclude .git "${pa_home}/navy-apps/" "${work_root}/navy-apps/"

am_home="${work_root}/abstract-machine"
nanos_home="${work_root}/nanos-lite"
navy_home="${work_root}/navy-apps"

# macOS ships GNU Make 3.81, which does not expand this newer define syntax.
if grep -q '^define LIB_TEMPLATE =' "${am_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${am_home}/Makefile"
fi
if grep -q '^define LIB_TEMPLATE =' "${navy_home}/Makefile"; then
  sed -i.bak 's/^define LIB_TEMPLATE =/define LIB_TEMPLATE/' "${navy_home}/Makefile"
fi

python3 "${script_dir}/patch-pa-nemu-ioe.py" "${am_home}"
if [ "${full_libc}" = 1 ]; then
  MEMU_NANOS_APP="${app_path}" MEMU_NANOS_VME="${vme}" python3 "${script_dir}/patch-pa-nanos-lite.py" "${nanos_home}" "${navy_home}" full-libc
else
  MEMU_NANOS_APP="${app_path}" MEMU_NANOS_VME="${vme}" python3 "${script_dir}/patch-pa-nanos-lite.py" "${nanos_home}" "${navy_home}"
fi
if [ "${ndl}" = 1 ]; then
  python3 "${script_dir}/patch-pa-navy-ndl.py" "${navy_home}"
fi

if [ "${app_name}" = "ndl-test" ]; then
  mkdir -p "${navy_home}/tests/ndl-test"
  cp "${script_dir}/mkbin/ndl-test.c" "${navy_home}/tests/ndl-test/"
  cat > "${navy_home}/tests/ndl-test/Makefile" << 'MAKEEOF'
NAME = ndl-test
SRCS = ndl-test.c
LIBS += libndl
include $(NAVY_HOME)/Makefile
MAKEEOF
fi

if [ "${app_name}" = "execve-test" ]; then
  mkdir -p "${navy_home}/tests/execve-test"
  cp "${script_dir}/mkbin/execve-test.c" "${navy_home}/tests/execve-test/"
  cat > "${navy_home}/tests/execve-test/Makefile" << 'MAKEEOF'
NAME = execve-test
SRCS = execve-test.c
include $(NAVY_HOME)/Makefile
MAKEEOF
fi

ramdisk_apps=""
ramdisk_tests="dummy"
key_events_file=""
case "${app_dir}" in
  apps/*)
    ramdisk_apps="${app_dir#apps/}"
    mkdir -p "${navy_home}/fsimg/share/slides"
    if [ "${app_name}" = "nslider" ] && [ -n "${NSLIDER_SLIDES:-}" ]; then
      # Expand a literal leading ~ (zsh does not expand it in make arguments).
      case "${NSLIDER_SLIDES}" in
        "~") NSLIDER_SLIDES="${HOME}" ;;
        "~/"*) NSLIDER_SLIDES="${HOME}${NSLIDER_SLIDES#\~}" ;;
      esac
      if [ ! -d "${NSLIDER_SLIDES}" ]; then
        echo "NSLIDER_SLIDES is not a directory: ${NSLIDER_SLIDES}" >&2
        exit 1
      fi
      slide_count="$(python3 "${script_dir}/mkbin/convert_slides.py" \
        "${NSLIDER_SLIDES}" "${navy_home}/fsimg/share/slides")"
      echo "MEMU: using ${slide_count} slides from ${NSLIDER_SLIDES}"
      perl -pi -e "s/^const int N = \\d+;/const int N = ${slide_count};/" \
        "${navy_home}/${app_dir}/src/main.cpp"
    else
      rm -f "${navy_home}/fsimg/share/slides/"slides-*.bmp
      python3 "${script_dir}/mkbin/gen_slides.py" "${navy_home}/fsimg/share/slides" 10
    fi
    if [ "${app_name}" = "bird" ]; then
      awk '/^include.*NAVY_HOME/{print "CFLAGS += -D_GNU_SOURCE"}1' "${navy_home}/apps/bird/Makefile" > "${navy_home}/apps/bird/Makefile.tmp" && mv "${navy_home}/apps/bird/Makefile.tmp" "${navy_home}/apps/bird/Makefile"
    fi
    ;;
  tests/*)
    ramdisk_tests="dummy ${app_dir#tests/}"
    if [ "${app_name}" = "execve-test" ]; then
      ramdisk_tests="dummy hello execve-test"
    fi
    ;;
  *)
    echo "unsupported Navy app directory: ${app_dir}" >&2
    exit 1
    ;;
esac

navy_vme_arg=""
if [ "${vme}" = 1 ]; then
  navy_vme_arg="VME=1"
fi

if [ "${app_name}" = "bird" ]; then
  PATH="${shim_dir}:$PATH" make -s -C "${navy_home}/${app_dir}" ISA=riscv32 NAVY_HOME="${navy_home}" ${navy_vme_arg} app
  mkdir -p "${navy_home}/fsimg/bin" "${navy_home}/fsimg/share/games/bird"
  cp "${navy_home}/apps/bird/build/bird-riscv32" "${navy_home}/fsimg/bin/bird"
  cp -r "${navy_home}/apps/bird/repo/res/"* "${navy_home}/fsimg/share/games/bird/"
else
  PATH="${shim_dir}:$PATH" make -s -C "${navy_home}/${app_dir}" ISA=riscv32 NAVY_HOME="${navy_home}" ${navy_vme_arg} install
fi
PATH="${shim_dir}:$PATH" make -s -C "${navy_home}" ISA=riscv32 NAVY_HOME="${navy_home}" ${navy_vme_arg} \
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
    if [ "${interactive}" != 1 ]; then
      key_events_file="${work_root}/key-events.txt"
      printf 'kd DOWN\nku DOWN\nkd J\nku J\n' > "${key_events_file}"
      key_args="--key-events ${key_events_file}"
    fi
    ;;
esac

if [ "${interactive}" = 1 ]; then
  case "${app_name}" in
    nslider)
      echo "NSlider controls: J/Down next slide, K/Up previous slide, digits+G go to slide."
      ;;
    bird)
      echo "Flappy Bird controls: press any key to flap."
      ;;
  esac
  echo "Close the SDL window to stop MEMU."
  status=0
  "${memu}" --image "${nanos_home}/build/nanos-lite-riscv32-nemu.bin" --batch --sdl --max-instr "${max_instr}" || status=$?
  if [ "${status}" -ne 0 ]; then
    echo "MEMU ${app_name} stopped (exit ${status})."
  fi
  exit 0
fi

status=0
output="$("${memu}" --image "${nanos_home}/build/nanos-lite-riscv32-nemu.bin" --batch --max-instr "${max_instr}" ${key_args} 2>&1)" || status=$?
printf '%s\n' "${output}" > "${work_root}/run-nanos.log"

require_output() {
  pattern="$1"
  if ! grep -q "${pattern}" "${work_root}/run-nanos.log"; then
    echo "FAIL nanos-lite: missing pattern: ${pattern}"
    sed -n '1,120p' "${work_root}/run-nanos.log"
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
    checksum_count=$(grep -c 'framebuffer checksum' "${work_root}/run-nanos.log" || true)
    if [ "${checksum_count}" -lt 2 ]; then
      echo "FAIL nanos-lite-nslider: expected at least 2 framebuffer checksums (slide navigation), got ${checksum_count}"
      sed -n '1,120p' "${work_root}/run-nanos.log"
      exit 1
    fi
    first_cs=$(grep 'framebuffer checksum' "${work_root}/run-nanos.log" | head -1 | sed 's/.*checksum //')
    second_cs=$(grep 'framebuffer checksum' "${work_root}/run-nanos.log" | head -2 | tail -1 | sed 's/.*checksum //')
    if [ "${first_cs}" = "${second_cs}" ]; then
      echo "FAIL nanos-lite-nslider: framebuffer checksums unchanged after key injection (both ${first_cs})"
      sed -n '1,120p' "${work_root}/run-nanos.log"
      exit 1
    fi
    echo "NSlider navigation OK: checksums differ (${first_cs} vs ${second_cs})"
    ;;
  event-test)
    require_output "instruction limit reached"
    ;;
  ndl-test)
    require_output "PASS: ndl-test"
    ;;
  execve-test)
    require_output "execve-test: before execve"
    require_output "Hello World"
    if grep -q "FAIL: execve returned" "${work_root}/run-nanos.log"; then
      echo "FAIL execve-test: execve returned instead of replacing program"
      sed -n '1,120p' "${work_root}/run-nanos.log"
      exit 1
    fi
    ;;
  bird)
    if grep -q "instruction limit reached" "${work_root}/run-nanos.log"; then
      echo "Bird ran without crashing (instruction limit reached)"
    else
      echo "FAIL bird: did not reach instruction limit (likely crashed)"
      sed -n '1,120p' "${work_root}/run-nanos.log"
      exit 1
    fi
    ;;
  *)
    echo "no output checks defined for Navy app: ${app_name}" >&2
    exit 1
    ;;
esac

if [ "${vme}" = 1 ] && [ "${app_name}" = hello ]; then
  echo "PASS nanos-lite-vme-hello"
elif [ "${full_libc}" = 1 ] && [ "${app_name}" = hello ]; then
  echo "PASS nanos-lite-libc-hello"
elif [ "${app_name}" = hello ]; then
  echo "PASS nanos-lite-hello-batch"
else
  echo "PASS nanos-lite-${app_name}"
fi
echo "SUMMARY pass=1 fail=0"
