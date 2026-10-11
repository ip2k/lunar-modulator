# Independent fixed loader configuration native review

2026-10-11. Branch `feature/2026-10-11@installable-firmware`, worktree
`/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
This reviews the exact private offline loader candidate, not physical execution.
No firmware/source changes, transport operations, commits or tests were performed.
Root owns source integration, focused Hera tests, backup and hardware decisions.

## Result

The three fixed patches implement the claimed direct-call configuration change.
The selector becomes a valid leaf returning an uploaded zero-filled span; both
later decode calls become NOPs. The traced parser returns field absence and the
unchanged initializer selects SPI mode 2, bypassing the identified quad NOR
status-program paths. [verified: original and patched vendor native listings]

No actionable defect was found in this bounded offline transformation. This
closes the retained-configuration premise for the three direct selector callers;
it does not establish the side effects of every external initializer or prove
physical readiness. The generated profile correctly leaves those claims false.
[inferred from the verified bounded paths; verified profile source]

## Pinned inputs and evidence

| Item | SHA-256 |
| --- | --- |
| Original encrypted loader, 24,064 bytes | `d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376` |
| Original decoded loader | `db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e` |
| Original vendor listing | `8c9e903a41dfbb990a9cc1a20f14bc3deb31800de9965678b012ca7c9718e737` |
| Patched encrypted loader | `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c` |
| Patched decoded loader | `a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af` |
| Patched vendor listing | `f8aeedf382158f17627ce119b01e451ab5611b6cafed485dca385a226334776e` |
| Vendor pi32v2 objdump | `cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73` |

[verified: independently calculated private file hashes]

Native listing was generated independently on Hera in
`/home/claude/mvave-fm1/loader-fixed-review-20261011`, using pinned toolchain
`/home/claude/mvave-fm1/sdk-v1213/toolchain/current` resolving to
`jieli-linux-toolchains-20250324.1`. A private incbin assembly wrapper was linked
with `.text` at `0x01c02000`; clang used `-target pi32v2 -mcpu=r3`, and objdump
used `-d -mcpu=r3 -mattr=+fprev1`. Container `lunar-jieli-check:bookworm` had
network disabled, one CPU, 256 MiB, and a read-only toolchain mount. No vendor
bytes were committed. [verified: executed bounded commands]

Original local evidence is `/tmp/lunar-loader-run-app/`; candidate and new
listing are `/tmp/lunar-loader-config-20261011/`. Machine-readable evidence,
including current reviewed source hashes and exactly changed offsets, is saved
as `build/loader-config-native-review-evidence.json`. An independent
implementation of kagaimiq's `jltech/cipher.py` CRC stream, with seed restarted
for each 512-byte block, matched the candidate encryption. Every one of the
24,064 listed bytes matched the candidate: zero mismatches or unlisted bytes.
[verified: bounded independent probes]

## Instruction, caller and tail bounds

Exactly 16 bytes change: relative offsets `[0x84,0x8c)`, `[0x666,0x66a)`,
`[0x676,0x67a)`. At `0x01c02084`, the six-byte native instruction sets
`r0=0x01c07c40`, followed at `0x01c0208a` by `rts`. It touches no other
register or stack state. The original selector body is bypassed. Remaining
bytes after the return do not form reachable code on these reviewed calls.
The two original four-byte calls at `0x01c02666` and `0x01c02676` decode as
four NOP instructions. [verified: byte comparison and native listing]

There are exactly three direct calls to the selector in this listing:
`0x01c02454`, `0x01c0265e`, `0x01c0266a`. The first is the field parser;
the other two surround the removed decode calls. The latter sequence still
computes pointer+512, but the removed call does not dereference it, and the
later code overwrites `r0`. A supplementary whole-image little-endian pointer
search found no literal pointer to the selector or zero span. This supports
the direct-call scope; it is not a proof against arbitrary dynamic dispatch.
[verified: native listing and bounded search; inferred scope limit]

The sole driver-table entry occupies `[0x01c07c28,0x01c07c34)`: its name,
operations and context pointers are `0x01c0560c`, `0x01c07964`, `0x01c0974c`.
The lookup at `0x01c02556` advances by 12 and stops at `0x01c07c34`.
The proposed `[0x01c07c40,0x01c07c80)` span is outside that table, within the
unchanged 47-block upload `[0x01c02000,0x01c07e00)`, and consists of 64
original decoded zero bytes. Initial state clearing around `0x01c09600` and
`0x01c09974` does not overlap it. No write to this span was found on the traced
initialization/read path. [verified: original bytes and native listing]

Describe this as uploaded zero padding unchanged on the traced path. The
source comment's word “immutable” should not imply a global RAM write
protection property. Another loader command-dispatch path uses `0x01c07e00`
as a buffer; this patch is not a whole-loader elimination of that address.
[inferred wording qualification; verified native listing]

## Parser and default SPI/NOR path

At `0x01c0244c`, parser calls the selector and stores its pointer in `r7`.
The first record length is read at pointer+34 (`0x01c07c62`). Its zero value
makes `(length-1)&255` equal 255, outside the admitted 0..31 record lengths;
the body is skipped and return value is zero (absence). No record-name copy
or output-field write occurs on that branch. The five initializer calls at
`0x01c02684`, `0x01c02710`, `0x01c0271c`, `0x01c02738`, `0x01c02776` all
therefore receive absence. [verified: patched pointer, original unchanged
parser and direct caller paths]

The default SPI branch at `0x01c026e0` masks and sets the state with `0x10300`,
stores clock/divider byte 4 at +76, and reaches the common setup with
`(state>>15)&7 == 2`. The mode-3-only rewrite before NOR init is skipped.
NOR initialization at `0x01c03aca` releases deep power-down (AB), reads JEDEC
ID (9F), and follows a 4B identification read. The interpretation of the
latter as UID remains inferred. [verified native operations; inferred 4B role]

Mode extraction at `0x01c03b5c` takes the mode-2 branch to `0x01c03c8c`,
skipping `[0x01c03b6c,0x01c03c88)`: the reads of status 05/35, WREN 06, status
write 01 and fallback 31 found on the quad path. Later mode selection sets
SFC register fields; it is not a flash status-program transaction. Capacity
at most 16 MiB skips the B7 four-byte-address command. The recorded owner
JEDEC `0x856014` indicates 1 MiB; a physical probe must validate the exact
expected response instead of assuming the recorded identity applies.
[verified native branch/opcodes; reported prior owner ID; inferred probe gate]

This establishes the bounded direct mode-2 path's avoidance of the identified
NOR status programming, not a universal claim that the entire loader cannot
write flash. Destructive handlers remain present; retain the strict command
allowlist, with no FC12, raw A1 or FC16 configuration programming.
[verified native listing; inferred consumer requirement]

## Remaining integration gates and next step

The external initializer call at `0x01c0278e` targets `0x01e00428`, and the
entry-supplied operations can dispatch outside the pinned image. Their full
implementations were not established by this review. No source body was found
in the checked SDK/reference inputs. These are inherited evidence limits,
not evidence that the patch causes a write; keep the effects claim unverified.
[verified call/pointer boundaries; inferred confidence limit]

The existing backup Reader and diagnostic binding still pin the original
encrypted loader hash. They therefore reject this patched loader. Offline
profile generation alone must not loosen those guards. Root must provide a
separate explicitly bound adapter for this exact candidate and its complete
47-upload/run/read sequence, retaining identity and read-only command limits.
[verified current consumer source; inferred integration requirement]

The next concrete dependency is that adapter's independent source review,
then the staged read-only loader probe and two complete matching backups,
compared with the recorded unit/baseline before diagnostic sector programming.
Root determines whether inherited external-initializer uncertainty is acceptable
under the owner's recorded staged authorization. This review ran neither that
probe nor tests; `hardware_ready` remains false. Source-tree baseline is recorded
in the accompanying evidence JSON; parent owns tracked-note promotion and push.
