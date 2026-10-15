# Stopped-transport IRQ and render measurements

[verified: retained transaction and capture] The one-use ROM89 campaign
installed209 sectors within the211-sector application envelope. Full readback
matched `a2c7eee6ca72659435452b59bd381fa8556b05a4fdc898329de3ea4fcdbf41d4`.
Fresh paired predecessor reads matched `bc593f95…fb566`. Firmware source is
`3e8664b5`, runtime source `280f48ad`. The single reset reply was ambiguous
(host7/info1/resid16) and was not retried. Separate native USB90 observation
preceded input-only telemetry. Both110s telemetry and180s six-channel KA6 audio
completed successfully. Passive sysfs afterward identifies ROM91, bus1/path1-1,
4c4a:8057. Do not relaunch the consumed ROM89 campaign.

## Idle baseline

[verified: decoded counters] No autoplay, USB MIDI messages, accepted note-ons,
or UART bytes occurred. This is the configured Event Horizon graph with stopped
transport, not an empty application. It still processes four sound slots,
Hall, limiter, and modulation/control dispatch. All thirteen engines remain
linked; these measurements do not mean thirteen engines render concurrently.

There are55 schema1,28 schema2,28 schema6,11 clock and11 PLL frames,133 total.
First/last schema1 uptime10102/118023ms spans107.921 firmware-reported seconds:
315.564 produced blocks/s and373.764 underruns/s. The expected output demand is
approximately689.34 64-frame blocks/s. Stopped-transport performance fails.

[verified: schema6 arithmetic] Twenty-four adjacent windows wholly inside
uptime10s..110s have zero overflow/mismatch. Median raw ticks per
firmware-reported second:

| Quantity | Raw ticks/s |
| --- | ---: |
| Tracked IRQ union | 2,178,647 |
| Render elapsed, including nested IRQ | 21,516,695 |
| IRQ union inside render | 1,957,948 |
| Render elapsed excluding measured IRQ | 19,558,664 |
| IRQ union outside render | 220,451 |
| Input handler, inclusive | 1,437,554 |
| Timer5 handler, inclusive | 1,824,678 |
| ALNK0 handler, inclusive | 379,151 |
| USB poll subregion, inclusive | 139,825 |

Inclusive source rows overlap and must not be added. Median input/USB service
rates are9983.22/1996.71 calls per firmware-reported second. Measured IRQ body
work is materially smaller than render mainline work in this diagnostic;
it does not explain the whole throughput deficit. This is not independent
clock calibration, an uninstrumented comparison, or a final root cause.

## Stage breakdown

[verified: schema2 window totals] Excluding the first startup profile,33984
master-effect calls provide the block denominator. Stage totals reset after
successful report publication; consecutive reports must not be differenced.

| Stage | Mean raw ticks per rendered64-frame block |
| --- | ---: |
| Sequence dispatch, inclusive of sound calls | 38,781.24 |
| Sound0 drums | 13,537.47 |
| Sound1 sixop | 10,619.07 |
| Sound2 Trio | 1,545.56 |
| Sound3 acid | 1,184.07 |
| Master0 Hall | 11,092.67 |
| Master1 limiter | 10,070.24 |
| Postmix | 6,955.13 |
| Display strip, amortized over rendered blocks | 238.69 |

Sound rows nest inside sequence dispatch. Stage timings include interrupts
and profiling overhead; schema6 subtraction is available for whole-render
timing, not individual schema2 stages. Current source reviews target concrete
repeated drum and dispatch work before changing behavior. Silent-block bypass
must preserve tails, phase, envelopes and future note behavior.

## Evidence and limits

Private evidence is `scratch/irq-profile-result/physical/`. Completed archive
is218306560bytes/20 members, SHA256
`61186d2140184f34c801e00a90cf954d91170e2f1612ef2eb410d509880d8b1b`.
An earlier archive retained with `-missing-member` suffix has a nonzero tar
exit because transaction/result.json does not exist; it is not the evidence
archive above. The durable result is install-session-result.json.
Events SHA256 `be05e557e06bc25d5bccf258bfacee4142856ebb82cb90c7f2a863fc3636b82b`;
raw SysEx `4741c42c7dfc3c7a86918d8604ee8b5c71333df3320919f1385aca7e6d9f9776`.
Archive telemetry bytes match the separately retrieved completed recording.
Receipt hashes match both. Window helper regression6 passed; independent
measurement review is scratch/irq-profile-build/measurement-review.md.

Firmware uptime derives from TIMER4 using the configured24ticks/us conversion;
raw rates do not independently establish real seconds or CPU MHz. Short
snapshot skew, excluded ISR assembly/prologues and profiling overhead remain.
No window spans a full uint32 counter wrap. Source/build receipt fields carrying
offline/mock scope remain historical provenance; physical evidence is the
simulated=false install result plus complete adapter/journal/readback and
separate native USB observation. Neither establishes musical acceptance.

Owner cold-boot screen/audio acceptance remains FAILED. SAVE remains disarmed;
no release or complete-device claim follows. Next: optimize measured render
costs with behavioral equivalence checks and a fresh matched hardware comparison,
then resume active notes/full-song acceptance and remaining release gates.
