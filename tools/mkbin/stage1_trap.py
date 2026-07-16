#!/usr/bin/env python3
import pathlib
import struct
import sys


PROGRAM = [
    0x02A00593,  # addi a1, zero, 42
    0x00000513,  # addi a0, zero, 0
    0x00100073,  # ebreak
]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} OUTPUT", file=sys.stderr)
        return 2

    out = pathlib.Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        for inst in PROGRAM:
            f.write(struct.pack("<I", inst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
