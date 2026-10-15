# Selected DSP bodies in RAM: bounded diagnostic experiment

The prior physical PLL diagnostic still failed audio acceptance: approximately
257 produced blocks/s against 689 required. Moving selected render bodies from
XIP into existing reserved RAM tests one possible instruction-fetch cost; it
does not establish the cause or promise a performance improvement.

[verified: source and host tests] `--hot-dsp-ram` is an explicit catalogue,
application-builder and artifact-flattener option. Selected sixop, Hall, limiter
and application render bodies use a separate `.ram_dsp` load segment copied at
startup. Linker and artifact checks bound it below 0x01C06000, disallow overlap
with the flash writer and preserve the debug reservation. Flash-writer
`.ram_text` call allowlisting is unchanged. Raw image call and stub-boundary
proofs carry the new section's independently validated flash load mapping.

The effective default linker script matches original SHA-256
833d79ca882336b4d61b2a977e6b4e13b5aed99e26fa21423fceb0b58ca0f16b.
Catalogue receipts must explicitly bind the RAM option and source inputs.
Only bounded diagnostic and song-diagnostic modes accept this experiment.
Callees and data may still live in XIP; full RAM residency and execution during
flash writes are explicitly unverified. SAVE remains disarmed.

[verified: host] Coordinator reran the optimization, synthetic ELF artifact
and catalogue receipt suites successfully. Review additionally found and fixed
a missing raw-image stub-boundary mapping for `.ram_dsp`; its regression checks
exact mapped bytes and rejection after mutation. These are host checks, not
target ABI, linked footprint, instruction timing or physical audio acceptance.

Next: fresh exact-source sixteen-shard catalogue on Hera, bounded diagnostic
link, independent inspection of actual section and selected symbol extents,
startup copy/disassembly, call audits, app budget and immutable receipts. Only
after admission checks prepare a new one-use hardware capture campaign. Previous
ROM73 PLL campaign is consumed and must never be rerun. No device operation has
been performed for this source change. Firmware/recovery/web release goal remains
active and unaccepted.

## Fresh linked target and offline admission

[verified: Hera build and copied receipts] Exact source
`e85a42f3a0a031f1f0e4f2c7d4f12bc3bbbaa083` built successfully in sixteen
fresh bounded catalogue shards followed by the EH+SET diagnostic link. The
successful v3 run preserves matching pre/post input snapshots. Earlier runner
attempts remain separate: one rejected invalid Docker mount syntax before
compilation; another completed compilation but rejected a host-generated Python
cache mutation. Neither earlier attempt is used for admission.

The successful app is 852,928 bytes (7,716 bytes below its 860,644-byte budget),
SHA-256 `8e74b08991959e5d1b36f80b878227568ac6d25b9e9f229836b3f5680cccbc00`.
Its ELF SHA-256 is
`8bfd4577643e48e98a384f05cdf78feafa8b988370280a941e5e9e69722756b0`.
Actual `.ram_dsp` occupies 3,196 bytes at `[0x01c00544,0x01c011c0)`,
loaded from `0x020cf7ec`; the four selected render symbols are present.
Independent inspection confirms the linked startup copy precedes app dispatch,
and mapped section bytes match the flat app. Heavy callees can still remain
in XIP: this is not full DSP residency. The existing narrow two-function
RAM flash-writer audit passes unchanged. Full saved disassembly is receipt-bound;
a new independent vendor-objdump regeneration was not performed locally.

[verified: host] Offline reconstruction now accepts this extra RAM segment only
with explicit selection and matching bounded diagnostic, disarmed SAVE and exact
ELF extent receipts. Default reconstruction still rejects an unexpected segment.
The four candidate/diagnostic/manifest suites pass 90 tests. This is not physical
installation, runtime execution or performance acceptance. Private actual-ELF
review and original frozen receipts remain under `scratch/native-hot-dsp-ram/`
and `scratch/hot-ram-result/`; no vendor binaries are committed.

## Fresh bench staging and constructed candidate

[verified: file-only bench checks] Fresh private staging at
`/home/claude/fm1-hot-ram-e85a42f3-20261015` preserves 172 pinned recorder
dependencies and two telemetry sources. A separate exact inventory checks all
249 tools files and ten directories before candidate construction and runtime
use. Tools archive is from coordinator commit bd687343; firmware remains exact
e85a42f3. Original ten-output v3 receipt is unchanged; a separate compatibility
seal verifies all outputs and container inspections before presenting the five
outputs expected by the existing generic gate. Nine seal, five staging, six
source-inventory and four one-use gate tests pass.

