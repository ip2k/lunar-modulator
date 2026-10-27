# Adaptive polyphony: first admission-cap experiment

The owner asked whether Lunar can shed voices when heavy usage would otherwise
exceed its timing budget. This authorizes an explicitly labelled adaptive
polyphony experiment, not a silent change to fixed-polyphony acceptance.
Default tracked engine capacity remains twelve. Native rate, operator math,
control/event order and the 34829 OSC24M-tick deadline remain unchanged.

## First bounded measurement

[verified] Private V141 copies V140 and limits `Instance::Allocate` to its
first eight slots. It retains all twelve slots in the instance layout and the
existing retrigger/oldest-released/oldest-held stealing order. This is fixed
new-note admission, not a dynamic controller or a new fade implementation.
No vendor code is copied. The M-VAVE archive's eight-slot DX7 capacity is a
useful comparison, not proof that stock firmware dynamically sheds voices.

[verified] Normal and ASan/UBSan host runs each complete 22052 blocks and
5645312 PCM bytes with identical output. A host assertion checks at most eight
active DX7 slots before every block. The first two mixed cases remain byte
identical (2822656 bytes). Cases 2 and 3 change intentionally; their hashes
are `e463c1c3` and `97a83c77`, following unchanged `6bcab227` and `46c02687`.
The stress fixture's held-note count is not total active engine polyphony;
eight held notes does not guarantee an eight-slot cap leaves its output intact.

The initial host fixture still asserted the original twelve-slot hash; it
stopped as expected. A second check assumed the first three cases were exact;
the comparison disproved that at the beginning of case 2. Only the private
experiment fixture was corrected. Production exact-PCM gates remain intact.
Host scripts and complete logs remain private under `scratch/devkit-20261023`
and the bounded Aeon task directory, `voice-cap-v141-proof-v3/summary.json`.

## Target run and experiment-specific output guard

[verified] V141 was installed application-only after acknowledged UART entry.
Its unchanged native guard rejected the intentionally changed case-2 hash
with fault 10308; no starvation preceded that rejection. It stopped after
16548 produced / 16546 harvested blocks. The receiver was closed with one
SIGTERM after two exact argv checks; terminal status and PID absence preceded
ordinary PING ACK. Its reset receipt is consumed and must never be retried.

V141b keeps that DSP unchanged and supplies the four precise hashes established
by both host builds to the private native fixture. It retains the existing
underrun, deadline, callback, finite-exit and full-count checks. This is not a
relaxation of the original fixed-polyphony gate: it is a separately labelled
reduced-polyphony run. The corrected target result follows.

## Next dependency

Measure whether the eight-slot cap gives the mixed producer meaningful
headroom without starving output. Then evaluate a render-owned dynamic limit:
retire quiet release tails before audible held voices, account for fade cost,
respond before the output queue empties and restore capacity with hysteresis.
Report active/admitted/shed voices beside deadline misses and underruns.
Fixed-cap success would not establish dynamic-controller or analog acceptance.


## V141b target result

[verified] The application-only dev-board run completes all 22052 produced,
harvested and submitted blocks, four cases of 5513 blocks each. All four
reduced-polyphony hashes match the independent normal/sanitizer host results.
Transport fault0, backend0, off/close0, IRQ late0, gaps0; final drain35,
ready minimum1. IRQ maximum1050 ticks. Parent unused445 words, heap4052
after DAC open. Finite workload returns `LUNAR_DEVKIT complete=1`.

| Mixed case | Producer mean ticks | Mean microseconds | Producer deadline misses | Consumer mean ticks | Consumer deadline misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 24578 | 1024.08 | 1 | 30479 | 0 |
| 1 | 28414 | 1183.92 | 0 | 32116 | 0 |
| 2 | 29775 | 1240.63 | 2 | 32131 | 0 |
| 3 | 29630 | 1234.58 | 2 | 32129 | 0 |

[verified] The deadline remains 34829 ticks (1451.21 us). Heavy-case producer
maximum39467 still exceeds it; the full buffered playback completes without
starvation. This does not pass a zero-producer-miss gate. V140's unchanged
twelve-slot workload starved after 907 heavy-case blocks; that incomplete
population cannot support a precise performance percentage against this
complete 5513-block run. The eight-slot run demonstrates useful headroom,
not sustained fixed-polyphony or listening acceptance.

The sole receiver PID714046 was twice exact-argv verified, sent one SIGTERM,
and reached terminal255/PID absence before ordinary PING ACK. Board is healthy
idle on V141b. No buttons, full backups, restore rehearsals, full-flash readbacks,
KA6 captures, Hera contact or physical FM-1 traffic. V141 and V141b reset
receipts are consumed and must never be retried.

Private target facts: `scratch/devkit-20261023/v141b-target-facts.json`.
Raw UART SHA256 `323036c55a2e72e22b309521780da2837bb6a98015edc7476104ab6e4e102e5c`.
Private candidate SHA256 `1eb2930aa20c73843675610f5b2b6f794c9bd515b7fcba55c6f09737799da622`.
No tracked engine default or hardware acceptance gate changed. The heartbeat
now explicitly preserves this opt-in adaptive-polyphony exception and remains
active. Dynamic retiring/fades, controller hysteresis and representative
30-minute analog soaks remain future work.
