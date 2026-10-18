# Cynthion / FM1 recovery review for Astra

Prepared 2026-10-18. Personal Lunar Modulator project. This is an evidence
packet, not an installable FM1 image or permission to operate hardware.
**Recovery has not succeeded. No valid FM1 USB identity is currently available.**

## Start here

1. Read this guide and [chronological bench notes](../../2026-10-18-cynthion-enumeration-capture.md).
2. Read the [repeat design/build/first attempt](../../2026-10-18-cynthion-pico-repeat.md),
   [staged preflight](../../2026-10-18-cynthion-staged-key-preflight.md), and
   [gateware operating contract](../../../tools/cynthion_usb_key/README.md).
3. Inspect the actual [protocol state machine](../../../tools/cynthion_usb_key/gateware.py),
   [physical integration](../../../tools/cynthion_usb_key/top.py), and
   [ULPI safe PHY](../../../gateware/ulpi_safe_phy.py).
4. Compare the raw read-only receipts and USB captures below against the claims.
5. Use [source-manifest.json](source-manifest.json) and
   [evidence-manifest.json](evidence-manifest.json) to check provenance.

The review base is `e0713b3db7dcbd03b75c1b720baa3d0f747b34a7` on
`feature/2026-10-11@installable-firmware`. This packet's commit is a descendant.
The authoritative current code is committed in the normal source tree; it is
not hidden in scratch. Source hashes are pinned in source-manifest.json.
Historical build outputs may use older source; use their own input-pins and
receipts rather than assuming current source generated every old bitstream.

## What happened and what is established

- [reported: owner, earlier firmware work] A smaller native Trio probe displayed
  correctly and produced audible notes with responsive keys and encoders.
  Later all-engine/song firmware was severely sluggish/distorted, including
  individual notes. This is a different acceptance result from recovery.
- [reported/verified in prior handoffs] USB/power was interrupted during earlier
  flashing. Subsequently the screen/power-button light remained dark. Charging
  indication still lights. The exact causal failure and CPU supply state are
  not established. Nothing here proves permanent hardware damage.
- [reported: owner, confirmed from videos] RIGHT is ON; LEFT is OFF. Early
  attempts switched RIGHT to LEFT under an incorrect/uncertain direction
  assumption. Those are not valid power-on recovery tests. Later named tests
  explicitly use LEFT/OFF to RIGHT/ON.
- [verified: source/simulation/routing] The custom GPIO key sequencer builds,
  satisfies the retained digital interlocks in simulation, and routed timing
  passes. Physical receipts report disconnected self-tests and terminal output
  release. These do not measure voltage/timing at the FM1 connector.
- [verified: bench kernel] Earlier attempts sometimes produced full-speed
  attach followed by descriptor/setup failures `-71`, including a direct
  connection bypassing Cynthion. They never yielded a valid ROM descriptor.
- [verified: latest run] The finite repeat ran to DONE with sixteen cycles,
  3,000 words in the final cycle, no reported PHY fault and both output enables
  zero. Owner reported steady red LED and connected TARGET C afterward.
  Bench saw no USB attach. A direct connection preserving power also produced
  no attach, and flipping only the FM1 USB-C plug did not change that.
- [verified: control] A Lenovo mouse enumerated directly, and eventually through
  the restored official analyzer at fixed Low speed after Packetry TARGET power
  was toggled. This validates that specific low-speed control, not all USB
  speeds or the FM1 cable/connector/electrical state.

## Latest exact repeating-key image

Source integration commit: `fef11263c88f4b79193ceff9b590094110124491`.
Profile: `pico-repeat --target-power-from-control`, Cynthion r1.4, layout 8.

Bitstream: [cynthion_usb_key.bit](evidence/coordinator/cynthion-pico-repeat-20261018/cynthion_usb_key.bit),
170,402 bytes, SHA-256
`8fcc78e502dc692cd6d0f8daeab01030c2ae815326e624879f95bb24b65cd28f`.
This is project-generated experimental gateware, not vendor FM1 firmware.
Do not load it merely to review this packet.

[Input source pins](evidence/coordinator/cynthion-pico-repeat-20261018/input-pins.json),
[root build review](evidence/coordinator/cynthion-pico-repeat-20261018/root-review.json),
[build runner](evidence/coordinator/cynthion-pico-repeat-20261018/root-build.py),
[routed timing](evidence/coordinator/cynthion-pico-repeat-20261018/cynthion_usb_key.tim),
[LPF](evidence/coordinator/cynthion-pico-repeat-20261018/cynthion_usb_key.lpf),
[compressed routed netlist](evidence/coordinator/cynthion-pico-repeat-20261018/cynthion_usb_key.json.gz).

Recorded Aeon container limits: 4 CPUs, 8 GiB memory and swap ceiling, 512 PIDs,
docker-batch.slice, network none, read-only root/inputs, no capabilities or
exposed devices, uid1003. Exit zero/no OOM. Routed clocks 67.29 MHz against
60 MHz and 194.93 MHz against 120 MHz. These are build receipts, not connector
waveform calibration. No new FPGA build was performed for this packet.

