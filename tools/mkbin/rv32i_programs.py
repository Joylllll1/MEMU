#!/usr/bin/env python3
import pathlib
import struct
import sys

ZERO = 0
RA = 1
SP = 2
T0 = 5
T1 = 6
T2 = 7
S0 = 8
A0 = 10
A1 = 11
A2 = 12
T3 = 28
T4 = 29
T5 = 30
T6 = 31

MEM_BASE = 0x80000000


def sext_range(value: int, bits: int) -> int:
    lo = -(1 << (bits - 1))
    hi = (1 << (bits - 1)) - 1
    if not lo <= value <= hi:
        raise ValueError(f"immediate {value} does not fit signed {bits}")
    return value & ((1 << bits) - 1)


def u_range(value: int, bits: int) -> int:
    if not 0 <= value < (1 << bits):
        raise ValueError(f"value {value} does not fit unsigned {bits}")
    return value


def r(f7, rs2, rs1, f3, rd, op=0x33):
    return (u_range(f7, 7) << 25) | (u_range(rs2, 5) << 20) | (u_range(rs1, 5) << 15) | \
        (u_range(f3, 3) << 12) | (u_range(rd, 5) << 7) | u_range(op, 7)


def i(imm, rs1, f3, rd, op=0x13):
    imm12 = sext_range(imm, 12)
    return (imm12 << 20) | (u_range(rs1, 5) << 15) | (u_range(f3, 3) << 12) | \
        (u_range(rd, 5) << 7) | u_range(op, 7)


def s(imm, rs2, rs1, f3, op=0x23):
    imm12 = sext_range(imm, 12)
    return ((imm12 >> 5) << 25) | (u_range(rs2, 5) << 20) | (u_range(rs1, 5) << 15) | \
        (u_range(f3, 3) << 12) | ((imm12 & 0x1f) << 7) | u_range(op, 7)


def b(offset, rs2, rs1, f3, op=0x63):
    if offset % 2 != 0:
        raise ValueError("branch offset must be 2-byte aligned")
    imm = sext_range(offset, 13)
    return ((imm >> 12) << 31) | (((imm >> 5) & 0x3f) << 25) | \
        (u_range(rs2, 5) << 20) | (u_range(rs1, 5) << 15) | (u_range(f3, 3) << 12) | \
        (((imm >> 1) & 0xf) << 8) | (((imm >> 11) & 0x1) << 7) | u_range(op, 7)


def u(imm20, rd, op):
    return (u_range(imm20, 20) << 12) | (u_range(rd, 5) << 7) | u_range(op, 7)


def j(offset, rd, op=0x6f):
    if offset % 2 != 0:
        raise ValueError("jump offset must be 2-byte aligned")
    imm = sext_range(offset, 21)
    return ((imm >> 20) << 31) | (((imm >> 1) & 0x3ff) << 21) | \
        (((imm >> 11) & 0x1) << 20) | (((imm >> 12) & 0xff) << 12) | \
        (u_range(rd, 5) << 7) | u_range(op, 7)


