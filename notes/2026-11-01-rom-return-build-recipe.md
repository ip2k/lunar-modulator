# Return-r01 offline build recipe preflight correction — 2026-11-01

The separately named fixed ROM-return Pico source was approved at
`9de85189049a21f88bfac958eead18ba61dfdd6a` and integrated before this
recipe correction. This change touches only the offline build wrapper and its
fake-Docker test. It does not change the ROM wire protocol, default transporter,
host driver, recovery shim, or firmware source.

The SDK 2.2.0 preflight found two recipe blockers. Aeon's offline builder is a
local, immutable Docker image identified by its full `sha256:` config ID; the
old wrapper accepted only a registry-style `name@sha256:` reference. It also
set a global linker map flag, although `pico_add_extra_outputs` produces the
target-specific `fm1_transporter_return_r01.elf.map`. The wrapper now accepts
either pinned input form, inspects and validates the full resolved local image
ID, records both the input reference and resolved ID, and runs that ID with
`--pull=never`. It copies the SDK map to the retained `return-r01.map` name.
Floating tags and malformed IDs are refused before Docker I/O. A local ID
whose inspected identity differs is refused before container creation.

The actual-wrapper fake-Docker test first failed against the old recipe:
full local ID exit 64; digest reference missing `return-r01.map` after the
fake SDK output. With the correction, six focused cases pass, including both
pinned forms, malformed inputs, bad inspect output, and mismatched local ID.
The existing recipe refusal tests pass. This is source and synthetic command
proof only: no Pico build, UF2, device access, or flashed-image attestation.

The later target build must use the separately materialized pinned SDK 2.2.0,
TinyUSB, upstream, and picotool-enabled immutable image documented in the
private dependency handoff. The recipe retains `--network=none`, read-only
source mounts, a new exclusive output directory, CPU/memory limits, and stage
cleanup. Its output ELF/map/listings/UF2 require separate review before any
host manifest can be trusted or any physical operation considered.
