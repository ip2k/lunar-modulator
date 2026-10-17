# Continuous target storage receipt contract

[verified: real Aeon worker at `1aa5e4f1`, independently rehashed] The fixed
private continuous producer compiled and linked all 55 modules: 13 engines,
24 effects, 2 MIDI processors and 16 modulators, with Event Horizon and its
parent-bound companion SET. SAVE and stack watermark remained linked.
The app is 852,720 bytes against the 860,644-byte D7000 budget: 7,924 bytes
remain. Link layout and the SDK-free key audit passed (0 failures, 0 pending,
linked executable).

| Output | SHA-256 |
| --- | --- |
| App | `888ef842ea67fb46a010226456568452bc32b3ceca13362caaab7119774db437` |
| ELF | `fed2d7e47ff1120a4d5c15acdb57f21cfe6144e71dd6bf689408943dbd0e6c3b` |
| Verification | `c95d5bec63203dc3e2cf95f2056713ee55d45be3780136afb8f15700a74a4a1a` |

The producer then failed the controller's fixed storage receipt check. Its
pinned target compiler reduced `sizeof(fm1_app_t)` to 220,848 bytes for RGB565
and 163,760 bytes for indexed pixels in `app-storage-{0,1}.ll`. The controller
used older 220,832/163,744 dimensions unless the separate stage7 diagnostic
profile was selected. Both pairs give 57,088 bytes of pool credit, so the
Shapes8 compressed-RAM instance pool remains 165,376 bytes. The coordinator
read both actual target IR constants and the retained verification; this was
not a host `sizeof` measurement.

[verified: source/tests] An explicit continuous-runtime storage contract now
requires exactly 220848/163760/57088. Historical generic diagnostic and named
stage7 receipt policies stay separate. Tests accept that exact continuous
ABI and reject the old pair or changed RGB565/indexed/credit/pool values.
The existing pool, wavetable, runtime, identity, layout, hash and admission
checks remain. Focused controller/wrapper/capture suites passed 110 tests;
one optional private-artifact test skipped. A successful producer and tuple
capture still require a fresh run from the correction's committed source.

Private failure evidence is under
`/home/claude/mvave-fm1/private-continuous-producer-event-horizon-20261017/capture-uidfix/`.
The shared handoff is
`handoffs/lunar--continuous-producer-event-horizon-20261017.md`.
No worker-provenance or tuple was emitted on this failed attempt. This build
performed no device operations. SAVE remains disarmed and unbound to flash;
runtime, recovery, persistence, hardware and release acceptance remain open.
This private image is not yet an installable or releasable artifact.
