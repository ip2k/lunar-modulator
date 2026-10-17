# Cynthion r1.4 USB_KEY prototype

This is an offline gateware prototype. It does not program or communicate with
a board from its build script. Build with `python -m tools.cynthion_usb_key.build
--build-dir PATH`; default mode is `operation`. That image starts with both
target GPIOs high impedance and requires the physical USER button to be stably
released and then pressed before its finite attempt can begin.

Every USB_KEY image leaves VBUS controls off by default. An operation image may be
built with `--target-power-from-control`; this enables only the r1.4
CONTROL-to-TARGET-A VBUS switch. TARGET-C passthrough, AUX VBUS, and discharge
remain off. This is an explicit build-time choice, not a runtime control. It
does not establish that a particular unit, cable, or power source is suitable;
the owner must review the hardware sequence. Keep TARGET-C unplugged while the
key attempt can drive lines; connect it only after terminal high impedance.
The disconnected-selftest mode rejects this power option and always leaves
all switches off.

`--mode disconnected-selftest` creates a separate image that automatically
drives the four USB line states through the N4/P3 series resistors after the
target PHY has passed its non-driving configuration/readback sequence. This
image has no reachable key-transmission state. **Both target ports must be
empty before configuring this image**, since the self-test intentionally drives
the target-side lines. It spends 1 ms on each expected line state. If one
state disagrees, it records the first failure, continues through the remaining
states for diagnostics, then faults and returns both GPIOs to high impedance.
The operation image still faults immediately on a self-test mismatch. The result checks
GPIO-to-USB3343-RXCMD loopback only; it does not prove ROM acknowledgement or
key behavior.

The ECP5 exposes read-only JTAG registers using LUNA's `JTAGRegisterInterface`:

| Address | Meaning |
| --- | --- |
| `0x01` | Magic `0x4c554e52` (`LUNR`) |
| `0x02` | Register layout version `6` |
| `0x03` | Status snapshot |
| `0x04` | Live GPIO: DP input, DM input, DP output, DM output, DP OE, DM OE (bits 0–5) |
| `0x05` | Self-test failure: reason (bits 0–1), step (2–3), expected state (4–5), last observed state (6–7) |
| `0x06` | GPIO input/output/OE snapshot latched at self-test failure (same bit layout as `0x04`) |
| `0x07` | RXCMD event counts for K/J/SE0/SE1, one saturating byte per step |
| `0x08` | Last RXCMD line state for each K/J/SE0/SE1 step, two bits per step |
| `0x09` | Valid-observation mask for the four self-test steps |
| `0x0a` | Expected sequence `K, J, SE0, SE1`, packed as `0xc6` |
| `0x0b` | Per-step GPIO input/output/OE snapshots, six bits per step (same layout as `0x04`) |
| `0x0c` | Terminal protocol receipt: snapshot-valid bit 0, failure reason bits 1–3, last active state bits 4–7, terminal state bits 8–11 |
| `0x0d` | Latched packet count at terminal state |
| `0x0e` | Latched ACK progress: receiver-live bit 0, ACK-confirm bit 1, ACK ticks bits 2–17 |
| `0x0f` | Latched WAIT_DP elapsed microseconds |
| `0x10` | Latched SOF elapsed microseconds |
| `0x11` | Latched SOF continuous-SE0 elapsed microseconds |
| `0x12` | Latched KEY position: bit index bits 0–7, bit phase bits 8–23 |
| `0x13` | Event ring metadata: next-write slot bits 0–4, saturated count bits 5–10, frozen bit 11 |
| `0x14` | Event ring timestamp clock in microseconds (32-bit, wraps after about 71 minutes) |
| `0x20`–`0x5f` | 32 event-ring entries, two read-only words per physical slot |
| `0x60` | Terminal Debug-read receipt: snapshot-valid bit 0, attempted bit 1, diagnostic read error bit 2 |
| `0x61` | Raw USB3343 Debug register `0x15`, zero if the read failed |
| `0x62` | Cached RXCMD snapshot: valid bit 0, line-state bits 1–2 |
| `0x63` | Age of cached RXCMD in 60 MHz USB clock cycles at diagnostic completion; saturates at `0xffffffff` |
| `0x64` | GPIO input/output/OE snapshot when the diagnostic read completes (same layout as `0x04`) |

