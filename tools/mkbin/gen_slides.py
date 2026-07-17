#!/usr/bin/env python3
"""Generate distinct BMP test slides for NSlider.

Each slide is a 400x300 32-bit BGRA BMP with a distinct color and a geometric
pattern (stripe, checker, gradient, border) so that slides are visually and
checksum-distinct. This replaces the placeholder projectn.bmp copies.

Usage:
  tools/mkbin/gen_slides.py /path/to/slides/ N
"""

import struct
import sys
from pathlib import Path

W = 400
H = 300
BPP = 4  # BGRA
ROW_SIZE = W * BPP  # already aligned to 4


def build_bmp(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Pack a 400x300 BGRA pixel array into a BMP file."""
    # BMP stores rows bottom-up
    pixel_data = bytearray()
    for row in reversed(pixels):
        for b, g, r, a in row:
            pixel_data.extend((b, g, r, a))
    pixel_data = bytes(pixel_data)

    file_size = 14 + 40 + len(pixel_data)
    header = struct.pack(
        "<2sIHHIIiiHHIIiiII",
        b"BM",  # magic
        file_size,  # file size
        0, 0,  # reserved
        54,  # data offset
        40,  # DIB header size
        W, H,  # width, height
        1,  # planes
        32,  # bpp
        0,  # BI_RGB
        len(pixel_data),  # image size
        2835, 2835,  # 72 DPI
        0, 0,  # colors
    )
    return header + pixel_data


def color_for_index(i: int, n: int) -> tuple[int, int, int, int]:
    """Pick a distinct opaque color for slide i of n."""
    hues = [
        (0xE0, 0x40, 0x40),  # red
        (0x40, 0xE0, 0x40),  # green
        (0x40, 0x40, 0xE0),  # blue
        (0xE0, 0xE0, 0x40),  # yellow
        (0xE0, 0x40, 0xE0),  # magenta
        (0x40, 0xE0, 0xE0),  # cyan
        (0xE0, 0x80, 0x40),  # orange
        (0x80, 0x40, 0xE0),  # purple
        (0x40, 0xE0, 0x80),  # mint
        (0xE0, 0xE0, 0xE0),  # light gray
    ]
    r, g, b = hues[i % len(hues)]
    return (b, g, r, 0xFF)  # BGRA


def draw_pattern(pixels: list[list[tuple[int, int, int, int]]], i: int, _n: int) -> None:
    """Overlay a simple geometric pattern so each slide is checksum-distinct."""
    bg = color_for_index(i, _n)
    for y in range(H):
        for x in range(W):
            pixels[y][x] = bg

    # Draw a darker border rectangle whose position depends on i
    bx = 40 + (i * 19) % 120
    by = 30 + (i * 23) % 80
    bw = 320 - (i * 11) % 80
    bh = 240 - (i * 13) % 60

    border = (bg[0] // 2, bg[1] // 2, bg[2] // 2, 0xFF)

    # Top and bottom borders (4px)
    for b in range(4):
        for x in range(bx, bx + bw):
            if 0 <= x < W and 0 <= by + b < H:
                pixels[by + b][x] = border
            if 0 <= x < W and 0 <= by + bh - 1 - b < H:
                pixels[by + bh - 1 - b][x] = border
    # Left and right borders (4px)
    for b in range(4):
        for y in range(by, by + bh):
            if 0 <= bx + b < W and 0 <= y < H:
                pixels[y][bx + b] = border
            if 0 <= bx + bw - 1 - b < W and 0 <= y < H:
                pixels[y][bx + bw - 1 - b] = border

    # Draw a cross in the center whose arm positions vary per slide
    cx = W // 2 + (i * 7) % 40 - 20
    cy = H // 2 + (i * 13) % 40 - 20
    cross = (0xFF, 0xFF, 0xFF, 0xFF)
    arm = 40 + (i * 5) % 30
    thick = 3

    for t in range(thick):
        for dx in range(-arm, arm + 1):
            px = cx + dx
            if 0 <= px < W and 0 <= cy + t < H:
                pixels[cy + t][px] = cross
        for dy in range(-arm, arm + 1):
            py = cy + dy
            if 0 <= cx + t < W and 0 <= py < H:
                pixels[py][cx + t] = cross

    # Draw slide number as simple block digits in the top-left corner
    _draw_big_digit(pixels, (i + 1) % 100, 20, 20, (0xFF, 0xFF, 0xFF, 0xFF))


def _draw_big_digit(
    pixels: list[list[tuple[int, int, int, int]]],
    num: int,
    ox: int,
    oy: int,
    color: tuple[int, int, int, int],
) -> None:
    """Draw a 2-digit number using blocky 11x7 segments."""
    # 5x3 font for digits 0-9
    font = {
        0: ["###", "# #", "# #", "# #", "###"],
        1: ["  #", "  #", "  #", "  #", "  #"],
        2: ["###", "  #", "###", "#  ", "###"],
        3: ["###", "  #", "###", "  #", "###"],
        4: ["# #", "# #", "###", "  #", "  #"],
        5: ["###", "#  ", "###", "  #", "###"],
        6: ["###", "#  ", "###", "# #", "###"],
        7: ["###", "  #", "  #", "  #", "  #"],
        8: ["###", "# #", "###", "# #", "###"],
        9: ["###", "# #", "###", "  #", "###"],
    }

    scale = 4
    gap = 2  # gap between digits
    digits = [(num // 10) % 10, num % 10]

    for di, d in enumerate(digits):
        dx_base = ox + di * (3 * scale + gap)
        for row in range(5):
            for col in range(3):
                if font[d][row][col] != "#":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        px = dx_base + col * scale + sx
                        py = oy + row * scale + sy
                        if 0 <= px < W and 0 <= py < H:
                            pixels[py][px] = color


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: gen_slides.py /path/to/slides/ N", file=sys.stderr)
        return 2

    out_dir = Path(sys.argv[1])
    n = int(sys.argv[2])
    if n < 1 or n > 100:
        print("N must be between 1 and 100", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(n):
        pixels: list[list[tuple[int, int, int, int]]] = [
            [(0, 0, 0, 0xFF) for _ in range(W)] for _ in range(H)
        ]
        draw_pattern(pixels, i, n)
        bmp = build_bmp(pixels)
        path = out_dir / f"slides-{i}.bmp"
        path.write_bytes(bmp)
        print(f"wrote {path} ({len(bmp)} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