Constructed 1 MiB target SHA-256
`58c9aebbd9d167d5f2f069d0e9d73d5c76bb03d1a0e4d70dfaec49f324c0070d`;
candidate receipt `6da5eb7594d033f3bceab3481a8628aefbdf30093a10f3b4b1b171386b055880`;
input template `993504bc82288c4c992c46144b779f500276ff0b32fa0a2b96b430a267aca612`.
There are 211 allowed sectors and 210 changed sectors relative to the prior
installed 864445bea image. The bench staged `run-cycle.py --preflight` passed
file-only checks. No fresh ROM read or device write is claimed by this checkpoint.
The ROM75 cycle is prepared for paired full reads, journaled header-last update,
full readback, one bounded boot and analogue/telemetry capture. Prior ROM73
journal was re-read: complete, no pending intent, verified target 864445bea.

SAVE remains disarmed. Selected RAM bodies are not a full transitive residency
proof; performance, recovery independence, musical and release acceptance remain
open. Private campaign tools and tests are in `scratch/hot-ram-cycle/`.

## Physical campaign and recovery

[verified: retained bench journal] The one-use ROM75 campaign installed all
210 changed sectors and verified complete target readback SHA-256
`58c9aebbd9d167d5f2f069d0e9d73d5c76bb03d1a0e4d70dfaec49f324c0070d`.
Its transaction is complete with no pending intent. The single boot request
returned an ambiguous SG response; it was not retried. Native USB enumerated
as devices 76 and 77 before stable device 78. A fresh checksum-valid identity
query returned `FM-1_000`, confirming USB rescue rather than a running synth.
The recorder obtained no telemetry frames; its bounded timeout and partial
analog capture cannot support a performance comparison or audio acceptance.

[verified: one-use recovery journal] After independent source review, one
fresh identity query and repeated unique ALSA-client/card-to-USB ancestry
validation, the coordinator sent one soft key. ROM `4c4a:8057` enumerated as
device 79. No physical power cycle or flash operation was needed for rescue.
Private evidence: `scratch/hot-ram-result/physical/campaign-evidence/` and
`rescue-to-rom-once.jsonl`; helper SHA-256
`239875532dbd196163d0e63192c2b42e6adb67a50aaa466403978991bec98fa0`.
The ROM75 campaign is consumed; never rerun it.

[verified: source and linked ELF] The PC guard's RAM window ends at
`_rt_end - 1 = 0x01c00543`, excluding every new `.ram_dsp` instruction;
`fm1_app_render` is linked at `0x01c00f58`. [inferred] Its first execution
could cause the fault handler's eight-second delay and warm reset. No captured
fault record proves attribution; watchdog expiry remains another possibility.

The opt-in builder now extends only PC window 1's upper bound to `_rd_end - 1`
after ordinary guard setup, under the existing debug unlock/lock sequence.
The lower bound stays `_rt_start`, both sections retain the link-time RAMTEXT
bound, and default builds and the flash-writer closure remain unchanged.
Coordinator optimization/artifact/catalogue receipt suites pass (126 tests).
Fresh target build, exact guard disassembly and physical acceptance remain
pending; no new image has been installed for this correction. SAVE remains
disarmed and the overall firmware/web release goal remains active.

## Guard-corrected build and fresh campaign preparation

[verified] Exact source `1ce8948370a410ad418a7c6491dedd92093bb223`
(tree `06a45885598c1fd7d9f639f87c1094f3ed61aa6a`) completed 16/16 Hera
shards and link. App is 852,944 bytes, SHA-256
`9bd1d9c539b2c1b69ba66c96b1ae4a2b7819706c120f2134f88610a3c86b91db`;
ELF `f042c8ca2a440bd589d433fac983091c5c48319281b9a1c8694f0eb8c05fe7b7`.
Raw ten-output receipt `4afac8c20e03fdbebeeea9f7b99ced0c45284dcb495d3cb672230272e0ccc1e3`
retained unchanged; separate compatibility seal
`9c74c94572becc1c4a12bc54b6d0a9e722dcc0084fc66292814ac73f1f7fcbce`
checks the complete build before the existing generic gate.

