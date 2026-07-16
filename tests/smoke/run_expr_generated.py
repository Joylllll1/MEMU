#!/usr/bin/env python3
import random
import re
import subprocess
import sys

MASK = 0xFFFFFFFF


def u32(value):
    return value & MASK


def div_u32(lhs, rhs):
    if rhs == 0:
        rhs = 1
    return u32(lhs // rhs)


def atom(rng):
    value = rng.randrange(0, 256)
    if rng.randrange(4) == 0:
        return f"0x{value:x}", value
    return str(value), value


def generated_expr(rng, depth):
    if depth <= 0:
        return atom(rng)

    kind = rng.randrange(8)
    if kind == 0:
        expr, value = generated_expr(rng, depth - 1)
        return f"({expr})", value
    if kind == 1:
        expr, value = generated_expr(rng, depth - 1)
        return f"-({expr})", u32(-value)

    lhs_s, lhs = generated_expr(rng, depth - 1)
    rhs_s, rhs = generated_expr(rng, depth - 1)

    op = rng.choice(["+", "-", "*", "/", "==", "!=", "&&"])
    if op == "+":
        return f"({lhs_s} + {rhs_s})", u32(lhs + rhs)
    if op == "-":
        return f"({lhs_s} - {rhs_s})", u32(lhs - rhs)
    if op == "*":
        return f"({lhs_s} * {rhs_s})", u32(lhs * rhs)
    if op == "/":
        if rhs == 0:
            rhs_s, rhs = "1", 1
        return f"({lhs_s} / {rhs_s})", div_u32(lhs, rhs)
    if op == "==":
        return f"({lhs_s} == {rhs_s})", 1 if lhs == rhs else 0
    if op == "!=":
        return f"({lhs_s} != {rhs_s})", 1 if lhs != rhs else 0
    return f"({lhs_s} && {rhs_s})", 1 if lhs != 0 and rhs != 0 else 0


def build_cases(count):
    cases = [
        ("10 - 3 - 2", 5),
        ("20 / 5 / 2", 2),
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("1 + 2 == 3 && 4 != 5", 1),
        ("1 + 2 == 4 && 4 != 5", 0),
        ("0x10 + 0x20", 0x30),
        ("-1", MASK),
        ("-(1 + 2)", u32(-3)),
        ("$pc == 0x80000000", 1),
        ("$a0 == 0 && $a1 == 0", 1),
        ("*0x80000000", 0x02A00593),
    ]

    rng = random.Random(0xC0DE)
    while len(cases) < count:
        cases.append(generated_expr(rng, 3))
    return cases


def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(f"usage: {sys.argv[0]} MEMU IMAGE [COUNT]", file=sys.stderr)
        return 2

    memu = sys.argv[1]
    image = sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) == 4 else 200
    cases = build_cases(count)
    commands = "".join(f"p {expr}\n" for expr, _ in cases) + "q\n"

    proc = subprocess.run(
        [memu, "--image", image],
        input=commands,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode

    matches = re.findall(r"([0-9]+) \(0x([0-9a-fA-F]{8})\)", proc.stdout)
    if len(matches) != len(cases):
        print(proc.stdout, end="")
        print(f"expected {len(cases)} expression results, got {len(matches)}", file=sys.stderr)
        return 1

    for idx, ((expr, expected), (_, hex_value)) in enumerate(zip(cases, matches), start=1):
        actual = int(hex_value, 16)
        expected = u32(expected)
        if actual != expected:
            print(proc.stdout, end="")
            print(
                f"case {idx} failed: {expr!r}: expected 0x{expected:08x}, got 0x{actual:08x}",
                file=sys.stderr,
            )
            return 1

    print(f"generated expression test passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
