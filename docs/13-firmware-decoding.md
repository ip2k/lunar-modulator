# 13 — Static firmware decoding

## What is implemented

`tools/fm1_decode.py` analyzes an extracted application without a device,
Ghidra, a vendor toolchain, or a subprocess. It provides:

- SHA-256 provenance, embedded identities and bounded ASCII strings;
- a verified V15 startup memory map, with file offsets distinct from runtime addresses;
- five fingerprinted startup/DSP spans, their decoded calls and remaining unsupported bytes;
- a partial pi32v2 instruction decoder with raw bytes for unknown instructions;
- independently located msfa algorithm data and mathematically reconstructed
  operator lookup tables from [16 — Operator mathematics](16-operator-mathematics.md).
- six effect dispatch records and eighteen callback pointers, with verified
  process roles and explicit uncertainty on initialization/update roles and
  names; see [18 — Effects decoding](18-effects-decoding.md).

This is **partial executable analysis**. It does not recover complete source
code, decode every instruction, prove all function boundaries, emulate a
complete voice, or establish hardware sound equivalence. A recognized opcode
at an arbitrary offset is not proof that those bytes execute.

```powershell
python -m tools.fm1_decode path\to\app.bin --output scratch\analysis.json
python -m tools.fm1_decode path\to\app.bin --offset 0x85064 --size 0x220
python -m pytest tests\test_fm1_decode.py
```

Use package extraction first for a FWSC file. The decoder accepts **application
bytes**, not a compressed/encrypted package. Inputs are limited to 16 MiB,
linear disassembly requests to 65,536 bytes, and strings to 4,096 entries.
The CLI refuses to overwrite its source with an analysis report.

## Fresh V15 address proof

[verified, 2026-09-14] The examined application is 581,564 bytes (`0x8DFBC`)
with SHA-256:

```text
306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203
```

Its XIP application base is **`0x02000120`**. Three independent absolute
register loads point exactly to NUL-terminated strings with this base:

| Instruction file offset | Instruction bytes | Loaded pointer | String file offset | String |
| --- | --- | --- | --- | --- |
| `0x2A054` | `c1 ff 6c e7 04 02` | `0x0204E76C` | `0x4E64C` | `EXT_RESERVED` |
| `0x2A376` | `c5 ff af e7 04 02` | `0x0204E7AF` | `0x4E68F` | `app_area_head` |
| `0x284FC` | `c1 ff 86 e7 04 02` | `0x0204E786` | `0x4E666` | `audio_server` |

Each `pointer - string_file_offset` equals `0x02000120`. This agrees with the
application-area metadata but does not depend on trusting that metadata alone.

**Correction to historical analysis:** the existing V009/V014 listings were
disassembled at file offset zero, and some prior reports added `0x02000000` to
their offsets. Those numbers cannot be used directly as V15 execution
addresses. A further complication is that part of the application executes
from RAM after a startup copy. Historical literal addresses and function names
remain research evidence; the decoder does not silently rebase all prior labels.

### Startup copy and zero initialization

[verified] Six-byte immediate instructions and their adjacent loops establish:

| File offset | Operation |
| --- | --- |
| `0x16` | Load BSS destination `0x01C0A05C` into `r3` |
| `0x1E` | Load zero count `0x195C0` into `r2` |
| `0x24` | Begin word-zero loop |
| `0x2C` | Load copy destination `0x01C00000` into `r4` |
| `0x32` | Load copy source `0x02084060` into `r1` |
| `0x38` | Load copy count `0xA05C` into `r2` |
| `0x3E` | Begin word-copy loop |

The resulting map is:

| Application file bytes | Runtime address | Interpretation |
| --- | --- | --- |
| `[0x00000, 0x83F40)` | `0x02000120 + file_offset` | Flash code and read-only data; not all bytes are instructions |
| `[0x83F40, 0x8DF9C)` | `0x01C00000 + file_offset - 0x83F40` | RAM initialization image containing executable code and data |
| No file bytes | `[0x01C0A05C, 0x01C2361C)` | Zero-initialized RAM/BSS |
| `[0x8DF9C, 0x8DFBC)` | Unclassified | 32-byte trailer beyond the copy extent |

The loaded RAM image also has flash source address `0x02084060`. That source
alias is not the runtime program counter used for calls inside the RAM routines.
For example, the startup call at file `0x7E` (`80 ff e8 0c c0 ff`) resolves
from actual XIP PC `0x0200019E` to RAM `0x01C00E8C`, backed by file `0x84DCC`.

The supported layout requires the complete startup fingerprint plus all three
literal/string pairs and the image size. A local edit outside those anchors can
retain this map. Function semantics are separately withheld when the exact
function fingerprint changes. An identity string such as `FM-1_015` alone
grants neither a memory map nor named functions.

## Fresh function spans and calling evidence