[verified: independent ELF review] Both section copies precede guard setup;
PC_LIMIT1_H becomes `_rd_end - 1` before app_main. RAM DSP remains 3,196 bytes,
with 20,032 bytes free in RAMTEXT; flash headroom is 7,700 bytes. Selected
bodies retain XIP callees. Static evidence does not establish runtime speed.
Review: private `scratch/native-hot-dsp-ram/guard-elf-review.md`.

Fresh private base `/home/claude/fm1-hot-ram-guard-1ce89483-20261015`,
cycle `rom79-hot-ram-guard-cycle` (unconsumed at this checkpoint).
Offline target `0c32c1a9120cf79ff8b3f88fabc08f7d1e443a3708760c17b31052831b8e6d20`;
candidate receipt `b304c182c6c19aa2ede61026f2c16fea00313cc4963370bfc33abc914ae2d40e`;
template `59242eff465e4ff2ebc8d11ad52a68b3e96a1504db53c47c88d9a70d6cac67f9`.
211 allowed sectors, 209 changed from prior installed 58c9aebb image.
Runtime checks all 249 source files/10 directories and 174 capture inputs;
source inventory `3b12738cac9de94bcc5edbb2415a84d91e7325e816fdd9b4193ff4452b9a6219`,
runtime manifest `7227d8c4e5f1da2b798ad8ae2d0c89b76b111b50455c34f9191ec6519c388dea`.
Fresh staged file-only preflight passed, and independent runner/helper review
found no blocker. Fifteen source-inventory/staging/preflight tests pass.
An attempted reuse of older passive-capture tests exposed API/fixture mismatch;
those tests are being adapted to the current completed-install helper before
claiming capture-suite validation. No hardware action follows from test reuse.

Private helpers `scratch/hot-ram-guard-cycle/` require fresh ROM79 binding and
paired complete reads, journaled header-last update/full readback, ready analog
recording before one boot, no retry, input-only telemetry and bounded cleanup.
SAVE remains disarmed; no physical acceptance or installable-release claim.

## ROM79 campaign active; next bounded placement prepared

[verified] Root launched the reviewed campaign once with persistent PID78314.
Fresh paired reads passed; the header-last209-sector transaction is active.
No boot or runtime result is claimed at this checkpoint. Inspect
`/home/claude/fm1-hot-ram-guard-1ce89483-20261015/cycle.stdout` and the cycle's
transaction journal before any further device action. Never rerun this campaign.

[verified: host] All four current private capture/staging/preflight test modules
now pass together:31 tests and7 subtests. The first combined run failed one
staging mode assertion because importing the capture helper changed the test
process umask to077. The test loader now restores the caller's mask in finally;
no live runtime helper or frozen input was changed. Root reran the combined
suite successfully. This is test isolation evidence, not hardware acceptance.

[verified: source] A narrowly scoped next experiment annotates SixOp
`Instance::RenderBlock` with the existing opt-in RAM placement macro. The
current linked wrapper calls this1,382-byte voice loop in XIP. The macro is
empty by default; no DSP arithmetic or order changed. Independent host SixOp
baseline comparison passes six mode/rate scenarios,24,000 stereo frames each,
bitwise. Native placement/size and performance require a fresh build and
separate physical campaign. Private rationale and limits:
`scratch/native-hot-dsp-ram/next-placement-review.md` and
`render-block-handoff.md`. Do not add inclusive dispatch and engine timings.

## Guard campaign native boot and fifth-body receipt correction

[verified: device] ROM79 transaction installed and read back the target. The
single boot request returned ambiguous SG status; no retry was made. Native
USB device80 appeared and bound to Lunar ALSA client28. Ready analog capture
preceded boot; input-only110-second telemetry recording started afterward.
Completion/performance are still pending; native enumeration is not acceptance.

[verified: build] Exact32adfdc6 source linked on Hera16/16. Independent ELF
review places RenderBlock at0x01c00544 with592 bytes; .ram_dsp totals3788 bytes.
Startup copies it and PC guard covers it. XIP callees remain. The generated
receipt listed only four bodies, so this artifact is not admissible. Builder
and candidate verifier now require all five; source hash pins updated in
adapter and boot runner. Root reran58 focused tests successfully. A fresh
exact-source build is required; do not retrofit metadata onto the old build.

## Completed guard measurements and fresh five-body campaign

