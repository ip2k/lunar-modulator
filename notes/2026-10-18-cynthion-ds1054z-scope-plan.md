# One loaded-connector experiment — Rigol DS1054Z preparation

**Prepared only; not authorized or executed.** Recovery remains unproven.
This refines acquisition for the
[independent audit's one experiment](2026-10-18-cynthion-independent-audit.md#one-recommended-next-experiment),
without changing the emitted waveform, polarity, resistance or PHY settings.

## Owner's equipment and unresolved fixture

[reported: owner, this turn] Rigol DS1054Z; four stock passive probes; four
50Ω pass-through terminators; breadboard; two six-pin USB-C breakouts; Pico2W;
two four-wire USB-C/DuPont cables (white/red/green/black).

Use three stock probes switched to10× with matching channel attenuation, DC
coupling, short ground connections, high-impedance scope inputs. **Do not fit
50Ω terminators.** They change loading and invalidate the stock passive probe
compensation; neither these nor the Pico is needed for this measurement.
CH1=D+, CH2=D−, CH3=VBUS, each relative to the same verified USB GND. Start
with1V/div on data and2V/div on VBUS, positioned to include0V and positive
plateaus; verify offsets/range before capture. Fourth probe is spare.
This measures low-frequency levels/timing, not USB full-speed eye compliance.

[inferred: unresolved] Six-pin breakouts may include CC pull resistors intended
for a sink. Joining two sink breakouts is not automatically a transparent
USB-C pass-through. Four-wire cable ends expose no CC wire; wire colours do
not prove pin assignment. Therefore **no breadboard/cable assembly is approved
from this inventory alone**. Owner has been asked for pin labels, plug/socket
form, board/model and resistor markings, continuity meter availability and
scope connectivity. Need verified pin-to-pin VBUS/GND/D+/D− routing in the
actual orientations, intact appropriate CC arrangement, no unexpected Rd/Rp
or data pulls, and insulated mechanical connections at the FM1 end. Keep
leads short and avoid long breadboard data stubs. Prefer an already verified
transparent pass-through breakout if these parts cannot preserve CC.

[verified: owner photo] The pictured receptacle board labels VBUS,GND,CC1,
D−,D+,CC2. R4 andR1 appear marked512 (5.1kΩ). [inferred] Those are likely
CC-to-GND sink terminations; continuity must verify that assignment. The
photo does not establish the second board's routing or a transparent fixture.
No owner photograph is published with this plan.

The stock probe grounds and scope BNC shells are common and earth referenced.
Confirm USB-GND/earth compatibility before connecting; never put a ground clip
on D+, D− or VBUS or defeat scope protective earth. If grounding is uncertain,
stop and use a reviewed differential/isolated measurement arrangement. No
internal FM1 probing is planned. These are fixture preparation conditions,
not instructions to connect anything now.

## Actual memory limit and conditional acquisition alternative

[verified: manufacturer documentation] The series datasheet specifies up to
6Mpoints with three/four analog channels enabled, versus12M dual and24M single.
Check installed firmware/options: older units may expose smaller depths.
At1MS/s,6Mpoints spans6s; the original56s/≥1MS/s-per-data-channel continuous
record needs≥56Mpoints per data channel and **cannot be promised on this scope**.
The programming guide specifies stopped-memory raw reads in chunks; that is
not continuous lossless streaming. Frame-count marketing is not proof of
continuous coverage or zero dead time. Do not use slow roll/display data as
an equivalent record.

Proposed **two acquisition windows within ONE unchanged55.04s attempt**:

1. Early window: YT/sample mode, CH1–3 enabled, maximum available depth,
   nominal500ms/div (12div=6s), CH1 rising-edge single trigger near1.5V,
   approximately100ms pretrigger. Confirm actual sample rate≥1MS/s and total
   raw sample duration≥3.6s; verify pretrigger placement empirically. Arm only
   after disconnected preflight, fixture connection and READY verification.
   It must retain initial KEY, released160µs gaps, first KEY→PWM transition,
   full first2s PWM and cycle boundary. CH1 may not cross1.5V under a severe
   clamp: a missing trigger is a failed acquisition, not a license to retry.
2. Save all three channels' complete raw records and preambles while stopped.
   Preserve sample interval, origin/reference, scaling, sample count and hash.
   Establish monotonic timing of the first trigger with a bounded uncertainty,
   using a qualified scope interface. Complete this transfer before45s.
3. Re-arm the same6s window at approximately51s after the first key trigger,
   using a prequalified timer; rising-edge PWM should trigger within1ms in
   the penultimate cycle’s PWM. Require timing uncertainty≤0.5s. This must
   include the final drive release near55.04s and≥100ms after it. Save all
   three raw records/preambles again. Keep TARGET C absent throughout.

[inferred: acquisition feasibility, **not yet demonstrated**] At51s the
unchanged schedule is in penultimate-cycle PWM (last cycle starts51.6s); rising
edges continue, and a6s record can include terminal release. This strategy
has an unobserved middle interval and does **not** reproduce the audit's
continuous56s record. It can answer loaded-level/first-transition/final-release
questions if both windows succeed. It needs independent review and explicit
approval of that coverage reduction before an FM1 attempt. If continuous
coverage remains required, obtain suitable deeper-memory equipment or a
verified independent continuous analog recorder; do not claim software raw
reads extend this scope's acquisition memory.

Before involving the FM1, a separately authorized **scope-only qualification**
with its compensation output must demonstrate depth/rate, single-trigger
placement, timestamp uncertainty, three-channel raw transfer within45s, and
second-window timing. No such qualification has been performed. Do not write
a bespoke streaming stack: first assess an established DS1054Z/VISA client
against the actual interface and raw-memory/preamble requirements. LAN/USB
availability is pending; no network/interface/device command was issued.
If qualification fails, resolve capture strategy before the one FM1 run.

## Separately authorized physical run and abort

Use the **historically pinned repeat image** and settings from the immutable
packet, not the newly routed telemetry images, for the controlled comparison.
Historical image SHA256:
`8fcc78e502dc692cd6d0f8daeab01030c2ae815326e624879f95bb24b65cd28f`.
It reports layout8: do not use layout9 decoding on its raw words. Even a
waveform-equivalent new image would introduce a comparison variable.
No load or readout is authorized by this document; confirm actual loaded
identity/source separately before a run. Keep CONTROL→Mac and TARGET C
physically unplugged. TARGET-C VBUS disable does not isolate data.

After separate authorization and scope/fixture acceptance: follow the existing
empty-port four-state preflight, require mask15/READY/OEs0/no reported fault;
connect LEFT/OFF FM1 and approved fixture, verify READY, then arm acquisition.
One USER press begins the unchanged finite repeat; move LEFT/OFF→RIGHT/ON.
Record actual USER/switch times. A physical switch movement still does not
prove CPU reset. No retries, host handoff, loader or flash follow automatically.
Capture terminal read-only receipt only under that separate authorization.

Reviewed abort concept: operator immediately **disconnects the cable at
Cynthion TARGET A**, physically removing the active driver from the target;
do not press USER/RESET or attach a host as an abort. Confirm the fixture is
arranged for that accessible disconnect before arming. This isolation action
has not been rehearsed/accepted; rehearse on the unpowered fixture as part of
separately authorized qualification. Software DONE/OE readout remains evidence
to collect after isolation, not a substitute for an accessible physical abort.

Stop on preflight failure, uncertain wiring/ground, unexpected heating,
clipping/out-of-equipment-limit voltages, missing trigger/raw acquisition,
reported fault, unexpected sustained drive after terminal, or failure to meet
the final-window deadline. An early abort ends the single experiment; no retry.
Never alter drive settings live to improve a trace.

## Observations and decisions

Extract measured low/high plateaus and clamp behavior;10/10µs key timing,
MSB-first0x16ef,160µs released gaps;500/500µs PWM; D− idle; and settled data
levels and persistence≥100ms after release. Preserve raw samples and settings,
fixture description/photo, software source/artifact pins and operator timestamps.
Compare<0.8V low/>2.0V high only as USB3343 screening values; FM1 ROM thresholds
are unknown. Bias after release is not a bootloader identity.

VBUS absent/collapsing → resolve supply/cable path. Loaded lows clamped or
key/timing absent → localize delivery/load before protocol changes. Clean key
with no response → rejected key/listening alignment versus inactive/reset-held
CPU remains unresolved; next would be separately planned CPU rail/reset/clock
witness, not another blind retry. Persistent released D+ high → qualify a
full-speed host path before interpreting absent packets. No outcome here
alone authorizes flashing or establishes installability.

Sources checked2026-10-18:
- [Rigol DS1000Z datasheet](https://www.rigol.com/dam/global/downloads/brochures/en/data-sheet/oscilloscopes/DS1000Z_DataSheet_EN.pdf),
  specifications: channel-dependent memory/input impedance and supplied probes.
- [Rigol MSO1000Z/DS1000Z Programming Guide, manufacturer manual mirrored by distributor](https://www.batronix.com/pdf/Rigol/ProgrammingGuide/MSO1000Z_DS1000Z_ProgrammingGuide_EN.pdf),
  pp2-154–158(timebase),2-233–236(raw memory reads/chunk limits and STOP).