def addi(rd, rs1, imm): return i(imm, rs1, 0x0, rd)
def slti(rd, rs1, imm): return i(imm, rs1, 0x2, rd)
def sltiu(rd, rs1, imm): return i(imm, rs1, 0x3, rd)
def xori(rd, rs1, imm): return i(imm, rs1, 0x4, rd)
def ori(rd, rs1, imm): return i(imm, rs1, 0x6, rd)
def andi(rd, rs1, imm): return i(imm, rs1, 0x7, rd)
def slli(rd, rs1, shamt): return i(shamt, rs1, 0x1, rd)
def srli(rd, rs1, shamt): return i(shamt, rs1, 0x5, rd)
def srai(rd, rs1, shamt): return i(0x400 | shamt, rs1, 0x5, rd)
def lb(rd, rs1, imm): return i(imm, rs1, 0x0, rd, 0x03)
def lh(rd, rs1, imm): return i(imm, rs1, 0x1, rd, 0x03)
def lw(rd, rs1, imm): return i(imm, rs1, 0x2, rd, 0x03)
def lbu(rd, rs1, imm): return i(imm, rs1, 0x4, rd, 0x03)
def lhu(rd, rs1, imm): return i(imm, rs1, 0x5, rd, 0x03)
def jalr(rd, rs1, imm): return i(imm, rs1, 0x0, rd, 0x67)
def add(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x0, rd)
def sub(rd, rs1, rs2): return r(0x20, rs2, rs1, 0x0, rd)
def sll(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x1, rd)
def slt(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x2, rd)
def sltu(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x3, rd)
def xor(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x4, rd)
def srl(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x5, rd)
def sra(rd, rs1, rs2): return r(0x20, rs2, rs1, 0x5, rd)
def or_(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x6, rd)
def and_(rd, rs1, rs2): return r(0x00, rs2, rs1, 0x7, rd)
def mul(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x0, rd)
def mulh(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x1, rd)
def mulhsu(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x2, rd)
def mulhu(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x3, rd)
def div(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x4, rd)
def divu(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x5, rd)
def rem(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x6, rd)
def remu(rd, rs1, rs2): return r(0x01, rs2, rs1, 0x7, rd)
def sb(rs2, rs1, imm): return s(imm, rs2, rs1, 0x0)
def sh(rs2, rs1, imm): return s(imm, rs2, rs1, 0x1)
def sw(rs2, rs1, imm): return s(imm, rs2, rs1, 0x2)
def beq(rs1, rs2, off): return b(off, rs2, rs1, 0x0)
def bne(rs1, rs2, off): return b(off, rs2, rs1, 0x1)
def blt(rs1, rs2, off): return b(off, rs2, rs1, 0x4)
def bge(rs1, rs2, off): return b(off, rs2, rs1, 0x5)
def bltu(rs1, rs2, off): return b(off, rs2, rs1, 0x6)
def bgeu(rs1, rs2, off): return b(off, rs2, rs1, 0x7)
def lui(rd, imm20): return u(imm20, rd, 0x37)
def auipc(rd, imm20): return u(imm20, rd, 0x17)
def jal(rd, off): return j(off, rd)
def ebreak(): return 0x00100073
def ecall(): return 0x00000073
def mret(): return 0x30200073
def fence(): return 0x0000000f
def fence_i(): return 0x0000100f


def csr(f3, csr_addr, rs1, rd):
    return (u_range(csr_addr, 12) << 20) | (u_range(rs1, 5) << 15) | \
        (u_range(f3, 3) << 12) | (u_range(rd, 5) << 7) | 0x73


def csrrw(rd, csr_addr, rs1): return csr(0x1, csr_addr, rs1, rd)
def csrrs(rd, csr_addr, rs1): return csr(0x2, csr_addr, rs1, rd)
def csrrc(rd, csr_addr, rs1): return csr(0x3, csr_addr, rs1, rd)
def csrrwi(rd, csr_addr, zimm): return csr(0x5, csr_addr, zimm, rd)
def csrrsi(rd, csr_addr, zimm): return csr(0x6, csr_addr, zimm, rd)
def csrrci(rd, csr_addr, zimm): return csr(0x7, csr_addr, zimm, rd)
def csrr(rd, csr_addr): return csrrs(rd, csr_addr, ZERO)
def csrw(csr_addr, rs1): return csrrw(ZERO, csr_addr, rs1)


class Program:
    def __init__(self):
        self.items = []
        self.labels = {}

    def label(self, name):
        self.labels[name] = len(self.items) * 4

    def emit(self, inst):
        self.items.append(inst)

    def emit_branch(self, kind, rs1, rs2, label):
        self.items.append(("branch", kind, rs1, rs2, label))

    def emit_jal(self, rd, label):
        self.items.append(("jal", rd, label))

    def emit_la(self, rd, label):
        self.items.append(("auipc_label", rd, label))
        self.items.append(("addi_label", rd, label))

    def encode(self):
        out = []
        for pc, item in enumerate(self.items):
            here = pc * 4
            if isinstance(item, int):
                out.append(item)
                continue
            if item[0] == "branch":
                _, kind, rs1, rs2, label = item
                off = self.labels[label] - here
                out.append(kind(rs1, rs2, off))
            elif item[0] == "jal":
                _, rd, label = item
                out.append(jal(rd, self.labels[label] - here))
            elif item[0] == "auipc_label":
                _, rd, label = item
                offset = self.labels[label] - here
                out.append(auipc(rd, ((offset + 0x800) >> 12) & 0xfffff))
            elif item[0] == "addi_label":
                _, rd, label = item
                base = (pc - 1) * 4
                offset = self.labels[label] - base
                hi = ((offset + 0x800) >> 12) & 0xfffff
                lo = offset - (hi << 12)
                out.append(addi(rd, rd, lo))
            else:
                raise ValueError(item)
        return out


