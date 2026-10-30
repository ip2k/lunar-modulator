# FM-1 back to stock V15 with FM-1-transporter on a Pico 2 W — 2026-10-26

## State

[verified: `feature/2026-10-11@installable-firmware`,
`notes/2026-10-18-fm1-interrupted-write-forensics.md`] On 2026-10-15 a stage-7
install through a RAM loader stopped at program `0x94600`; power was then
lost. Logged mutations cover `0x5000`–`0x94600` only; `0x0`–`0x4000`
(header, SPL) was never erased or written. The unit has shown no display and
no USB since. The Cynthion USB_KEY trials of 2026-10-15..18 did not reach ROM
entry.

## Owner decisions, 2026-10-26

- Goal: stock firmware booting again. Restoring the unit's own backup is not
  required.
- Use FM-1-transporter's wiring as its author designed it: Pico GP0 → D+,
  GP1 → D−, GND → GND, no VBUS, push-pull with no series resistors. This is an
  owner exception to docs/10 E1/E2 (open-drain key, series resistors), limited
  to this recovery.
- The owner has a USB breakout/cut cable and a charged battery. There are no
  15 kΩ pull-downs; try without them first (RP2350 E9).

## Method

- FM-1-transporter `a7fb5e8` (MIT), built on aeon in `ubuntu:24.04` with
  pico-sdk 2.2.0 and `PICO_BOARD=pico2_w`. The unpatched upstream UF2 has SHA-256 `c6f45e3c…3654`
  and is kept privately in `scratch/fm1t-pico2w-20261026/`. Pico 2 is listed
  upstream as "builds, untested"; the upstream hardware results are from a
  XIAO RP2040 [reported].
- Loader commands sent: ROM `FB06`/`FD07`/`FB08`, then loader `FB01`/`FB04`/
  `FD05`/`FC09`/`FC0A`/`FC14`/`FC0C` [verified: `src/jieli_uboot.c`]. There is
  no `FC12` and no `0xA1`. The firmware refuses writes outside
  `[0x4000, 0x93000)`. The loader is kagaimiq's `wl82loader.bin` (24064 B),
  uploaded to RAM only.
- The upstream `write` imports `fm-1-research-lab`, which is private. A local
  stand-in (`scratch/fm1t-pico2w-20261026/research-shim/tools/`) accepts only
  the stock V15 package (SHA-256 `db1642b2…db8a`). It takes the type-0 flash
  image as `0x93000` bytes at file offset `0x414`. That image's `0x0`–`0x4000`
  equals the archived FM-1_092 dump of this unit [verified], so the SPL is
  unchanged.
- Sectors `0x93000`–`0x94600` still hold bytes from the interrupted install.
  In V15 they are VM (`0x93000`, size `0x56000`), which V15 reformats when it
  finds it invalid, as on any rollback from FM-1+VA [inferred].

## Results

- 13:3x (bench01 local): the Pico 2 W enumerates as
  `2e8a:000a` "FM-1 Transporter"; console is `-if00`, data `-if02` under
  `/dev/serial/by-id/` (the ACM numbers move after each `rekey`).
- Unpatched upstream firmware, three runs [verified: the console log on
  bench01, kept privately]:
  - FM-1 **on** (it was on, not off as first thought): "D+ high in gap" after
    1 packet, then 6 s of pulses, host started, `USBH Device Attach` followed
    by `DEVICE REMOVED` about 1 s later. Something on the FM-1 does pull D+ up
    while it is on; what it is, and why it drops, is not known.
  - FM-1 **off**: "D+ high in gap" after 28 packets (about 14 ms), "early D+
    blip at 0.3 ms", D+ = 0 at the 6 s timeout, then a handoff anyway. This is a
    false trigger: no ROM pull-up was ever there. Either the RP2350 E9 pad
    erratum or charge left by the key clock on the unpowered FM-1 [inferred;
    not separated].
