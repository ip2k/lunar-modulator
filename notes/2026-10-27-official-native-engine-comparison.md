# M-VAVE native engine comparison — 2026-10-27

## Scope and provenance

[verified] Inspected `m-vave/fm1_open` commit
`4c7496daac04a95ff10d1afdcc8f9ead2dbabc41`, specifically its published
`sdk/lib/libfm1_engine.a` (SHA256
`733a96c5d32e00244e31d7d7c36a4c1fb7646114f218526ee6a0964e56f94ea2`).
This establishes facts about that SDK library, **not binary identity with any
installed FM-1 stock release**. The archive is ordinary unprotected `ar` with
one ELF member, `engine_startup.S.o`; no decryption or protection bypass occurred.
Raw object/disassembly remain private under ignored scratch storage.

[verified] REA symbol inspection evidence
`ev_188bfac2eb413172687e397e203c8c046324ffad3c0e5e9467bdfc1da88b11a2`
and relocation inspection
`ev_a5cfaa8ad0752d5156f4623d5974bf74b3cced296d43c01d8eb025ce82a1de26`
resolve native DX7 kernel names and sine-table references. REA's installed
objdump cannot disassemble pi32v2 (evidence
`ev_c14b35d429c03f740657c65391890565a928c70823a8011baf01a44999e4852d`);
JieLi's vendor objdump successfully decoded the ELF on bounded Aeon instead.
Symbol sizes and instruction inspection are not runtime cycle measurements.

## Verified differences

| Area | Published M-VAVE native library / APP | Lunar measured path |
| --- | --- | --- |
| FM operator arithmetic | Native assembly references 1024-entry 16-bit logarithmic-sine and exponential tables. Gain adds in attenuation domain, then table/shift/sign reconstruction; no per-sample sine-interpolation and amplitude multiplies in the inspected pure kernel. | msfa interpolated sine plus linear gain multiply; compiler already lowers interpolation to a bounded 32-bit multiply and gain to a signed wide multiply/shift. |
| Kernel specialization | Distinct 64-sample pure/modulated/feedback add/store assembly kernels, plus fused two/three-operator feedback loops. Hot code in volatile RAM sections. | C++ kernels and fused algorithm-5 pairs, also hot SRAM. Fusion and SRAM placement are already present; these are not new missing fixes. |
| Callback geometry | Public APP interface 128 frames, 44100 Hz; native FM kernels internally operate on 64 samples. | Acceptance workload is 64 frames with fixed 34829-tick deadline. Increasing blocks changes latency/deadline and is not an accepted optimization. |
| Voice capacity | Native `.volatile_ram.fm1` bytes at voice_capacity are `8,4,11,8,8,24`, matching public source's DX7/303/808/PSG/pluck/sample capacities. Native voice-limit entry dispatches to synth_dx7_limit. | Heavy held DX7 workload uses 12 voices; reducing to eight would change the benchmark. |
| Cost accounting | Native voice_cost multiplies active count by a six-entry cost table and calls an engine-specific limiting/accounting path. | No conclusion that stock dynamically sheds voices follows from these symbols alone. Do not treat cost estimates as measured cycles. Adaptive shedding is now an owner-authorized, separately labelled experiment. |

[verified] Public Apache-2.0 `web/synth/dx7math.c::mk_sin` supplies a readable
counterpart to the native log/exp sequence. Native relocation records bind the
inspected assembly loads to `dx7_sin_log_table` and `dx7_sin_exp_table`, so this
is not merely an inference from browser source. The different quantization,
gain domain and rounding mean substituting it would change Lunar PCM.

## Concrete implementation work and result

[verified] Tested an independently written pointer-walk rewrite of Lunar's
`OperatorPair`: preserve every operation/order and replace output indexing with
a pointer walk. The idea came from native output-pointer handling, not copied
vendor instruction bytes. Normal and ASan/UBSan host runs each matched 22052
blocks, 5645312 PCM bytes and 1087869264 captured CPU0-state bytes exactly.
PCM SHA256 `ead722bab2f5fff43cc5959f258d1418defd7cdd197f8aefc9156bcf5329c6d3`.
Private proof report: `pair-pointer-proof/summary.json` on Aeon.