def li(p, rd, value):
    value &= 0xffffffff
    signed = value if value < 0x80000000 else value - 0x100000000
    if -2048 <= signed <= 2047:
        p.emit(addi(rd, ZERO, signed))
        return
    upper = ((value + 0x800) >> 12) & 0xfffff
    lower = value - (upper << 12)
    if lower >= 2048:
        lower -= 4096
    p.emit(lui(rd, upper))
    if lower != 0:
        p.emit(addi(rd, rd, lower))


def check_eq(p, reg, expected):
    li(p, T6, expected)
    p.emit(xor(T5, reg, T6))
    p.emit(or_(A0, A0, T5))


def arithmetic():
    p = Program()
    p.emit(addi(A0, ZERO, 0))
    p.emit(addi(T0, ZERO, 7))
    p.emit(addi(T1, ZERO, 5))
    p.emit(add(T2, T0, T1)); check_eq(p, T2, 12)
    p.emit(sub(T2, T0, T1)); check_eq(p, T2, 2)
    p.emit(and_(T2, T0, T1)); check_eq(p, T2, 5)
    p.emit(or_(T2, T0, T1)); check_eq(p, T2, 7)
    p.emit(xor(T2, T0, T1)); check_eq(p, T2, 2)
    p.emit(ori(T2, ZERO, 0x55)); check_eq(p, T2, 0x55)
    p.emit(andi(T2, T2, 0x0f)); check_eq(p, T2, 0x05)
    p.emit(xori(T2, T2, 0x0f)); check_eq(p, T2, 0x0a)
    p.emit(slti(T2, ZERO, 1)); check_eq(p, T2, 1)
    p.emit(sltiu(T2, ZERO, 1)); check_eq(p, T2, 1)
    li(p, T0, 0xffffffff)
    p.emit(addi(T1, ZERO, 0))
    p.emit(slt(T2, T0, T1)); check_eq(p, T2, 1)
    p.emit(sltu(T2, T0, T1)); check_eq(p, T2, 0)
    li(p, T0, 0x80000000)
    p.emit(srli(T2, T0, 31)); check_eq(p, T2, 1)
    p.emit(srai(T2, T0, 31)); check_eq(p, T2, 0xffffffff)
    p.emit(addi(T1, ZERO, 5))
    p.emit(addi(T0, ZERO, 1))
    p.emit(sll(T2, T0, T1)); check_eq(p, T2, 32)
    p.emit(srl(T2, T2, T1)); check_eq(p, T2, 1)
    li(p, T0, 0xfffffff0)
    p.emit(sra(T2, T0, T1)); check_eq(p, T2, 0xffffffff)
    p.emit(ebreak())
    return p.encode()


def load_store():
    p = Program()
    p.emit(addi(A0, ZERO, 0))
    p.emit(lui(T0, 0x80001))
    li(p, T1, 0x12345678)
    p.emit(sw(T1, T0, 0))
    p.emit(lw(T2, T0, 0)); check_eq(p, T2, 0x12345678)
    li(p, T1, 0x80)
    p.emit(sb(T1, T0, 4))
    p.emit(lb(T2, T0, 4)); check_eq(p, T2, 0xffffff80)
    p.emit(lbu(T2, T0, 4)); check_eq(p, T2, 0x80)
    li(p, T1, 0x8001)
    p.emit(sh(T1, T0, 8))
    p.emit(lh(T2, T0, 8)); check_eq(p, T2, 0xffff8001)
    p.emit(lhu(T2, T0, 8)); check_eq(p, T2, 0x8001)
    p.emit(ebreak())
    return p.encode()


def branch_sum():
    p = Program()
    p.emit(addi(T0, ZERO, 0))
    p.emit(addi(T1, ZERO, 0))
    p.emit(addi(T2, ZERO, 100))
    p.label("loop")
    p.emit(addi(T0, T0, 1))
    p.emit(add(T1, T1, T0))
    p.emit_branch(blt, T0, T2, "loop")
    p.emit(addi(A0, ZERO, 0))
    check_eq(p, T1, 5050)
    p.emit_branch(beq, ZERO, ZERO, "beq_ok")
    p.emit(addi(A0, ZERO, 1))
    p.label("beq_ok")
    p.emit_branch(bne, ZERO, ZERO, "bad")
    p.emit_branch(bge, T0, T2, "bge_ok")
    p.label("bad")
    p.emit(addi(A0, ZERO, 1))
    p.label("bge_ok")
    li(p, T3, 0xffffffff)
    p.emit_branch(bltu, T2, T3, "bltu_ok")
    p.emit(addi(A0, ZERO, 1))
    p.label("bltu_ok")
    p.emit_branch(bgeu, T3, T2, "done")
    p.emit(addi(A0, ZERO, 1))
    p.label("done")
    p.emit(ebreak())
    return p.encode()


