#!/usr/bin/env python3
"""Convert user images into NSlider-compatible slides.

Takes a directory of images (png/jpg/bmp/gif/tiff/heic), resizes each to
400x300 with macOS sips, and re-packs them as plain uncompressed 32-bit BGRA
BMPs named slides-0.bmp, slides-1.bmp, ... that Navy's libbmp can load
(libbmp requires the classic 54-byte header with compression=0).

Prints the number of slides written to stdout.

Usage:
  tools/mkbin/convert_slides.py /path/to/images/ /path/to/fsimg/share/slides/
"""

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

W = 400
H = 300

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".heic"}


def repack_bmp(src: Path, dst: Path) -> None:
    """Re-encode any uncompressed 24/32-bit BMP as plain 32-bit BGRA."""
    data = src.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{src}: not a BMP file")
    offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if bpp not in (24, 32):
        raise ValueError(f"{src}: unsupported bit depth {bpp}")
    # BI_RGB or BI_BITFIELDS with the standard BGRA layout
    if compression not in (0, 3):
        raise ValueError(f"{src}: unsupported BMP compression {compression}")
    if (width, abs(height)) != (W, H):
        raise ValueError(f"{src}: expected {W}x{H}, got {width}x{abs(height)}")

    depth = bpp // 8
    stride = (width * depth + 3) & ~3
    top_down = height < 0
    rows = []
    for i in range(H):
        src_row = i if top_down else H - 1 - i
        row = bytearray()
        base = offset + src_row * stride
        for x in range(W):
            b, g, r = data[base + x * depth : base + x * depth + 3]
            row.extend((b, g, r, 0xFF))
        rows.append(bytes(row))

    pixel_data = b"".join(reversed(rows))  # BMP rows are stored bottom-up
    header = struct.pack(
        "<2sIHHIIiiHHIIiiII",
        b"BM",
        14 + 40 + len(pixel_data),
        0, 0,
        54,
        40,
        W, H,
        1,
        32,
        0,
        len(pixel_data),
        2835, 2835,
        0, 0,
    )
    dst.write_bytes(header + pixel_data)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: convert_slides.py /path/to/images/ /path/to/slides/", file=sys.stderr)
        return 2

    src_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not src_dir.is_dir():
        print(f"not a directory: {src_dir}", file=sys.stderr)
        return 2

    images = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        print(f"no images found in {src_dir} (looked for {sorted(IMAGE_SUFFIXES)})",
              file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("slides-*.bmp"):
        stale.unlink()

    with tempfile.TemporaryDirectory() as tmp:
        for i, image in enumerate(images):
            resized = Path(tmp) / f"slide-{i}.bmp"
            result = subprocess.run(
                ["sips", "-z", str(H), str(W), "-s", "format", "bmp",
                 str(image), "--out", str(resized)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                print(f"sips failed on {image}: {result.stderr.decode().strip()}",
                      file=sys.stderr)
                return 1
            repack_bmp(resized, out_dir / f"slides-{i}.bmp")
            print(f"slide {i}: {image.name}", file=sys.stderr)

    print(len(images))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