[verified] Standalone vendor compilation saved one instruction per sample in
the non-feedback pair. However, the full V140 LTO firmware link canonicalized
it back into the original indexed loop. Therefore **no native speedup is
claimed and this candidate was not flashed or promoted**. The compiler-barrier variant then retained a pointer walk in the full link.
Its separate normal and ASan/UBSan runs passed the same exact PCM/state checks.
An empty register constraint emits no instruction and preserves pointer value.

## Next implementation decisions

1. Keep Lunar's exact arithmetic and rates for kernel comparisons. Evaluate native kernel
   scheduling only against final linked machine code, not standalone object size.
2. The larger available change is a logarithmic DX7 operator backend. It must be
   an explicitly separate audio comparison experiment: not an exact-PCM fix and
   not silently substituted for the current engine. Measure matched patch,
   voices, events, block size and output quality before proposing promotion.
3. Continue the already proven copied-state CPU1 suffix-assist experiment for
   the actual remaining heavy-case gap. It preserves existing operator math;
   its host proof does not establish target cache, stack or deadline acceptance.
4. Do not run the proprietary SDK archive on the generic dev board or redistribute
   it as an optimization shortcut. Its separate FM-1 component terms and our
   distribution rules still apply. Public Apache components retain their own
   terms; no vendor implementation was added to tracked Lunar source here.

## V140 target result

[verified] One application-only install and one unique reset of V140 were run
on the dev board. No backups, restore rehearsal or full-flash readback.
The sole receiver was closed with one SIGTERM after two exact argv checks;
terminal255 and PID absence preceded ordinary PING ACK. The reset receipt
`iteration-two-slot-v140-20261027` is consumed and must never be retried.
No physical FM-1 traffic occurred.

| Case | V138 producer mean ticks | V140 producer mean ticks | V140 blocks |
| --- | ---: | ---: | ---: |
| 0 | 24643 | 24512 | 5513 |
| 1 | 28638 | 28339 | 5513 |
| 2 | 31118 | 30727 | 5513 |
| 3 | 36181 | 34647 | 907 |

[verified] Complete cases 0..2 retain hashes `6bcab227`, `46c02687`, `1e2f305d`.
Their producer means improve by 131/299/391 ticks (5.46/12.46/16.29 us).
Heavy V138 covered 139 blocks whereas V140 covered 907; these populations
are different, so no precise heavy-case gain percentage is justified.
V140 heavy still has 397 producer deadline misses and ends with output
starvation10304; this is NOT acceptance. Worker backend errors0, IRQ late0,
gaps0, max1098 ticks; parent unused445 words. Heap5620 before DAC/4052 after.
Raw capture remains private `scratch/devkit-20261023/v140-uart.bin`.

[verified] Production source now carries the pointer walk and a pi32v2-only
opaque register constraint; other targets retain ordinary portable C++.
The vendor compiler macro is `__PI32V2__` (verified by its preprocessor).
Production DX7/kernel tests pass all 160 cases on bounded Aeon with clang.
The actual browser WASM rebuild passes 108 parity cases. An independent local
build-record check passes exact module/source hashes, imports, pinned images
and sequence records. The local pytest runner was unavailable (no pytest);
that check was performed with Python standard-library assertions instead.
CI/review/merge and sustained hardware acceptance remain distinct gates.


## Adaptive polyphony: owner direction

The owner asked whether voices can be shed when heavy usage would otherwise
exceed the timing budget. Adaptive polyphony is now an authorized experiment;
do not apply the earlier fixed-polyphony constraint as a blanket prohibition.
It must be identified separately from the unchanged twelve-voice benchmark.

[verified] Lunar's `Instance::Allocate` in `engines/src/msfa_dx7.cc` already
reuses a matching key, otherwise a free slot, then the oldest released voice
before an oldest held voice. `Quiet` detects released carriers that can remain
silent. Neither is an adaptive render-budget controller.

[inferred] A useful next experiment is an explicit render-owned voice limit,
reducing quiet release tails before audible held notes, driven by measured
producer time and output queue headroom. Avoid controls that change renderer
state from another CPU while it is executing. Measure fade cost and clicks;
a fade does not make the current block free. Restore capacity with hysteresis.
Record active/admitted/shed voice counts, deadline misses and output starvation;
never label reduced-polyphony success as a fixed-twelve-voice pass. The native
eight-voice capacity is verified for this archive, but dynamic stock shedding
has not been established.