def jump():
    p = Program()
    p.emit(addi(A0, ZERO, 1))
    p.emit_jal(RA, "func")
    p.emit_jal(ZERO, "done")
    p.label("func")
    p.emit(addi(A0, ZERO, 0))
    p.emit(jalr(ZERO, RA, 0))
    p.label("done")
    p.emit(ebreak())
    return p.encode()


def mul_div():
    p = Program()
    p.emit(addi(A0, ZERO, 0))

    li(p, T0, 0xfffffff9)
    p.emit(addi(T1, ZERO, 3))
    p.emit(mul(T2, T0, T1)); check_eq(p, T2, 0xffffffeb)

    li(p, T0, 0x40000000)
    p.emit(addi(T1, ZERO, 4))
    p.emit(mulh(T2, T0, T1)); check_eq(p, T2, 1)

    li(p, T0, 0x7fffffff)
    li(p, T1, 0xffffffff)
    p.emit(mulhsu(T2, T0, T1)); check_eq(p, T2, 0x7ffffffe)

    li(p, T0, 0xffffffff)
    p.emit(addi(T1, ZERO, 2))
    p.emit(mulhu(T2, T0, T1)); check_eq(p, T2, 1)

    li(p, T0, 0xffffffea)
    p.emit(addi(T1, ZERO, 5))
    p.emit(div(T2, T0, T1)); check_eq(p, T2, 0xfffffffc)
    p.emit(rem(T2, T0, T1)); check_eq(p, T2, 0xfffffffe)

    p.emit(addi(T0, ZERO, 22))
    p.emit(addi(T1, ZERO, 5))
    p.emit(divu(T2, T0, T1)); check_eq(p, T2, 4)
    p.emit(remu(T2, T0, T1)); check_eq(p, T2, 2)

    p.emit(addi(T1, ZERO, 0))
    p.emit(div(T2, T0, T1)); check_eq(p, T2, 0xffffffff)
    p.emit(divu(T2, T0, T1)); check_eq(p, T2, 0xffffffff)
    p.emit(rem(T2, T0, T1)); check_eq(p, T2, 22)
    p.emit(remu(T2, T0, T1)); check_eq(p, T2, 22)

    li(p, T0, 0x80000000)
    li(p, T1, 0xffffffff)
    p.emit(div(T2, T0, T1)); check_eq(p, T2, 0x80000000)
    p.emit(rem(T2, T0, T1)); check_eq(p, T2, 0)

    p.emit(ebreak())
    return p.encode()


def system_csr():
    p = Program()
    p.emit(addi(A0, ZERO, 0))
    p.emit(fence())
    p.emit(fence_i())

    p.emit(addi(T0, ZERO, 0x18))
    p.emit(csrrw(T1, 0x300, T0))
    p.emit(csrr(T2, 0x300)); check_eq(p, T2, 0x18)
    p.emit(csrrsi(T2, 0x300, 0x1)); check_eq(p, T2, 0x18)
    p.emit(csrr(T2, 0x300)); check_eq(p, T2, 0x19)
    p.emit(csrrci(T2, 0x300, 0x1)); check_eq(p, T2, 0x19)
    p.emit(csrr(T2, 0x300)); check_eq(p, T2, 0x18)
    p.emit(csrr(T2, 0xf14)); check_eq(p, T2, 0)

    p.emit_la(T0, "trap_handler")
    p.emit(csrw(0x305, T0))
    p.emit(ecall())
    check_eq(p, A1, 0x1357)
    p.emit_jal(ZERO, "done")

    p.label("trap_handler")
    p.emit(csrr(T1, 0x342)); check_eq(p, T1, 11)
    p.emit(csrr(T2, 0x341))
    p.emit(addi(T2, T2, 4))
    p.emit(csrw(0x341, T2))
    li(p, A1, 0x1357)
    p.emit(mret())

    p.label("done")
    p.emit(ebreak())
    return p.encode()


PROGRAMS = {
    "rv32i-add.bin": arithmetic,
    "rv32i-load-store.bin": load_store,
    "rv32i-branch-sum.bin": branch_sum,
    "rv32i-jump.bin": jump,
    "rv32m-mul-div.bin": mul_div,
    "rv32-system-csr.bin": system_csr,
}


def write_image(path, words):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for word in words:
            f.write(struct.pack("<I", word & 0xffffffff))


def main():
    out_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("tests/images")
    for name, build in PROGRAMS.items():
        write_image(out_dir / name, build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
