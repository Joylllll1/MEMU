#!/usr/bin/env python3
import pathlib
import struct
import sys

MEM_BASE = 0x80000000
DATA_OFF = 0x100
DATA_ADDR = MEM_BASE + DATA_OFF

ZERO = 0
A0 = 10
A1 = 11
A2 = 12
A7 = 17
T0 = 5

SYS_WRITE = 64
SYS_EXIT = 93
SYS_BRK = 214


def inst_i(imm, rs1, funct3, rd, opcode=0x13):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def lui(rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def addi(rd, rs1, imm):
    return inst_i(imm, rs1, 0, rd)


def ecall():
    return 0x00000073


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


def write_syscall(msg_addr, msg_len):
    code = []
    code += li(A7, SYS_WRITE)
    code += li(A0, 1)
    code += li(A1, msg_addr)
    code += li(A2, msg_len)
    code.append(ecall())
    return code


def exit_syscall(code):
    out = []
    out += li(A7, SYS_EXIT)
    out += li(A0, code)
    out.append(ecall())
    return out


def brk_syscall(value):
    code = []
    code += li(A7, SYS_BRK)
    code += li(A0, value)
    code.append(ecall())
    return code


def image_with_data(path, words, data):
    blob = b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in words)
    if len(blob) > DATA_OFF:
        raise ValueError(f"{path}: code is too large")
    blob += b"\0" * (DATA_OFF - len(blob))
    blob += data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def write_program(path, message):
    data = message.encode("ascii")
    code = write_syscall(DATA_ADDR, len(data))
    code += exit_syscall(0)
    image_with_data(path, code, data)


def write_brk(path):
    message = b"brk ok\n"
    code = brk_syscall(0)
    code = code + brk_syscall(0x82001000)
    code = code + write_syscall(DATA_ADDR, len(message))
    code = code + exit_syscall(0)
    image_with_data(path, code, message)


def write_unknown(path):
    code = []
    code += li(A7, 0x123)
    code.append(ecall())
    image_with_data(path, code, b"")


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("tests/images")
    write_program(out / "sys-write.bin", "sys write\n")
    write_brk(out / "sys-brk.bin")
    write_program(out / "prog-a.bin", "program A\n")
    write_program(out / "prog-b.bin", "program B\n")
    write_unknown(out / "unknown-syscall.bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
