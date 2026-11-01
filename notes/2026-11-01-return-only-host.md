# Fixed return-r01 one-attempt host: offline source only

Personal, non-commercial MIT source, based on exact integrated coordinator
`a7a1c310a346dcad03892557c4405470576ed00c`. This stream owns only the new
`tools/jieli/rom_return_once.py`, `tests/test_rom_return_once.py` and this note.
No ordinary recovery/Pico/shim/build/device source is changed. No real serial
connection, device command, native/Pico build, protected decode, dependency
installation or download was performed. The driver is disabled in production:
`REVIEWED_IMAGE_MANIFEST_SHA256` is **None** and fails before input reads,
campaign creation, serial import or port I/O.

The independent Pico wire contract is SHA-256
`6f5b203a0b07ecba8c16f392c4e3aa0f2122431d2ee9a8f11a912829e40ded09`.
Ready/upload/call have exactly one bounded LF reply, maximum 96 bytes including
LF; no CR, extra fields/bytes, pipelining or mount variation. The canonical
mount generation is nonzero uint32. Ready has a 10-second whole-phase budget;
open/upload/call/close have 5 seconds each. The driver sends exactly the
`rr01-ready`, `rr01-upload` plus fixed plaintext, and `rr01-call` lines, in that
order, at most once. It never imports generic fm1t, discovers ports, retries,
rekeys, queries after call or attempts automatic recovery. Observed stale or
extra bytes refuse; absence of future unseen bytes is not attested.

The payload is precisely `80 00` followed by 510 zero bytes, SHA-256
`898b7737d69e351e54b406aebda27652c04413344d19dfb698a8642e33b698f9`.
The reviewed **native payload source** manifest is
`firmware/rom-witness-return/manifest.json`, SHA-256
`e03ef5e05b1b8161bde6efc1fe4507a6bc2a743d5647f65f2fcd6ad79716800c`.
Its exact source hashes are checked locally without running a toolchain. This
manifest is distinct from the Pico variant's new build manifest.

Four explicit CLI inputs are required: data `--port`, new `--campaign`, exact
`--payload`, and `--reviewed-image-manifest`. There is no approval flag, pin
override, environment escape or public arbitrary memory API. The entire raw
reviewed-image JSON must match a separately reviewed trusted digest, which is
not yet populated. Its strict bounded schema contains:

- Fixed schema 1, candidate `return-r01`, source base above, contract hash,
  `return_payload_manifest_sha256`, payload hash, board `pico2_w`, build ID
  `rr01-pico-v1`, upstream `a7fb5e8ac692c528f8ed29e325911a3f4b8111d6`, and USB
  identity (`2e8a:000a`, product `Lunar fixed ROM return-r01`, interface 2,
  string `Return-r01 fixed data`).
- Full `strict_source_commit`, separate `pico_build_manifest_sha256` and
  `recipe_sha256`, exact `patch_sha256` keys `0001`/`0002`/`0003` (first two
  existing reviewed pins are fixed), and final `uf2` size/hash. No interim
  Pico source/recipe/hash is treated as final evidence here. The eventual whole
  manifest digest must be pinned only after source/build/artifact review.

These are source/build identities, never flashed-image or USB authentication.
The physical coordinator must independently establish which strict image is
flashed and select its explicit interface-02 port. Generic USB IDs and strings,
the build marker and mount generation do not attest a flashed image or target.
Even an exact OK is only bounded evidence consistent with ROM FB08 call-return
under the separate cold-ROM/provenance chain. ERR, timeout, disconnect, partial
write/reply, malformed/extra reply or crash is refused before call, or
inconclusive after consumed call intent. Hardware, flashed image, ROM ABI,
instruction fetch, watchdog and installation qualifications remain false.

The campaign parent must already be operator-owned, owner-only and unaliased.
The new mode-0700 campaign is an exclusive cross-process claim. Its creation
is parent-fsynced; immutable mode-0600 receipts use dirfd-relative exclusive
O_NOFOLLOW creation, complete writes, file fsync and directory fsync. A durable
`upload_attempted` precedes any upload byte; a durable
`jump_intent_consumed` precedes any call byte. No receipt or existing directory
is resumed, overwritten or removed, including incomplete/failure state. Every
created campaign stays spent; a new campaign after uncertainty is a separate
coordinator/owner decision. A final outcome is returned only after its receipt
is durable. A persistence failure never restores permission. Records contain
small hashes/IDs/timestamps, not the payload. Operator records are retained;
test-created campaigns are reproducible fixtures and are removed by test
cleanup only.

The installed POSIX pyserial flush is `tcdrain`, so write_timeout alone would
not bound it. A small main-thread POSIX SIGALRM/setitimer context bounds all
serial phases, including open/write/flush/read. Missing primitives, a non-main
thread, blocked SIGALRM or an active real-time alarm refuse before I/O; an
inactive previous handler/timer state is restored. The synchronous caller must
own this process-global alarm during a phase. No signal retry threads or
platform framework were added; existing pyserial is imported only after
preflight and durable campaign creation. Other platforms remain unavailable.

Tests use the actual driver, real temporary filesystem and a private fixture
manifest pin/fake serial seam. The CLI has no path to that seam. Causal checks
include every record open/write/file-fsync/directory-fsync failure, parent
fsync failure, partial writes, symlink/FIFO/no-overwrite, real competing
processes, process exits at upload/call, strict grammar/mount boundaries,
timeouts/disconnects, no later call after upload failure, no command after
call, and real SIGALRM interruption of blocking open/flush in isolated child
processes. No fake test establishes device execution or a valid future UF2.
Commands/results live in ignored `scratch/rom-return-host/`; owned pytest
trees are removed in the runner's finally block. Small logs/receipts remain.

Semantic tools were not re-rooted: Rarefaction remains at the primary checkout
and rejects external worktree paths. Serena absolute navigation matched the
existing source checker; direct pinned Git/source and actual tests establish
this new-file evidence. No shared project activation/restart or graph build.

Next gates: independent exact-source host review, integration regression, a
separately allocated Pico variant build and reviewed final immutable manifest,
then a separately reviewed source update to populate the trusted digest.
Physical coordinator/owner authorization and cold-ROM/flashed-image/ROM-return
assumptions remain separate. Source acceptance does not authorize opening a
serial port or any Pico/target action.