Status register `0x03` packs state in bits 0–3, PHY ready/fault in bits 4–5,
the four-step self-test mask in bits 6–9, line-state-valid in bit 10, the
USB3343 line-state value in bits 11–12, disconnected-selftest mode in bit 13,
and CONTROL-to-TARGET-A power selection in bit 14. This is diagnostic telemetry
and is not a safety interlock or hardware acceptance result. All registers are
read-only. Status and live GPIO snapshots are captured in the USB clock domain.
Failure registers preserve the first self-test fault evidence after the pads
return high impedance. The expected sequence uses bit 0 = DP and bit 1 = DM;
register `0x08` packs step 0 into bits 0–1 and then ascends by two bits per
step. Register `0x07` similarly packs step 0 into bits 0–7. Register `0x0b`
packs each step's six-bit GPIO snapshot consecutively starting at bit 0. Self-test
failure reasons are 1 for RXCMD mismatch/timeout and 2 for loss of the drive
interlock. Register `0x0c` is a separate terminal protocol receipt: reason 1
means packet limit exhausted, 2 means WAIT_DP timeout, 3 means SOF timeout,
and 4 means the drive interlock was lost during KEY/GAP/WAIT_DP/SOF. The last
active state uses the existing state encoding (KEY=3, GAP=4, WAIT_DP=5,
SOF=6); terminal state is DONE=7 or FAULT=8. A zero protocol reason on a
self-test fault means the key protocol did not begin. The top captures these
read-only fields once on first DONE/FAULT observation in the USB domain; they
are diagnostic evidence, not a success signal or hardware acceptance result.

The protocol's finite attempt limit is 30,000 packets. With the current
16-bit word at 20 us per bit and 160 us release gap, the maximum packet train
is 30,000 × (16 × 20 + 160) us = 14.4 seconds, plus self-test and transition
time. The bound ends in fault without candidate ACK evidence; it is not a
success signal or an estimate of ROM acceptance.

On r1.4 these switches are active high; in particular, leaving
`target_c_vbus_en` high would enable the TARGET-C-to-TARGET-A path. It is always
set to zero here, even when CONTROL power is selected.

The prototype currently emits SOF by pulling D+ low through the onboard 1 kΩ
series resistor. Against the reported 1.5 kΩ ROM pull-up, an ideal divider
would leave about 1.32 V at the target side, above the USB full-speed single-
ended low maximum of 0.8 V. This is a source-derived concern, not a measured
result; post-ACK SOF acceptance is therefore unproven. The prototype does not
switch to PHY transmit mode.

The target PHY configuration, electrical assumptions, remaining review gates,
and offline verification limits are recorded in the task handoff. This
prototype is not an accepted recovery method or an installability claim.

The safe-PHY initializer applies the USB3343 register setup directly through
ULPI, including register `0x39` value `0x06` for the Cynthion r1.4 D+/D- trace
swap. It verifies this value by readback before exposing drive permission.
Generic USB3343 instances retain the register's `0x04` default profile unless
the board-specific r1.4 profile is explicitly selected. This follows the
platform's `ulpi_extra_registers` setting and Microchip USB334x datasheet
§7.1.3.5; it does not change the GPIO or RXCMD line-state bit order.