[verified: device evidence] Guard trial completed analog180s and telemetry110s,
then automatically returned ROM81. Counter deltas over device uptime give
256.896 baseline vs267.603 produced blocks/s (+4.17%); underruns432.456 vs421.741/s.
Still far short of approximately689 blocks/s: no playback acceptance. Private
archive SHA abbbe26167e80571c222241a18743a322a1dc1ae17bfbd474c1fda99a09789f1;
comparison scratch/hot-ram-guard-result/physical/comparison.json.

[verified: build and passive device] Exact9377348f rebuilt all16 shards on Hera.
Corrected receipt lists five bodies, .ram_dsp3788B, RenderBlock592B at01c00544;
XIP callees remain. Ten artifact hashes and independent ELF review pass.
Candidate b2d5b9505128398631d7fef2a268624ab00cba2d635653d2fc581953b925ffc1,
210changed sectors. Runtime/source pins, independent runner review and file-only
preflight pass. New root-owned bench base fm1-hot-ram-render-block-9377348f-20261015;
rom81-render-block-cycle launched once, PID84237. Fresh exact ROM81 USB binding
verified before launch. Installation/boot/capture outcome pending. Do not reuse.
The build archive required separately staged exact selection.json; constructor
then succeeded offline, before any device action. SAVE remains disarmed.

## Next offline experiment: inner FM voice placement

[verified: source] Extracted the existing opt-in placement macro into a narrow
header, and applied it to plaits::FMVoice::Render's declaration. Default builds
leave the attribute empty; no synthesis arithmetic changed. Vendored license
headers preserved and UPSTREAM records the local change. Builder/candidate now
require the sixth named body; stale missing-body and duplicate-body receipts
are rejected by focused tests. Four focused optimization/candidate/adapter/boot
suites pass. Target compilation, linked placement and equivalence remain pending;
this is an experimental source checkpoint, not an admitted installation artifact.
The active ROM81 campaign uses separately frozen five-body9377348f inputs.

## Six-body target link reviewed; wrapper placement is insufficient

[verified: frozen build and independent ELF review] Exact a7dc8fbe built on
Hera in sixteen bounded catalogue shards. All ten receipt-bound output hashes
match. App852604bytes fits860644bytes; .ram_dsp3816bytes and its flattened
copy agree. Startup copy, PC bounds and the narrow existing flash-writer audit
pass static checks. Independent evidence is saved at
scratch/native-hot-dsp-ram/fmvoice-elf-review.md.

[verified: disassembly] FMVoice::Render is only a28byte RAM wrapper calling
plaits::fm::Voice<6>::Render in XIP at0206679c. The compute-heavy implementation
was not relocated. Do not infer a speedup or admit another physical trial from
the wrapper's placement. Follow-up is to review the concrete template render
body and its callees. No DSP arithmetic changed; no six-body device write.
Installability, performance, SAVE and hardware acceptance flags remain false.

[verified: physical observation] The five-body ROM81 installation reached its
single boot request, which returned an ambiguous acknowledgement. No retry was
issued. Native USB82 appeared and the independently launched capture helper
is recording. Preserve the consumed campaign; capture completion, final
readback evidence and automatic ROM return still need inspection.

## Five-body physical result and actual FM-template source follow-up

[verified: physical evidence] Five-body transaction journal is complete with
intent null and verified targetb2d5b9505128398631d7fef2a268624ab00cba2d635653d2fc581953b925ffc1.
Telemetry110s and analog180s both exited0; nativeUSB82 automatically returned
to ROM83. No boot retry. Private campaign archive230195200bytes SHA256
d237de85ee3056560f5f581bc5b411f62d931130d7826a13b11e7b468050ad89,
safely extracted at scratch/hot-ram-render-block-result/physical/campaign-evidence/.
Counter rates: previous267.602634 vs268.253350 produced blocks/s; new
underruns421.092143/s over107.898device seconds. This tiny difference does not
resolve starvation against689.34375blocks/s demand or establish musical acceptance.
Comparison saved at scratch/hot-ram-render-block-result/physical/comparison.json.

[verified: host and source] Exact a7dc8fbe default and RAM-opt-in host SixOp tests
both pass six mode/rate scenarios x24000 stereo frames against the cached-accent
reference. This is neither cross-build PCM identity nor target timing proof.
The next source experiment annotates only the concrete FM-template three-argument
Render overload, preserving arithmetic and default behavior. Seven-body receipts
now require it; missing and duplicate template entries are rejected. Updated
source pins and four focused receipt/adapter/boot suites pass63tests.
Fresh target build and disassembly remain required; no seven-body device write.