[verified byte extents; inferred semantic names] The following V15 spans have
explicit entry instructions and terminating returns. Their semantic names are
research hypotheses informed by the older AL-255 analysis and fresh references
to the algorithm and mathematical tables.

| Name | File offset | Runtime address | Bytes | Supported instruction bytes | Unresolved instruction bytes |
| --- | --- | --- | ---: | ---: | ---: |
| Startup/CRT | `0x00000` | `0x02000120` | 198 | 176 | 22 |
| Operator kernel candidate | `0x85064` | `0x01C01124` | 544 | 544 | 0 |
| FM core renderer candidate | `0x85284` | `0x01C01344` | 2,270 | 2,084 | 186 |
| Voice block candidate | `0x85B62` | `0x01C01C22` | 2,054 | 1,408 | 636 |
| Effects dispatcher candidate | `0x872BE` | `0x01C0337E` | 656 | 550 | 106 |

The voice span also contains ten identified inline jump-table bytes, excluded
from instruction coverage. Its two `tbb` tables are at file `0x85BB4` (six
entries) and `0x860D6` (four entries). Their target convention is
`table_runtime_address + 2 * entry_byte`. Arbitrary linear decoding outside
these identified spans can still interpret other embedded data as instructions.

The effects dispatcher ends with a return at `0x8754C`; a new function starts
at `0x8754E`. A wider span ending at `0x88904` includes unrelated routines and
must not be described as one effects function.

[verified call encodings] The main observed relationship is:

```text
voice candidate
  file 0x8607E -> runtime 0x01C01344, core candidate at file 0x85284
core candidate
  file 0x85554 -> runtime 0x01C01124, operator candidate at file 0x85064
```

This establishes specific encoded calls, not their reachability for every
preset. The core's calls at file `0x852A4` and `0x852B0` both resolve to
`0x02044E22` (file `0x44D02`). The function at that target has not been assigned
a verified library name by this decoder.

[verified data reference] At file `0x852E0`, instruction
`c1 ff 4c 7f c0 01` loads RAM address `0x01C07F4C`. The startup map resolves
this to the independently found 192-byte algorithm table at file `0x8BE8C`.
The operator's exponent/log-sine pointers and numeric interpretation are
documented separately in [16](16-operator-mathematics.md).

There are currently 21 call instructions in the five spans, including seven
unresolved indirect calls in the effects dispatcher. The six repeated slot
calls are at file offsets `0x8746C`, `0x87498`, `0x874C4`, `0x874F0`, `0x8751C`
and `0x87548`. Indirect calls retain their register operand and a null target;
they are not replaced with guessed addresses.

## Instruction decoder and validation boundary

[verified against independent local listings] pi32v2 instruction width is:

```text
first halfword has high byte 0xff: 6 bytes
otherwise its top three bits are 111: 4 bytes
otherwise: 2 bytes
```

All halfwords are little-endian. This width rule matched every decoded entry
in both existing vendor-tool listings examined locally:

| Oracle application | Listing entries | Supported forms checked |
| --- | ---: | ---: |
| `FM-1_009` | 199,931 | 168,935 |
| `FM-1_014` | 200,435 | 169,439 |

The supported operands and relative targets agree with those listings.
Stack register lists were checked separately. Entries marked unknown by the
vendor listing do not count as decoded oracle entries. In particular, its
unknown floating-point prefixes and following apparent halfwords must not be
treated as reliable instruction boundaries. These are **oracle comparison
counts**, not code coverage: the older listings themselves sweep through data.
V15 coverage is reported for the bounded spans above and remains incomplete.

Supported forms include immediate/register moves, direct and indirect calls,
short branches, register arithmetic/logic, sign/zero extension, stack saves,
several load/store forms, indexed table loads, bit extraction, compact immediate
arithmetic/logic, and conditional branches. Unknown forms preserve their
exact bytes. Six-byte direct calls use a signed displacement relative to the
next PC. An odd low displacement bit selects `gotoss`; it is not a call.

The reference SLEIGH definitions were useful but were not treated as an
oracle. Checks corrected short AND/NOT selection, special-register names,
stack forms, and the six-byte call form missing from the early Ghidra decoder.
Parallel issue markers are preserved, but parallel execution is not emulated.
For recognized packet encodings the following companion row shares a
`packet_file_offset`. The companion may read a register's value from before
the first operation writes it; a sequential Python interpretation would not
be justified. Unsupported arithmetic can retain a known packet marker without
claiming decoded arithmetic semantics. This decoder does not invent register
read/write effects for unsupported opcodes.

The complete compact-immediate expansion uses an eight-bit value repeated in
one, two or four byte positions, or an implicit-leading-one mantissa shifted
left. Known operator constants independently validate this rule:
`0xC80 -> 0x4000`, `0xC7C -> 0xFC00`, and `0xAE0 -> 0x70000`.
Every applicable decoded oracle entry agrees with the implemented expansion.