Two-stage USER interlock: disconnected four-line self-test, READY with outputs
released, then a fresh USER press after connection. The repeat emits sixteen
cycles of 3,000 `0x16ef` words, MSB first; D+ clock 10 us low/10 us high; released
160 us gap after each word; then 2 s of push-pull D+ at 1 kHz/50%, D- released.
Total 55.04 s. No ACK/SE0 early stop in this profile. DONE and FAULT are absorbing.
TARGET C must remain detached during driving. CONTROL supplies TARGET A in
this named profile. Existing GPIO series-resistor electrical limits remain.

The reference is [czietz's Pico example](https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5).
Our profile is deliberately finite and is not electrically or temporally proven
identical to MicroPython's loop. In particular, interpreter gaps, SPI deinit
behavior, idle D- and actual Pico waveform were not measured here.

## Latest physical receipt chain

Directory: [repeat evidence](evidence/coordinator/cynthion-pico-repeat-20261018/).
Times here are UTC on 2026-10-18; bench journal lines use Pacific local time.

| Receipt | Observation |
| --- | --- |
| retry-after-control-load.log | Supported volatile FPGA load completed; no persistent flash write |
| retry-after-control-safe.json |08:53:33–41 SAFE0, PHY ready, no fault, OEs 0, stable safety sweep |
| retry-after-control-preflight.json |08:54:13–21 READY9, four tests/mask15, OEs 0 |
| retry-after-control-connected.json |08:54:56–08:55:04 READY after FM1 connection; status/GPIO/terminal stable; event-ring metadata changed |
| retry-after-control-observation.json |08:55:26–34 activePWM6, five completed cycles; non-atomic observation |
| retry-after-control-terminal.json |08:56:14–23 DONE7, cycles 16, final words3000, terminal0x701, OEs 0, no fault, stable sweep |
| retry-after-control-host-connected.txt |08:57:02 host roots + KA6 only; no new USB attach |
| retry-after-control-direct.txt |08:57:47 direct FM1, still no USB attach |
| retry-after-control-direct-flipped.txt |08:58:25 FM1 plug 180 degree flip, still no USB attach |

The register reader is included as read_status.py. It checks layout/profile
before reading; it does not arm the sequencer. Sweeps are explicitly non-atomic.
The bounded 150 s kernel follower ended with timeout 124 as intended; no monitoring
process remains running. Hardware was left FM1 directly connected to bench01,
RIGHT/ON, Cynthion terminal DONE with outputs released. No loader/flash/MIDI
command was issued in these capture/retry steps.

## USB control and FM1 capture comparison

Directory: [enumeration captures and host logs](evidence/coordinator/cynthion-enumeration-capture-20261018/).
Raw PCAPNG files are retained byte-for-byte. Hashes/sizes are in the manifest.
[Independent capture summary](capture-summary.json) records block counts and
tshark descriptor results. All eleven files have valid PCAPNG block framing;
that does not establish completeness, valid USB packets or ROM acceptance.

| Capture | Result / important limit |
| --- | --- |
| attempt01-auto | Only events, no proven valid FM1 exchange |
| attempt02-full | Malformed/invalid PID records; not attributable valid FM1 responses |
| control01-reset-interrupted | Owner accidentally pressed Cynthion RESET; interrupted recording |
| control02-mouse-auto | Host descriptor/setup -71; mouse not enumerated |
| direct mouse hostlog | Lenovo 17ef:6019/HID recognized; port differed from failed path |
| control03-mouse-replacement | Known data replacement C cable still failed -71; identical host port not established |
| control04-cold-auto | After full Cynthion cable removal/reset, still -71; Packetry closed-channel error. Saved file has96 USB blocks despite GUI showing only 3 events |
| control05-low-flipped | Fixed Low plus TARGET C plug 180 degree flip still -71 |
| FPGA-offline hostlog | Mouse replug had no attach. Inconclusive: FPGA-controlled VBUS switches mean offline does not establish powered passthrough |
| control06-low-software-power-pass | Official analyzer restored; fixed Low and software TARGET power cycle; mouse17ef:6019/HID recognized and Packetry decoded descriptors |
| attempt03-full-after-mouse-pass | Capture began with mouse still attached at wrong decode speed; Packetry save failed;224 B/start-only file is INCOMPLETE |
| attempt04-full-software-power | Clean Full capture, USB power toggled;320 B/start and stop only, no USB packets. Battery means this was NOT a CPU reset |
| attempt05-full-physical-cycle | Owner physical OFF 5 sec→ON, no screen/light change;320 B/start and stop only, no USB attach on host |

Successful control06: 806876 B, SHA-256
`cc46944b45675ab9a104a7e9c788a26fb9a6583f7b82a1962f742e6aa67c1013`.
Independent tshark decoded 17ef:6019, EP0 max 8, at frames 91 and 209. The successful
combination does not isolate which action fixed the control path. No known
full-speed peripheral control has passed during this latest comparison.

Packetry save error in attempt03: `Failed to load segment width`; requested
range 0..1223 while stream length 1222; backtrace through StreamReader,
CompactIterator and ui::save_file. A clean subsequent capture saved successfully.
The failed export must never be treated as absence-of-packets evidence.

## Fresh offline verification for this review

[Full test output](current-tests.log). Command (existing test virtualenv with
installed Cynthion/Amaranth dependencies on PYTHONPATH):

```sh
python -m pytest -o addopts= -p no:cacheprovider \
  tests/test_ulpi_safe_phy.py \
  tests/test_cynthion_usb_key_gateware.py \
  tests/test_cynthion_usb_key_ack_gap_reset.py \
  tests/test_cynthion_usb_key_pico_repeat.py \
  tests/test_cynthion_usb_key_protocol_review.py \
  tests/test_cynthion_power_monitor.py \
  tests/test_cynthion_power_readout.py \
  tests/test_cynthion_target_usb_probe.py
```

**119 passed, 177 warnings, 20.65 s**, exit0. Warnings are retained in the log,
including Amaranth deprecations/UnusedElaboratable. This verifies digital
simulation/test expectations only. Earlier 117 combined result and 63 repeat-focused
result remain historical receipts, not claims that this packet reran routing.

## Other evidence and review questions

The packet includes earlierGPIO/ACK-duration reviews, D+/D- swap-register
follow-up, passive PAC current-monitor receipts and lamp control, staged-key
results, and the deeper Facedancer review. Historical recommendations can be
superseded; follow the dated notes and actual current code rather than treating
every old report as current truth.

Please independently evaluate:

1. Does exact current ULPI configuration and readback establish the intended
   non-driving PHY state, including USB3343 swap register0x39=0x06 and GPIO pad roles?
   Could analyzer restoration/PHY state explain control failures or key behavior?
2. Are disconnected self-tests exercising actual external USB line levels in a
   way that predicts loaded FM1 voltage? What do they fail to measure?
3. Is the GPIO through 1 kohm recoveryclock/data path electrically viable at the
   FM1 connector? Consider clamp/load behavior, thresholds, directions,
   idle levels, turnaround and ACK contention. No connector-level voltage is known.
4. Is the repeat waveform/protocol faithful enough to the Pico prior art?
   Audit clock polarity, bit order, timing, word gaps, push-pull PWM, D- idle and
   transition to host connection. Treat counters as schedule evidence only.
5. Could power/switch/battery/USB-Cconnection explain noattach? What minimal
   external measurement distinguishes CPU-not-running from a rejectedkey or
   USB line problem? Do not infer CPU rail health from charging LED/VBUS alone.
6. Is our USB capture interpretation warranted given low-speed-only control,
   wrong-speed mouse traffic, Packetry errors and non-atomic receipt sweeps?
7. Propose the smallest next experiment that changes a falsifiable hypothesis.
   Another identical retry without new evidence is not useful. No scope probing,
   opening the unit, gateware replacement or flashing is authorized by this
   review packet itself.

Facedancer/Moondancer research found maintained USB-device/endpoint/connect
controls, not an existing raw USB_KEY clock sequencer or host controller API.
See the retained source-linked research; this is a research finding, not a
proof that a custom PHY serial-mode implementation is impossible.

## Publication and completeness

The manifest accounts for 397 original files,394 exported. This includes all
available files under the coordinator's scratch/cynthion* trees and the one
primary-checkout Cynthion review. Device serial/UID, private home paths, LAN IPs
and unrelated FAT logs are removed from text copies; original hash and exported hash
are separate. Large generated text is deterministic gzip (mtime0). Current
project gateware `.bit` files and PCAPNG are unmodified. No vendor FM1 binary,
flash dump, SDK toolchain, credentials or account database is included.

Two whole-repository source.tar files are represented by their original hashes,
input pins and committed source rather than duplicated here. A copied full
third-party UBOOT document is omitted in favor of its retained upstream pin/link.
All three omissions are explicit in the manifest. Original private files remain
untouched. Relative scratch links inside historical notes may need mapping to
`evidence/coordinator/` or `evidence/primary/`; directory names are preserved.

No firmware release, recovery, restore, hardware audio acceptance, full CI or
main merge success is implied. This packet is intended to enable an independent
review of what actually happened and what must be measured next.

No screenshot image was saved for the latest Packetry GUI error; its text and
backtrace were observed through computer use and transcribed above. Do not
interpret that transcription as an independently captured application log.
Installed control-tool versions in the retained receipt: Cynthion 0.2.5, Apollo
1.1.1, Python 3.12.14. The six final repeat input source hashes match the current
committed files byte-for-byte.

Machine-generated evidence retains its original whitespace. The local
.gitattributes marks that archive as generated and disables whitespace warnings
for those evidence copies only; source and review prose retain normal checks.
SHA256SUMS covers every packet file except itself.
