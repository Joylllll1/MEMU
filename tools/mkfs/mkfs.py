#!/usr/bin/env python3
import pathlib
import struct
import sys

MAGIC = b"MEMUFS1\0"
NAME_MAX = 64
RECORD_SIZE = NAME_MAX + 8
HEADER_SIZE = 12


def parse_manifest(path):
    entries = []
    base = path.parent
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        guest, host = line.split(None, 1)
        entries.append((guest, base / host))
    return entries


def main():
    if len(sys.argv) != 3:
        print("usage: mkfs.py MANIFEST OUT", file=sys.stderr)
        return 2

    manifest = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    entries = parse_manifest(manifest)
    table_size = HEADER_SIZE + len(entries) * RECORD_SIZE
    offset = table_size
    records = []
    payloads = []
    for guest, host in entries:
        data = host.read_bytes()
        encoded = guest.encode("utf-8")
        if len(encoded) >= NAME_MAX:
            raise ValueError(f"path too long: {guest}")
        records.append((encoded, offset, len(data)))
        payloads.append(data)
        offset += len(data)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", len(records)))
        for name, file_offset, size in records:
            f.write(name)
            f.write(b"\0" * (NAME_MAX - len(name)))
            f.write(struct.pack("<II", file_offset, size))
        for data in payloads:
            f.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
