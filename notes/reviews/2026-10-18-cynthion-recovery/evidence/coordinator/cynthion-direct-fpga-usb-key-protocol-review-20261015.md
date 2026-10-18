# Cynthion direct-FPGA USB_KEY protocol review

Base reviewed: integration checkout `/Users/REDACTED/.codex/worktrees/installable-firmware/mvave-fm1-firmware`, `4ab06ff15fe99865b4ec379c562b465fc28e5eec`. Offline source review only. No device, gateware build, USB, PHY, or electrical operation/research.

## Source facts and model boundary

- `dongle/sim/jieli_rom.py:9-24,40-68` models the key receiver sampling rising edges, asserts a 1.5 ms ACK in the example configuration, then transitions directly to SOF measurement. The ROM behavior is reported from related JieLi material, not observed on AC791N (`docs/10-usb-key-dongle.md:76-110,532-534`).
- `dongle/sim/dongle.py:68-96` samples ACK only in released inter-packet gaps, requiring both resolved lines low for at least 100 us (`dongle/firmware/config.h:22-27`). The RP2040 dongle has switchable 2.2 kΩ pull-ups (`config.h:8-9`; docs/10 §2 E3). `dongle/sim/cosim.py:7-9` resolves released lines as low when no modeled pull-up exists, reflecting the documented 15 kΩ target pulldowns.
- The model's “no false ACK with absent/unpowered target” check is for its specific pull-up/line model and dongle (`docs/10-usb-key-dongle.md:520-530`). It does not establish that a direct FPGA reader can distinguish ROM ACK from the target's pulled-low idle bus.
- Under the assigned direct-FPGA topology, the 1 kΩ series resistors limit drive but do not bias released lines. With no strong external pull-ups, GPIO high-Z on both lines reads the same low state during idle and during the ROM's both-low ACK. Therefore the RP2040 rule “both low for 100 us” cannot be ported as an ACK detector. It would be a false-ACK condition by construction.

## Blind key-then-SOF versus a safe transition

A fixed finite 50 kHz key burst followed by fake SOF is an open-loop guess. The ROM may accept any packet in the burst; after acceptance, the ROM reportedly holds ACK low for 1–2 ms, then starts a PLL window expecting four consistent ~1 ms D+ falling-edge periods. If key traffic continues during that interval it supplies 50 kHz transitions; if the burst ends at a fixed time, the first SOF pulse train may begin before or after the unknown ROM window. The ROM retry count is family-dependent and unknown for WL82. Thus a finite blind schedule can miss the listening window or its first calibration attempt, and there is no source evidence that the next retry is guaranteed. A long fixed key interval followed by a finite fake-SOF period does not provide an observable proof of calibration or readiness.

A protocol-aware alternative is to keep ACK-low detection disabled while lines are released, transmit the documented 0x16EF MSB-first at ~50 kHz, and look for the ROM's *post-ACK D+ pull-up* after the key outputs are released. The reported sequence says D+ is pulled up after the 1–2 ms ACK and used for SOF calibration (`docs/10-usb-key-dongle.md:94-110`). Since the reported pre-key target pulldown holds released D+ low, a D+ low-to-high transition observed while the FPGA is high-Z is a distinct candidate indication of ACK completion/calibration start; it does not require interpreting both-low. This is an inference from reported ROM behavior and the stated topology, not validated Cynthion/ROM behavior. Gateware needs a target-side input/line-state path that can actually observe that transition, a bounded timeout, and high-Z fail-safe; do not infer success from elapsed time alone.

Once that rise is observed, stop key drive and supply only the documented SOF stand-in: D+ low for 4 us once per 1 ms, leave D− floating, and wait for D+ to remain low as the ROM releases its pull-up after calibration (`dongle/firmware/usb_key.pio`, `config.h:29-36`, docs/10 §1 item 6). Use a bounded phase timeout, then return all lines high-Z and surface failure. Separate “ACK complete / D+ pull-up observed,” “SOF train sent,” “ROM pull-up released,” and “host enumerated UBOOT” as distinct states/evidence.

## Direct-FPGA constraints/checklist for installer evidence contract

1. Use the direct side's actual line-level feedback; do not reuse cosim's `both low >=100 us` ACK detector without adding an independently valid idle-high bias/reference. With the assigned no-strong-pull-up condition, both-low is ambiguous.
2. Confirm by code/waveform reasoning that the key sequence drives every required D+/D− high/low combination for `0x16EF`, MSB-first, 50 kHz, with correct rising-edge sample and setup time. Open-drain release alone cannot guarantee high against the target pulldowns in this topology; any push-pull high/low state must honor the 1 kΩ series isolation and parent-owned hardware boundary.
3. After each packet/gap, release outputs before sampling. Candidate ACK-complete evidence is D+ rising due to ROM's reported post-ACK 1.5 kΩ pull-up, not both lines low. Verify no FPGA/PHY pull-down masks that edge. Require the line to remain high for a documented debounce interval; the exact value remains unselected.
4. On D+ rising, cease keying and begin only 4 us-low/1 ms D+ SOF pulses, D− high-Z. Do not run 50 kHz key edges concurrently with the PLL-measurement window.
5. Detect ROM pull-up release separately as calibration completion. If it does not happen before bounded timeout, switch outputs high-Z and report failure. Do not assert success merely because a finite key/SOF timer elapsed.
6. Keep a final acceptance gate for observed `UBOOT1.00` host enumeration; it is separate from an inferred ACK edge or ROM calibration signal.
7. Update/extend the offline model only to represent the actual direct-FPGA sensing strategy and absence of strong pullups; current dongle/cosim unit tests remain evidence for the RP2040 dongle design, not this interface.

No source files were changed. This is a protocol review, not a PHY/electrical sign-off or authorization to run a device trial.
