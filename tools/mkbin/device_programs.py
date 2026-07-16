#!/usr/bin/env python3
import pathlib
import struct
import sys

ZERO = 0
T0 = 5
T1 = 6
T2 = 7
A0 = 10

SERIAL_ADDR = 0xA00003F8
DEV_BASE = 0xA0000000
RTC_LOW_OFF = 0x48
KBD_OFF = 0x60
VGACTL_SYNC_OFF = 0x104
FB_ADDR = 0xA1000000


def inst_i(imm, rs1, funct3, rd, opcode=0x13):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def inst_s(imm, rs1, rs2, funct3):
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | \
        (funct3 << 12) | ((imm & 0x1F) << 7) | 0x23


def inst_b(imm, rs1, rs2, funct3):
    imm &= 0x1FFF
    return ((imm >> 12) << 31) | (((imm >> 5) & 0x3F) << 25) | \
        (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | \
        (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | 0x63


def lui(rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def addi(rd, rs1, imm):
    return inst_i(imm, rs1, 0, rd)


def lw(rd, rs1, imm):
    return inst_i(imm, rs1, 2, rd, opcode=0x03)


def sb(rs2, rs1, imm):
    return inst_s(imm, rs1, rs2, 0)


def sw(rs2, rs1, imm):
    return inst_s(imm, rs1, rs2, 2)


def beq(rs1, rs2, imm):
    return inst_b(imm, rs1, rs2, 0)


def li(rd, value):
    value &= 0xFFFFFFFF
    upper = (value + 0x800) >> 12
    lower = value - (upper << 12)
    code = []
    if upper != 0:
        code.append(lui(rd, upper))
        code.append(addi(rd, rd, lower))
    else:
        code.append(addi(rd, ZERO, lower))
    return code


def ebreak():
    return 0x00100073


def good_trap():
    return [addi(A0, ZERO, 0), ebreak()]


def write_words(path, words):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for word in words:
            f.write(struct.pack("<I", word & 0xFFFFFFFF))


def hello_serial():
    code = []
    code += li(T0, SERIAL_ADDR)
    for ch in b"Hello, MEMU\n":
        code += [addi(T1, ZERO, ch), sb(T1, T0, 0)]
    code += good_trap()
    return code


def timer():
    code = []
    code += li(T0, DEV_BASE)
    code += [lw(T1, T0, RTC_LOW_OFF)]
    loop_pc = len(code) * 4
    code += [lw(T2, T0, RTC_LOW_OFF)]
    this_pc = len(code) * 4
    code += [beq(T1, T2, loop_pc - this_pc)]
    code += good_trap()
    return code


def keyboard():
    code = []
    code += li(T0, DEV_BASE)
    code += [lw(T1, T0, KBD_OFF)]
    code += good_trap()
    return code


def fb_clear():
    code = []
    code += li(T0, FB_ADDR)
    code += li(T1, 0x11223344)
    code += [sw(T1, T0, 0)]
    code += li(T1, 0x55667788)
    code += [sw(T1, T0, 4)]
    code += li(T0, DEV_BASE)
    code += [addi(T1, ZERO, 1), sw(T1, T0, VGACTL_SYNC_OFF)]
    code += good_trap()
    return code


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("tests/images")
    write_words(out / "hello-serial.bin", hello_serial())
    write_words(out / "timer.bin", timer())
    write_words(out / "keyboard.bin", keyboard())
    write_words(out / "fb-clear.bin", fb_clear())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
