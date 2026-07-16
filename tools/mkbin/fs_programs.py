#!/usr/bin/env python3
import pathlib
import struct
import sys

MEM_BASE = 0x80000000
DATA_OFF = 0x180
DATA_ADDR = MEM_BASE + DATA_OFF
BUF_ADDR = MEM_BASE + 0x300

ZERO = 0
T0 = 5
A0 = 10
A1 = 11
A2 = 12
A7 = 17
S0 = 8
S1 = 9

SYS_OPEN = 1024
SYS_CLOSE = 57
SYS_LSEEK = 62
SYS_READ = 63
SYS_WRITE = 64
SYS_EXIT = 93


def inst_i(imm, rs1, funct3, rd, opcode=0x13):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def inst_b(imm, rs1, rs2, funct3):
    imm &= 0x1FFF
    return ((imm >> 12) << 31) | (((imm >> 5) & 0x3F) << 25) | \
        (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | \
        (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | 0x63


def lui(rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def addi(rd, rs1, imm):
    return inst_i(imm, rs1, 0, rd)


def bne(rs1, rs2, imm):
    return inst_b(imm, rs1, rs2, 1)


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


def mv(rd, rs):
    return addi(rd, rs, 0)


def syscall(no, a0=None, a1=None, a2=None):
    code = []
    code += li(A7, no)
    if a0 is not None:
        code += li(A0, a0)
    if a1 is not None:
        code += li(A1, a1)
    if a2 is not None:
        code += li(A2, a2)
    code.append(ecall())
    return code


def write_const(msg_addr, msg_len):
    return syscall(SYS_WRITE, 1, msg_addr, msg_len)


def exit_code(code):
    return syscall(SYS_EXIT, code)


def image_with_data(path, words, data_items):
    data = bytearray()
    addrs = {}
    for name, blob in data_items:
        addrs[name] = DATA_ADDR + len(data)
        data.extend(blob)
    blob = b"".join(struct.pack("<I", word & 0xFFFFFFFF) for word in words)
    if len(blob) > DATA_OFF:
        raise ValueError(f"{path}: code is too large")
    blob += b"\0" * (DATA_OFF - len(blob))
    blob += bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return addrs


def patch_words(words, patches):
    for idx, value in patches:
        words[idx] = value & 0xFFFFFFFF


def make_fs_cat(path):
    data_items = [
        ("msg_path", b"/share/message.txt\0"),
    ]
    msg_path = DATA_ADDR
    words = []
    words += syscall(SYS_OPEN, msg_path, 0, 0)
    words += [mv(S0, A0)]
    words += syscall(SYS_READ, None, BUF_ADDR, 64)
    words += [mv(S1, A0)]
    words += li(A7, SYS_WRITE)
    words += li(A0, 1)
    words += li(A1, BUF_ADDR)
    words += [mv(A2, S1), ecall()]
    words += li(A7, SYS_LSEEK)
    words += [mv(A0, S0)]
    words += li(A1, 0)
    words += li(A2, 0)
    words.append(ecall())
    words += li(A7, SYS_READ)
    words += [mv(A0, S0)]
    words += li(A1, BUF_ADDR)
    words += li(A2, 5)
    words.append(ecall())
    words += [mv(S1, A0)]
    words += li(A7, SYS_WRITE)
    words += li(A0, 1)
    words += li(A1, BUF_ADDR)
    words += [mv(A2, S1), ecall()]
    words += li(A7, SYS_CLOSE)
    words += [mv(A0, S0), ecall()]
    words += exit_code(0)
    image_with_data(path, words, data_items)


def make_fs_missing(path):
    data_items = [
        ("missing_path", b"/share/missing.txt\0"),
        ("ok", b"missing ok\n"),
    ]
    missing_path = DATA_ADDR
    ok_addr = DATA_ADDR + len(data_items[0][1])
    words = []
    words += syscall(SYS_OPEN, missing_path, 0, 0)
    words += li(T0, 0xFFFFFFFF)
    bne_index = len(words)
    words.append(0)
    words += write_const(ok_addr, len(data_items[1][1]))
    words += exit_code(0)
    bad_pc = len(words) * 4
    words += exit_code(1)
    bne_pc = bne_index * 4
    patch_words(words, [(bne_index, bne(A0, T0, bad_pc - bne_pc))])
    image_with_data(path, words, data_items)


def make_fs_devices(path):
    data_items = [
        ("dispinfo_path", b"/proc/dispinfo\0"),
        ("events_path", b"/dev/events\0"),
        ("events_empty", b"events empty\n"),
    ]
    dispinfo_path = DATA_ADDR
    events_path = dispinfo_path + len(data_items[0][1])
    events_empty = events_path + len(data_items[1][1])
    words = []
    words += syscall(SYS_OPEN, dispinfo_path, 0, 0)
    words += [mv(S0, A0)]
    words += syscall(SYS_READ, None, BUF_ADDR, 32)
    words += [mv(S1, A0)]
    words += li(A7, SYS_WRITE)
    words += li(A0, 1)
    words += li(A1, BUF_ADDR)
    words += [mv(A2, S1), ecall()]
    words += li(A7, SYS_CLOSE)
    words += [mv(A0, S0), ecall()]

    words += syscall(SYS_OPEN, events_path, 0, 0)
    words += [mv(S0, A0)]
    words += syscall(SYS_READ, None, BUF_ADDR, 32)
    bne_index = len(words)
    words.append(0)
    words += write_const(events_empty, len(data_items[2][1]))
    words += li(A7, SYS_CLOSE)
    words += [mv(A0, S0), ecall()]
    words += exit_code(0)
    bad_pc = len(words) * 4
    words += exit_code(1)
    bne_pc = bne_index * 4
    patch_words(words, [(bne_index, bne(A0, ZERO, bad_pc - bne_pc))])
    image_with_data(path, words, data_items)


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("tests/fsimg")
    bin_dir = out / "bin"
    share_dir = out / "share"
    bin_dir.mkdir(parents=True, exist_ok=True)
    share_dir.mkdir(parents=True, exist_ok=True)
    make_fs_cat(bin_dir / "fs-cat.bin")
    make_fs_missing(bin_dir / "fs-missing.bin")
    make_fs_devices(bin_dir / "fs-devices.bin")
    (share_dir / "message.txt").write_text("Hello from ramdisk\n", encoding="ascii")
    (out / "MANIFEST").write_text(
        "/bin/fs-cat bin/fs-cat.bin\n"
        "/bin/fs-missing bin/fs-missing.bin\n"
        "/bin/fs-devices bin/fs-devices.bin\n"
        "/share/message.txt share/message.txt\n",
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
