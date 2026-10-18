# Finite Pico-inspired Cynthion repeat profile

Personal, offline source/test work; coordinator owns every device operation.
Base 0db2b5d9875eff1bcdc5da1142546ca83a0734c6, isolated branch
`fix/2026-10-18@cynthion-pico-repeat` in
`/Users/likwid/.codex/worktrees/cynthion-staged-key/mvave-fm1-firmware`.
No source changes in integration checkout. No SSH/Hera, containers, FPGA/target
build, USB/MIDI, gateware load or device operation in this task.

## Evidence and deliberate differences

[verified: primary source fetched/read] czietz's
[gist](https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5)
loops forever: 3000 two-byte writes at requested50kHz, then two seconds requested
1kHz/32768 PWM. Nominal SPI defaults are polarity0, phase0, eight-bit MSB-first
([MicroPython API](https://docs.micropython.org/en/latest/library/machine.SPI.html)).
Actual Pico frequency/timing and pin voltage were not measured.

[verified: pinned source read] MicroPython
[v1.19.1 RP2 SPI protocol table](https://github.com/micropython/micropython/blob/v1.19.1/ports/rp2/machine_spi.c#L281)
has init/transfer, no deinit callback; [generic deinit](https://github.com/micropython/micropython/blob/v1.19.1/extmod/machine_spi.c#L52)
only calls a non-null callback. Thus spi.deinit is not evidence of high-Z.
Exact idle D− retention remains unmeasured. Our intentional released160us gap,
released PWM D− and finite16 cycles are explicit differences, not equivalence.
Existing1kΩ series resistor electrical limitation remains unresolved.

## Before and after

Original staged operation is evidence-reactive: USER1 disconnected preflight,
READY, fresh USER2; KEY8us low/12us high can stop on candidateACK; WAIT_DP
requires reportedJ; SOF4us low/released remainder can complete on cached reported
SE0. Those modes and layout7 remain unchanged.

New explicit `pico-repeat` keeps exactly the staged disconnected preflight,
READY and fresh USER2 interlocks. It then executes16 cycles (owner refinement
from initial3): 3000 words0x16ef MSB-first, clock10us low/10us high, each followed
by released160us gap; then fixed2s push-pull D+ at1kHz/50%duty, D− released.
No ACK stop, WAIT_DP or reportedSE0 early DONE. Fixed cycle3.44s, total55.04s
from KEY start; held/repeated USER never extends or restarts it. LED5 alone and
both OEs0 at terminal DONE. FAULT is also absorbing. All existing electrical
interlocks and explicit PHY-fault masking remain active throughout. USER2
resets only pico's microsecond divider so even the first bit has complete10/10us
intervals at a divided clock; other modes are untouched.

The finite state machine counts words at end of each gap and cycles at end of
each fixed PWM duration. Core cycle parameter validates integer1..16; words
1..65535, positive32-bit PWM duration divisible by the positive integer period,
50%duty required. Build profile hardcodes16/3000/2,000,000us/1000us/500us, with
no CLI waveform override. Short core parameters are for bounded simulation.

## Read-only identity and counters

Only pico-repeat uses layout8. Status bits15(staged) and16(pico-repeat) are1;
existing modes still layout7. Register0x65 =0x0bb81001: profileID1 bits0..7,
cyclebound16 bits8..15, words3000 bits16..31. Register0x66: completedcycles
bits0..7, words completed in currentcycle bits8..23. At DONE16/3000 remains.
Neither register changes hardware behavior. Existing stateIDs/register meanings,
FAULT/DONE terminal history and READY nonterminal capture rules remain intact.
Counters describe emitted schedule, never ROM acceptance or calibration.

## Validation and limits

[verified: offline Amaranth] Final focused suites63 passed. New checks exhaust
all16 bits,20us perbit,160us gap, PWM phases and exact duration across accelerated
1 and16 cycle bounds under cachedSE0, candidateACK and invalidRXCMD; no WAIT_DP
or premature completion. Sixteen gate/phase combinations prove immediate
combinational masking then absorbingFAULT during KEY/GAP/PWM-low/PWM-high.
A2MHz test verifies complete first-bit divider intervals. Argument bounds,
physical staged start and held/repeated USER terminal behavior covered. Existing
operation/disconnected/staged and protocol review/ACK-gap tests remain passing.
A temporary float-valued old SOF threshold in initial new tests was corrected to
integer1ms; no production timing conversion was changed. Dependency warnings
are deprecation/unused-elaboratable warnings, not failed assertions.

Interpreter: existing `/tmp/lunar-installer-service-test-venv/bin/python`,
PYTHONPATH existing Cynthion Python3.12 site-packages; pytest no cache/no addopts.
Shared semantic startup previously showed original checkout roots for both
Rarefaction/Serena; not retargeted during concurrent work, source inspection used.
No semantic practical evaluation or new hardware success claimed.

Next dependency: coordinator source review and exact branch integration; reader
must explicitly recognize layout8 and these counter fields. Separately authorized
build/physical procedure remain coordinator work. Source simulation cannot prove
FM-1 voltage compatibility, clock calibration, USB identity, recovery or restore.

## Coordinator integration, routed build and SAFE load

[verified] Integrated as `fef11263c88f4b79193ceff9b590094110124491`, pushed
and remote SHA compared. Independent combined ULPI/key/power suites: 117 passed.
Final source/test hashes match the independent test inputs. No main merge or
full-CI success is claimed.

[verified] Aeon build root:
`/home/claude/.local/share/codex-builds/lunar/cynthion-pico-repeat-20261018`.
Pinned prior image/venv/OSSCAD, source archive and six source pins checked by
runner. Container `8e4a0af06aae0aee10b119768545008c9acb59d5df01445dc0da8bbb44be54a6`
exited zero without OOM. Root checked 4 CPU, 8 GiB RAM/swap, 512 PID,
docker-batch.slice, network none, read-only root/inputs, no capabilities/devices,
no-new-privileges and uid1003. Final routed clocks: 67.29 MHz PASS60 and
194.93 MHz PASS120. Netlist/LPF confirms CONTROL power1, C/AUX/discharge0,
N4/P3 bidirectional LVCMOS33/PULLNONE. Container removed only after retained
logs/created/terminal/artifact receipts; shared handoff saved and own claim released.

Bitstream 170402 bytes, SHA-256
`8fcc78e502dc692cd6d0f8daeab01030c2ae815326e624879f95bb24b65cd28f`.
Local root evidence: `scratch/cynthion-pico-repeat-20261018/`, including
root-review.json, input-pins.json, source.tar, runner, logs and read-only reader.

[verified] After owner confirmed both TARGET ports empty, volatile load exited
zero. At 08:13:49 UTC, read-only layout8 capture verified SAFE, PHY ready/no
fault, both outputs disabled, profile0x0bb81001, cycle count0, packets0 and no
terminal receipt; safety fields stable over sweep. Requested one USER press
with both ports still empty for disconnected self-test. No connected repeating
attempt has happened yet, and no FM1 loader/flash command was issued.

Owner also requested deeper Facedancer research. Source review is retained in
`scratch/cynthion-facedancer-deep-review-20261018.md`: maintained Moondancer
exposes USB-device/endpoint/connect controls; no raw recovery-line or host
controller API was identified. An inert emulator could validate ordinary USB
on an empty target path; a PHY-driven recovery sequencer is separate design work.

## Connected repeat completed; USB enumeration failed — 08:20 UTC

[verified: physical JTAG schedule receipt] During the run, read-only observation
saw eleven completed cycles. Terminal capture at 08:17:54–08:18:02 UTC records
DONE7, terminal receipt0x701, no PHY fault, both output enables0, sixteen
completed cycles and3000 words in the last cycle (reg0x66=0x000bb810),
last PWM duration2000000us. State/GPIO/terminal/history fields were unchanged
over the final sweep. These are sequencer receipts, not FM1 acknowledgements.

[reported: owner] TARGET C connected after the requested repeating procedure;
owner did not separately state the final LED pattern. [verified: bench kernel]
At08:17:41–43UTC, port3-2 detected full-speed attach, descriptor read/64
failed-71, setup-address attempts failed, and USB enumeration failed. Fresh
08:20:19UTC lsusb shows roots and KA6 only; no FM1 application, OTA or ROM
identity. The180-second kernel follower ended with expected timeout124.
No loader, flash, MIDI, firmware-write or additional trigger command was sent.

Evidence under scratch/cynthion-pico-repeat-20261018/: terminal-status.json,
run-observation-status.json, host-enumeration-after-connect.txt and
live-kernel-log.txt. Requested direct FM1→bench01 with verified cable,
RIGHT/ON unchanged and no power cycle, to separate Cynthion's passthrough
path from device response while retaining any current ROM state. Pending owner.
Recovery remains unproven; do not repeat identical attempts automatically.
