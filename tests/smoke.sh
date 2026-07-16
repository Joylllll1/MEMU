#!/bin/sh
set -eu

memu_bin="${1:-./build/memu}"

"${memu_bin}" --help | grep -q "Usage:"
"${memu_bin}" --version | grep -q "0.1.0"
"${memu_bin}" --self-test --batch | grep -q "HIT GOOD TRAP"

