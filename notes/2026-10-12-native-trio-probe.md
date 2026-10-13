# Native Trio integration probe

This is a build-only milestone toward the owner's native, web-installable
Lunar Modulator goal. It is not an installable image or full application.

## Results [verified]

- The owner observed white, red, green and blue bands after the V8 diagnostic
  boot. This is physical display acceptance of that earlier image; this native
  Trio probe has not been installed or tested on the FM1.
- Hera linked the native Trio probe without JieLi SDK archives and with no
  named undefined symbols. ELF SHA256:
  `845bb1237a42de8400bdbe4d1e580597ac2415ea0276f620947f978f333e4b17`.
- ELF regions fit the imported linker script: text 46,372 bytes, RAM text
  1,128, data 8, BSS 16,132, pool 161,792, and noinit 76. The RAM text
  disassembly contains no call instruction.
- Sixteen parallel Hera containers passed the adapter oracle: 128 note and
  velocity cases, 12,288 blocks of 1–64 frames, note release, unsupported-rate
  rejection, output equivalence, and caller-buffer canaries. All exit statuses
  were zero, with no container OOM. These are host CPU tests, not pi32v2
  arithmetic accuracy or real-time audio acceptance.

Private receipts are under `build/native-engines-16-20261012/guarded-probe/`
and `build/native-engines-16-20261012/adapter-oracle-verification.json`.
The remote campaign is `/home/claude/mvave-fm1/native-engines-16-20261012`
on Hera. Its `host-build.sh` and `host-launch.py` record the exact host jobs.

## Implementation and boundaries

The pinned GPL-3.0-only Dinghy platform is imported with its licences,
provenance and per-file hashes. The application uses the existing Lunar Trio
engine descriptor through a narrow C adapter, with fixed instance storage and
64-frame rendering. Audio mutations happen in the ISR; the main loop queues
key and USB MIDI events. The display reports peak and callback timing.

`tools/native/build_probe.py` verifies source pins and generates a guarded
platform copy. Exactly two checked adaptations skip boot OTA cleanup and
make the flash-write allowlist empty. Upstream files remain unmodified.
There is no firmware packaging or flash admission in this builder.

Follow-up build [verified]: no SDK source header directory was mounted. Using
the toolchain's C headers and a bounded C++11 placement-construction declaration
produced the same ELF hash above. The wrapper's unused `<cstring>` include was
removed. Full libc++ was evaluated against its official LLVM 4.0 source; it
would import exception and allocation declarations and transitive headers for
a single caller-owned construction operation. The small native-only header
implements that operation, without an allocator or a C++ library runtime.
Primary comparison: [LLVM libc++ new](https://github.com/llvm/llvm-project/blob/llvmorg-4.0.0/libcxx/include/new).

The subsequent guarded probe adds bounded event consumption and releases all
notes after queue overflow. Rendering rejects uninitialized, null, zero-length
and oversized requests. All 16 host shards passed again, with added unsupported
initialization, block-size boundary and all-notes-off checks. Target ELF SHA256
is `bfc32413e1bd9f0aff1c56c4285628fc7033e02d3f913a58e589c301546b3084`.
It links with no SDK archives or SDK source headers and no named undefined
symbols. These assertions do not establish real-time performance or full
toolchain source/licence reproducibility.

Stock flash layout and entry/recovery review, queue overflow hardware timing,
and physical audio checks remain required.
The application is a single-engine diagnostic, without the complete Lunar
interface, sequencer, effects or web installer acceptance.

## Semantic tooling limits [verified]

Rarefaction and Serena selected the primary checkout, not this worktree; their
shared selection was left unchanged. Serena found the common Trio descriptor.
Rarefaction found its declaration but returned zero callers despite the known
registry reference and inferred an incorrect fallback type. The absence of
target compile commands limits this index. Native branch-only code was checked
through source and actual Hera target builds; neither index proves pi32v2 ABI.

## Hardware continuation

The accepted V8 diagnostic is still the last installed image; stock restoration
has not been claimed. The earlier stock restore admission is stale and must
not be replayed. Obtain a fresh reviewed loader admission and two matching
backups before another flash operation. Preserve stock SPL, OTA/cfg and the
recovery route; no blanket erase or eFuse commands are authorized.
