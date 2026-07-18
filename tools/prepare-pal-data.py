#!/usr/bin/env python3
"""Stage PAL resources for the case-sensitive Navy ramdisk."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REQUIRED_FILES = {
    "abc.mkf",
    "ball.mkf",
    "data.mkf",
    "f.mkf",
    "fbp.mkf",
    "fire.mkf",
    "gop.mkf",
    "map.mkf",
    "mgo.mkf",
    "m.msg",
    "mus.mkf",
    "pat.mkf",
    "rgm.mkf",
    "rng.mkf",
    "sss.mkf",
    "voc.mkf",
    "word.dat",
    "wor16.asc",
    "wor16.fon",
}

PAL_CONFIG_SIZE = 4096
PAL_SAVE_SIZE = 262144
PAL_SAVE_FILES = tuple(f"{slot}.rpg" for slot in range(1, 6))


def padded_file(source: Path, size: int, fill: bytes = b"\0") -> bytes:
    data = source.read_bytes() if source.exists() else b""
    if len(data) < size:
        data += fill * (size - len(data))
    return data


def sync_back(source: Path, destination: Path) -> None:
    source.mkdir(parents=True, exist_ok=True)
    for name in ("sdlpal.cfg", *PAL_SAVE_FILES):
        staged = destination / name
        if not staged.is_file():
            continue
        (source / name).write_bytes(staged.read_bytes())


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("usage: prepare-pal-data.py SOURCE_DIR DEST_DIR [--sync]", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).expanduser()
    destination = Path(sys.argv[2])
    if not source.is_dir():
        print(f"PAL data source is not a directory: {source}", file=sys.stderr)
        return 2

    destination.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 4:
        if sys.argv[3] != "--sync":
            print("unknown option: " + sys.argv[3], file=sys.stderr)
            return 2
        sync_back(source, destination)
        return 0

    for child in destination.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()

    names: dict[str, Path] = {}
    for child in sorted(source.iterdir()):
        if not child.is_file():
            continue
        name = child.name.lower()
        if name in names:
            print(
                f"PAL data has case-colliding files: {names[name].name} and {child.name}",
                file=sys.stderr,
            )
            return 1
        names[name] = child
        shutil.copy2(child, destination / name)

    missing = sorted(REQUIRED_FILES - names.keys())
    if missing:
        print("PAL data is incomplete; missing: " + ", ".join(missing), file=sys.stderr)
        return 1

    config = source / "sdlpal.cfg"
    if config.is_file():
        (destination / "sdlpal.cfg").write_bytes(padded_file(config, PAL_CONFIG_SIZE, b"#\n"))
    else:
        default_config = (
            "OPLSampleRate=11025\n"
            "SampleRate=11025\n"
            "WindowHeight=200\n"
            "WindowWidth=320\n"
        ).encode("ascii")
        (destination / "sdlpal.cfg").write_bytes(
            default_config + b"#\n" * ((PAL_CONFIG_SIZE - len(default_config) + 1) // 2)
        )

    for name in PAL_SAVE_FILES:
        (destination / name).write_bytes(padded_file(source / name, PAL_SAVE_SIZE))

    print(f"MEMU: staged {len(names)} PAL resource files and sdlpal.cfg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
