# MEMU Tools

This directory is reserved for local helper scripts used by later stages.

Stage 0 intentionally keeps it small. Do not add SDL, ELF, RISC-V toolchain,
or NEMU PA build assumptions here yet. When later stages need guest programs,
put generated binaries under `tools/artifacts/` and record the exact build
command, source repository, commit, target ISA, and host environment next to the
artifact.