All **183 instructions / 544 bytes** of the identified V15 operator kernel now
have supported operands, including its signed gain shifts, 10-bit/5-bit
extraction, single-instruction predicates and 64-sample loop branch. This is
complete instruction coverage for that bounded kernel only; it is not complete
firmware or sound-engine decoding. Numeric execution and packet behavior need
the separate checks described in [17 — Operator ABI](17-operator-abi.md).

The default automated suite uses synthetic instruction vectors and malformed
inputs. It tests sign handling, addressing, truncation, the bounds on strings
and disassembly, stale-analysis rejection, source preservation, and the rule
that an identity string cannot grant a runtime map. An optional local fixture
test accepts a privately held, hash-verified V15 image:

```powershell
$env:FM1_V15_APPLICATION = 'path\to\private\app.bin'
python -m pytest tests\test_fm1_decode.py
```

The private image is never copied into the test directory. On 2026-09-14 all
85 synthetic cases and the optional V15 case passed. Live device I/O was not
part of this work.

## API and evidence schema

```python
from tools.fm1_decode import (
    analyze_application, disassemble, analyze_control_flow, address_to_offset,
)

analysis = analyze_application(application_bytes)
listing = disassemble(application_bytes, 0x85064, 0x220, analysis=analysis)
offset = address_to_offset(0x01C01124, analysis)
graph = analyze_control_flow(application_bytes, 0x85064, 0x220, analysis=analysis)
```

`analyze_application` returns `schema_version: 1` and kind
`fm1-executable-analysis`, with `sha256`, `identities`, `profile`, `regions`,
`functions`, `calls`, `features`, `dsp`, `strings`, `unresolved`, and
`device_io_performed: false`. Offsets/addresses are JSON integers; unproven
addresses are null. Region entries with a null file offset, such as BSS, cannot
be used to retrieve file bytes. Strings describe data presence only.
`dsp.effects` comes from `tools/fm1_effects.py` and requires the exact complete
V15 application fingerprint. Modified or unrecognized images receive no effect
annotations from that profile, even if their startup map remains supported.

`disassemble` returns a bounded list of instruction/data rows. Each row retains
file offset, runtime address when justified, size and raw hexadecimal bytes.
Supported forms include explicit operands; unsupported forms remain `unknown`.
The report independently checks the known span fingerprint before claiming a
verified starting boundary. Neither a stale analysis nor a fabricated function
list carrying the current image hash can grant that claim.

`analyze_control_flow` explores possible paths within a requested span, with
nodes, edges and explicit barriers. It stops at unsupported semantics, refuses
targets inside instructions/data, leaves indirect destinations unresolved and
does not assume callee return behavior. Predicate scopes over unverified
parallel packets stop a path. The V15 operator kernel's graph contains 183
nodes and 197 possible edges, with no unresolved barriers; loops terminate the
analysis through a visited-node set. The other reported spans still hit
unsupported instructions. This graph does not establish what ran on a device.

## Provenance and next work

Research sources inspected locally:

- [AL-255/FM-1-RE](https://github.com/AL-255/FM-1-RE/tree/95eca8488ac8c3b6f86287b2d3d43678e03e271a),
  revision `95eca8488ac8c3b6f86287b2d3d43678e03e271a`: V009/V014 disassembly,
  `analysis/db.json`, and synth/startup notes. Its project is WTFPL; vendor
  firmware/listings were used as private research evidence and are not redistributed.
- [kagaimiq/ghidra-jieli](https://github.com/kagaimiq/ghidra-jieli/tree/b5e60122b6cd3e6b615387035994b8bed0ea1a26),
  revision `b5e60122b6cd3e6b615387035994b8bed0ea1a26`: Apache-2.0 pi32v2
  instruction-field descriptions, independently checked as described above.
- [kagaimiq/jielie pi32v2 notes](https://github.com/kagaimiq/jielie/blob/1657d25e6e51df6b2c18cd55cfc576c4a6370c63/cpu/pi32v2.md),
  revision `1657d25e6e51df6b2c18cd55cfc576c4a6370c63`: additional instruction
  layout and compact-immediate facts, checked against the independent listings.
  No implementation or prose from those notes was copied into the decoder.
- The stock V15 application named by its SHA-256 above. All current addresses,
  calls, span fingerprints and table contents were checked against its bytes.

No vendor binary, private capture, full firmware listing or toolchain executable
is included in the contribution. Research scripts/listings remain ignored.
No native pi32v2 toolchain or working WSL distribution was available during
this work; existing local vendor listings were validation references only.
Normal analysis uses the new Python implementation.

Next work is to decode the remaining arithmetic, conditional execution and
branch forms; expand proven function/interrupt boundaries; follow indirect
dispatch through actual tables; reconstruct operator/voice state and complete
effect equations; and compare a rebuilt implementation with controlled hardware
measurements. Relocation-masked similarity alone is insufficient to claim
equivalent behavior across firmware versions.