### Corrected FM buffer-array overload (target review follow-up)

[verified: target disassembly] The 9b49b1c5 experiment moved only the 32-byte
float* temporary-buffer adapter. Its float** buffer-array overload remained
in XIP at 0x0206679c (1,956 bytes). The earlier description of that experiment
as relocating the compute body was premature. No seven-body image was flashed.
Independent review is saved privately at scratch/native-hot-dsp-ram/fm-template-elf-review.md.

[verified: source and host tests] The opt-in annotation now targets only
Render(Parameters,float**,size_t), and receipt names/source pins match it.
The source regression binds the annotation to the exact buffer-array signature.
All 63 focused builder/candidate/adapter/boot checks pass. Fresh target build,
actual compute-body RAM placement review and subsequent physical evidence are
still required. DSP arithmetic is unchanged; no performance claim is made.


### Corrected buffer-array target build completed

[verified: build outputs] Source d8586ae89f54cd266b2a42a8f45ad8976347244c
was pushed and remote SHA verified. Its fresh sixteen-shard Hera build completed;
all ten frozen output hashes rechecked locally. Private evidence archive
scratch/hot-ram-build/fm-buffers-d8586ae8-evidence.tar is 27,473,920 bytes,
SHA256 963fbee881037eeca78e46755af60a68fb62b6e225dc908e9adcdcab5f594ec1.
Extracted evidence: scratch/hot-ram-fm-buffers-result/.
The buffer-array Render symbol is now RAM 0x01c00544, size 710 bytes;
compiler optimization changes its size relative to the prior XIP copy.
Total .ram_dsp is 4,524 bytes, ending 0x01c016f0 below 0x01c06000;
app is 852,688 bytes. Calls into XIP remain. This is placement evidence,
not proof that all expensive work is in RAM or that audio starvation is solved.
Independent linked-code review is pending. Exact-source default/opt-in host
SixOp reference checks passed; report scratch/native-hot-dsp-ram/fm-buffers-host-checks/report.md.
No corrected-image physical write yet; fresh candidate admission/compatibility
binding and a separately reviewed campaign are next after linked-code review.
Bench device last observed in ROM83. SAVE remains disarmed and release unaccepted.

[verified: tests] MIDI parser/USB/UART/input integration checks again pass37tests.
Existing transport accepts FA Start (rewind), FC Stop (pause/gate release),
FB Continue (resume); exact FA rewind and TRS physical acceptance still pending.
F8 clock synchronization is separate. Goal remains active.

### Corrected buffer-array candidate staged (no launch yet)

[verified: offline artifacts] Independent linked-code review confirms the intended
710-byte buffer-array FM render body in RAM, with XIP callees remaining.
The compatibility seal rechecked all ten build outputs and sixteen container
shards. Original v3 receipt SHA256 is
7ff489dda3560c02c5778fe53097907868dcc84277922340f5381f4c3e5ce11d;
compatibility receipt SHA256 is
3495fab967ddf308e8de0aef8c1444f01a1b8aec32c928d0ebde13c561ed1a20.

[verified: bench filesystem only] New private base
/home/claude/fm1-hot-ram-fm-buffers-d8586ae8-20261015 contains the frozen
build and exact d8586ae8 tools. All 174 runtime dependency pins passed, including
172 retained environment paths; runtime manifest SHA256
78d5e61c80d792fb62c2c1871c3cd5e8845cc4a0707ced5d0e55695aba552eb0.
Offline constructor emitted a 1MiB target SHA256
3571d21401a921df425ff416824d32bca0f8ca4d1856ec007041cc5df875fbbb,
candidate receipt 6f7a318b8e14ca3d86afb3c36bf725150dd36a63a1ec87e118ee0b11ed04bc53,
and non-admissible input template
65f20b47ffa619f52266bd292c1581a8353d1a3f315fb269f59fbf27cf02c4f1.
Comparison against the previous target file shows 210 changed sectors within
211 allowed, protected ranges unchanged. That comparison is not a fresh device
read. Passive USB observation remains ROM83; no new flash/boot command issued.

Next: freeze and independently review the separate rom83-fm-buffers-cycle
runner; require fresh paired reads of expected current b2d5b950… before any
write. Single reset only, no retry on ambiguous acknowledgement. Timed return
to ROM, analog capture and telemetry remain distinct acceptance evidence.
The full goal remains active; audio starvation, persistence/recovery and web
release remain unaccepted. SAVE remains disarmed.
