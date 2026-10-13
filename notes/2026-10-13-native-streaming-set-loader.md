# Native packed-set loader [verified]

`firmware/native/content_set.c` connects `fm1_state_bin_read` to the existing
`fm1_seq_import_begin/feed/end` importer. Decoded `FM1_REC_LINE` fragments go
directly to the importer; a newline is fed only on `FM1_REC_LAST`. It neither
allocates nor retains a whole set or line. The source must remain immutable.

The caller supplies an initialized scratch sequencer. Failure may change that
scratch instance, which must be discarded. This API deliberately does not
accept a live application or activate playback. Only standalone SET containers
are accepted; applying project engine/effect/modulation state remains separate.

The established importer ignores unknown lines and truncates data outside its
fixed capacities. Matching that importer is not strict semantic acceptance or
proof that every requested event fits. Application admission, lane resolution,
an atomic activation path and realtime playback remain required. The binary
reader's measured entry frame alone exceeds 8 KiB; this API is main-thread only,
and target compilation is not a complete stack-margin verification.

## Verification [verified]

Sixteen independent Hera containers ran eight cases under each of `-Os` and
`-Oz`. All sixteen passed with no OOM. Each case compiled and executed a host
ASan/UBSan harness and compiled the bridge with the pinned pi32v2 toolchain.
Successful cases compared complete canonical sequencer exports with the existing
whole-text importer: the golden orbit set, a long 256-note line crossing decoder
fragments, unknown-line behavior and a track outside the destination's capacity.
Refusal cases covered truncation, corrupted payload, a project supplied as a set
and non-Lunar input. Null arguments and oversized input were also refused. The
harness checked that a distinct live instance remained byte-identical.

The first campaign failed at host linking because the test omitted `-lm`, needed
by existing sequencer code. That receipt is retained; it is not passing evidence.
The corrected `content-set-v2-verification.json` is retained privately under
`build/native-external-arenas-16-20261012/` and on Hera's corresponding `out/`.
No USB, RAM-loader or flash operation was performed. This component is not yet invoked by the native application probe and is not
an installable firmware milestone.

## Optional native link checkpoint [verified]

`build_application_probe.py --link-set-loader` retains the decoder entry as a
linker root, reusing freshness-checked state codec objects already in the native
catalogue. It reports link verification separately from activation, stack margin,
semantic acceptance and physical verification; all latter flags remain false.

The 16-container `content-loader-link-v2` campaign retained the five-engine
profile, optional Plate and 0/1/2/4 text/binary source assets. Eight profiles
without Plate passed the full linked-image audit and protected artifact guard,
and final ELF content was compared byte-for-byte. Eight Plate profiles linked
but were rejected by the unchanged safety audit. No campaign-wide pass is claimed.

The audit hit is `.text +0x3751d` in `fm1_app_render`. Pinned vendor disassembly
of shard 08 shows at 0x0203763a `80 ff 0c 2e 01 00`, a relative call to
`__umoddi3` at 0x0204a44c; at 0x02037640 `02 15`, a register-pair move.
The scanned LE32 stub signature `2e 01 00 02` crosses those instructions
[verified for shard 08]. This is an audit false positive, but the audit remains
unchanged and these builds remain refused. The existing proof mechanism covers
complete relative-call payloads for eFuse checks only. Next: extend it narrowly
with matching ELF-byte/instruction/call-target proofs and negative regression
cases for real loads, data constants, damaged disassembly and out-of-function
instructions. Do not bypass the audit or whitelist a whole function.

The first loader-link campaign duplicated codec objects already supplied by the
catalogue and failed with duplicate definitions; its receipt is retained.
The corrected campaign used those catalogue objects. No physical operations
occurred, and all test containers were removed.
