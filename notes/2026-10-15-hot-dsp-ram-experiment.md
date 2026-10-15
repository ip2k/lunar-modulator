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
