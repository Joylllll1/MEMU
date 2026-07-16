#!/usr/bin/env python3
import pathlib
import struct
import sys

MEM_BASE = 0x80000000
ZERO = 0
A0 = 10


def inst_i(imm, rs1, funct3, rd, opcode=0x13):
    imm &= 0xFFF
    return (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def inst_jal(rd, offset):
    imm = offset & 0x1FFFFF
    return ((imm >> 20) << 31) | (((imm >> 1) & 0x3FF) << 21) | \
        (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12) | \
        (rd << 7) | 0x6F


def addi(rd, rs1, imm):
    return inst_i(imm, rs1, 0, rd)


def ebreak():
    return 0x00100073


def write_words(path, words):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for word in words:
            f.write(struct.pack("<I", word & 0xFFFFFFFF))


def write_elf(path, words):
    entry = MEM_BASE
    ehsize = 52
    phentsize = 32
    phoff = ehsize
    data_offset = 0x100
    data = b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in words)

    ident = bytearray(16)
    ident[0:4] = b"\x7fELF"
    ident[4] = 1  # ELFCLASS32
    ident[5] = 1  # ELFDATA2LSB
    ident[6] = 1  # EV_CURRENT

    ehdr = struct.pack(
        "<16sHHIIIIIHHHHHH",
        bytes(ident),
        2,        # ET_EXEC
        243,      # EM_RISCV
        1,
        entry,
        phoff,
        0,
        0,
        ehsize,
        phentsize,
        1,
        0,
        0,
        0,
    )
    phdr = struct.pack(
        "<IIIIIIII",
        1,          # PT_LOAD
        data_offset,
        MEM_BASE,
        MEM_BASE,
        len(data),
        len(data) + 16,  # include tiny .bss-like zero tail
        5,          # R_X
        0x1000,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(ehdr)
        f.write(phdr)
        f.write(b"\0" * (data_offset - f.tell()))
        f.write(data)


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("tests/images")
    good = [addi(A0, ZERO, 0), ebreak()]
    bad = [addi(A0, ZERO, 1), ebreak()]
    loop = [inst_jal(ZERO, 0)]
    invalid = [0xFFFFFFFF]

    write_words(out / "good.bin", good)
    write_words(out / "bad.bin", bad)
    write_words(out / "infinite-loop.bin", loop)
    write_words(out / "invalid.bin", invalid)
    write_elf(out / "good.elf", good)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