- So upstream on a Pico 2 hands off within milliseconds of the first key
  packets and stops keying before the FM-1 is switched on. Patch on a local
  branch `fix/2026-10-26@rp2350-false-ack` of the transporter clone:
  - D+ is sampled after a 1 µs drive-low and a 2 µs release (a real 1.5 kΩ
    pull-up recovers, a stale level does not).
  - The pulse phase returns to keying if D+ is low for 50 ms before 1 s, or
    low at the 6 s timeout.
  - This is a candidate for upstream (Pico 2 is "builds, untested" there).
- An Opus review of the first patch found that a 50 ms "D+ low" rule could
  reject a real entry. Upstream's own success log shows the ROM dropping D+
  at 7.3 ms (`docs/logs/m0_success_2026-10-01.log:37`). The flashed build
  (UF2 SHA-256 `4f5fab3f…f482`) does three things instead:
  - The key program drives D+ low for one cycle before releasing it
    (`nop side 0`), which removes the E9 float at its source.
  - D+ highs are counted passively and confirmed by one drive-low probe.
  - The pulse phase re-keys only if D+ has been low for ≥ 1 s at the 6 s
    timeout.
- With that build and the FM-1 off, the key ran steadily (28,630 packets in
  14 s, no handoff). The owner switched the FM-1 on at about 13:52, and it
  enumerated as `WL82 UBOOT1.00` and answered INQUIRY [verified: console log].
- `info` returned `key=980F type=3 id=856014` [verified].
- Two full reads, `dumpA`/`dumpB-20261026.bin`, are identical, SHA-256
  `3fdaaebd…b270` [verified]. Against the archived 092 dump, `0x0`–`0x4000`
  equals both 092 and V15, and `0x4000`–`0xD7000` differs.
- The `write` dry run passed: a fresh read equalled `--ref`, with 143 sectors
  queued (`0x4000`–`0x92000`).
- `write --write`: 143/143 sectors OK, and the final full read "EQUALS the
  expected image". An independent `dumpC-after-v15.bin` has
  `[0, 0x93000)` == the V15 flash image [verified].
- Dumps and the write log are kept privately in
  `scratch/fm1t-pico2w-20261026/dumps/`.
- Boot check: the owner power-cycled the FM-1 with the transporter
  disconnected, and it boots stock V15 [reported: owner, 2026-10-26]. With its USB
  plugged into the Pico's host port by mistake, it enumerated there as an
  ordinary device for ~146 s. The transporter sends no soft key unless told
  to (console `k` or `fm1t uboot`), and neither was sent [verified:
  `src/pio_host.c`, console log].
- Identity, sent from bench01 with `tools/fm1_identify.sh` (`amidi`, the
  read-only query `F0 00 32 45 00 00 00 40 7F F7` only), with USB `4c4a:c755`
  "FM-1": the reply is `F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 4C 1A 00…
  00 20 06 F7` (41 bytes), which `tools/fm1_identify.py --decode-file` decodes as
  **`FM-1_015`** with a valid checksum [verified]. This is the first hardware run of
  `fm1_identify.sh`, and it worked.
- **Outcome:** the unit is back on stock V15. It no longer holds FM-1+VA
  (`FM-1_092`); the 092 backups remain the only copy of that state.

## Follow-ups

- The transporter patch (`fix/2026-10-26@rp2350-false-ack` in the
  `reference/FM-1-transporter` clone; diff kept privately as
  `scratch/fm1t-pico2w-20261026/rp2350-false-ack.diff`) is a candidate
  upstream fix for Pico 2 support. Proposing it follows the
  `oss-contributions` rules and needs the owner's sign-off.
- The review's untested items:
  - how long the ROM's 7.3 ms D+ drop lasts;
  - whether the ROM counts the single probe edge;
  - an IE-toggle E9 probe as an edge-free alternative.
- CLAUDE.md now records `FM-1_015` (this branch). The procedure is written up
  as docs/17, with the cable used and `tools/fm1-transporter/build.sh`, which
  rebuilds the flashed pico2_w UF2 byte for byte [verified on aeon,
  2026-10-26].