Layout v5 adds a 32-entry diagnostic ring that records only on a qualified
RXCMD line-state update or an FSM state transition. It is not a periodic
sampler. Each physical slot occupies two consecutive JTAG words beginning
at `0x20 + 2*slot`: word 0 is timestamp in microseconds; word 1 contains the
32-bit payload. Payload bits are state 0–3, RXCMD-update event flag 4 (zero
means state transition), line-state-valid 5, line state 6–7, GPIO
input/output/OE snapshot 8–13 (same layout as register `0x04`), key bit index
14–17, key phase in USB clock cycles 18–28, receiver-live flag 29, latched
candidate-ACK-confirm flag 30, and nonzero-ACK-progress flag 31. The timestamp
counts USB-domain microseconds from startup and wraps at 32 bits. Register
`0x13` gives next-write slot and saturated count; the oldest retained slot is
`(next_write - count) mod 32`, then walk forward modulo 32. When the FSM
reaches DONE or FAULT, the terminal transition is recorded and the ring
freezes. The recorder is passive and does not gate protocol outputs. The ring
is diagnostic evidence only; RXCMD events remain event-on-change reports and
must not be interpreted as continuous line sampling.

Layout v6 adds one read-only USB3343 Debug register `0x15` read after a
terminal `WAIT_DP` timeout. The ULPI transaction uses the existing register
window and a bounded timeout; it never writes PHY state or retries. `0x60`
reports completion and any diagnostic transaction error separately from the
PHY initialization fault in status register `0x03`. The raw `0x15` byte,
cached event-on-change RXCMD state, its age in 60 MHz USB clock cycles, and
the GPIO input/output/OE snapshot are latched when this diagnostic completes.
The age counter saturates rather than wraps. A failed diagnostic read leaves
the raw-value register at zero and still preserves the other captured fields.
The core remains in its terminal high-impedance state throughout; this receipt
is diagnostic evidence only and does not establish a ROM ACK or change any
keying decision.

## Separate power-monitor diagnostic

`power_monitor.py` builds a separate PAC1954 monitor image, with no USB_KEY core
or target data GPIOs. It enables CONTROL-to-TARGET-A power and leaves TARGET-C,
AUX and discharge off. At startup it writes channel-1 `NEG_PWR_FSR=0x4000`
(bipolar ±100 mV), sends `REFRESH_V`, waits 1 ms, and requires
`NEG_PWR_FSR_ACT=0x4000` before accepting measurements. This is necessary
because the board shunt polarity makes CONTROL-to-TARGET-A current negative at
PAC1954 VSENSE+ minus VSENSE−. It reports signed current: positive is
TARGET-A-to-CONTROL; negative is CONTROL-to-TARGET-A. Other channel/range bits
remain at their power-on defaults. The monitor does not test the FM1 CPU rail or
prove bootloader recovery. Both TARGET ports must be empty for a reviewed
volatile load; connect FM1 to TARGET A only after unloaded readback is accepted,
leaving TARGET C empty. Do not use the USB_KEY `LUNR` register table above for
this `PAC2` image.

After a separately reviewed load, capture read-only JSON lines with the Python
environment containing Apollo/Cynthion:

```sh
python -m tools.cynthion_usb_key.read_power_monitor --samples 10 --interval 1
```

The reader never builds, loads, changes power, or writes FPGA registers. It
requires magic `PAC2`, layout2, healthy ready/sample flags, expected PAC ID/range,
CONTROL-only power and sample age no more than250ms. Invalid readings preserve
raw evidence with `valid:false` and null conversions; the command exits nonzero
if any sweep is invalid. Up to120 sweeps are allowed, with0.125–10 seconds
between completed sweeps. Redirect JSONL to an ignored scratch path to retain
measurements during an explicitly announced FM1 switch test. Current conversion
uses the nominal20mOhm shunt and signed bipolar ±5A range; tiny no-load offsets
are not a calibration result. Register reads are sequential, `atomic:false`;
voltage and current may belong to different conversions, so no instantaneous
power is calculated. Raw age is sampled during the sweep, not at the later JSON
write.

Monitor layout2:1 magic,2 layout,3 PHY/PAC ready/fault plus PAC error and sample
presence,4 manufacturer plus active range,5 VBUS raw,6 signed-bipolar VSENSE
raw,7 sequence,8 age in60MHz cycles,9 refresh count,10 power controls. Details and unloaded
physical evidence: `notes/2026-10-16-cynthion-power-monitor.md`.
