# Guest Artifact Staging

Use this directory for local copies of guest artifacts produced outside MEMU,
such as raw binaries or ELF files built from AM, am-kernels, Nanos-lite, or
Navy-apps.

For each artifact, keep a short note with:

- source project and commit
- build host, such as Linux, Docker, Lima, UTM, or a remote machine
- exact build command
- target ISA and ABI
- MEMU stage or compatibility target that consumes it

Binary artifacts are ignored by default and should not be committed unless a
later stage explicitly decides to track tiny fixtures.
