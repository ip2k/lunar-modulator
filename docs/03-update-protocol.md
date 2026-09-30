# 03 — The update protocol and its version gate

Everything here is **[reported]**: aroum reverse-engineered the macOS updater
binary; AL-255 captured the Windows updater under Wine with ALSA sequencer
logging, decompiled its worker, disassembled the on-device loader, and
byte-verified the framing (48/48 captured packets). AL-255's
[`docs/io/11-ota-protocol.md`](https://github.com/AL-255/FM-1-RE/blob/main/docs/io/11-ota-protocol.md)
is the authoritative reference; this is a summary with the parts that matter
for an open firmware.

## 1. Transport

Everything runs over **USB-MIDI System Exclusive** while the stock application
is running; there is no DFU, CDC or HID traffic. The device pulls the image from
the host with read requests, the host only answers.

| Mode | VID:PID | Name |
| --- | --- | --- |
| normal | `4C4A:C755` | "FM-1 Midi" composite (USB-MIDI + UAC1) |
| OTA loader | `4D4A:4155` | "ota-FM-1" composite (USB-MIDI, unused HID) |

The MIDI port *names* a host shows differ by OS [reported: Baud Girl,
measured 2026-09-25/26]. On Windows the synth is `FM-1 Midi` and the loader
`USB-Midi`. In Chrome on macOS both are `USB Composite Device`, so the name
cannot tell the two modes apart; the identity reply can (`FM-1` vs
`ota-FM-1`). Each mode change re-enumerates in about 6 s. Bluetooth MIDI ports
also appear and must be skipped, because updates run over USB only.

## 2. Session flow

1. **Identity query** host→device: `F0 00 32 45 00 00 00 40 7F F7`
   (manufacturer/device header `00 32 45`, address `00 00 00`, item `0x40`,
   command `0x7F` = get). Fuzzing all item ids showed the device answers
   **only** item `0x40` (aroum).
2. **Identity reply** 41 bytes **[verified 2026-09-06 on `FM-1_015`]**:
   `F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 4C 1A 00×21 20 06 F7`.
   Everything between `F0` and `F7`, the `00 32 45 58` header included, is the
   7-bit LSB-first packing of a 34-byte JieLi ID block
   `00 59 11 | len 27 | "FM-1_015" + zero padding | checksum` (the header
   unpacks to exactly `00 59 11`; checksum = `~sum(body) & 0xFF`). The plain
   field carries the whole `MODEL_NNN` identity. The second-field derivation in
   AL-255's mirror of the updater's parser (bytes 14–33 plus ASCII `0`) yields
   version 0 on this real reply, so parse the plain field;
   `tools/fm1_identify.py` does.
3. **Upgrade command** host→device, identical for both steps: `F0 22 24 35 7F F7`.
4. **Step 1 — verification.** The running app pulls parts of the package with
   read requests, checks them, writes a boot record (`FM-1_0xx` + `ota-`, a
   JieLi `UPDATA_PARM`), and soft-resets into the OTA loader, which
   re-enumerates as `4D4A:4155`. The host waits 2000 ms after the command,
   answers requests with an 8000 ms receive timeout, and treats a request for
   raw address `0xE0000000` (length 8, answered with `"success\0"`) as
   "verification complete", then keeps the port open 3000 ms.
5. **Step 2 — upgrade.** Identity query and upgrade command again; the loader
   pulls the UFW header, the entry list (descending) and the bulk data
   (ascending), erases and writes the **single** application layout, verifies
   the flash, updates loader metadata, then requests `0xF0000000` (length 8)
   and expects `"success\0"`. It then records the result and resets. The loader
   tries the finish handshake at most four times and returns zero even if all
   four fail (AL-255).
6. **Post-reboot**: the host must re-query the identity and compare model and
   version; the `0xF0000000` acknowledgement proves the loader reached the
   post-write path, not that the new image boots.

## 3. Read-request / response framing

**Corrected by Echomatter (AL-255 PR #2, 2026-09-04, verified on hardware):**
the whole message is one 7-bit LSB-first bitstream between `F0` and `F7`,
built as `00 59 30 | body_len:u24 | flashtype:u8 | addr:u32 | length:u24 |
data | checksum`, with `body_len = 8` for requests and `length + 8` for
responses and `checksum = ~sum(flashtype … data) & 0xFF`. The device requires
`body_len + 7 == decoded length` before dispatching. The fixed `00 32 41 41`
prefix below is what that stream happens to look like for aligned 512-byte
blocks; for the final partial block (481 bytes) it encodes the wrong length and
the device silently drops the reply, which is what had blocked their recovery.

```
device → host   F0 00 32 41 41 [f1:4][addr:4][len:4] F7
host → device   F0 00 32 41 41 [f1:4][addr:4][len:4] [pack7(data + chk)] F7
```

- `f1`, `addr`, `len` are little-endian u32 sent as 4×7-bit groups
  (`b0 | b1<<7 | b2<<14 | b3<<21`).
- `len` = `(length << 4) | flashtype`; requests carry `f1 = 0`, responses
  carry `f1 = length >> 4`.
- Data is an 8→7-bit **LSB-first continuous bitstream** (7 wire bytes per 8
  data bytes), holding `length + 1` bytes: the data plus one checksum byte
  `chk = ~(flashtype + sum(data) + sum(addr_le4) + sum(length_le3)) & 0xFF`.
- Requests address a *logical* image: the first 960 file bytes are 20 blocks of
  `0x30` bytes each carrying `0x2F` payload bytes plus a marker; strip the
  markers and append the rest of the file.

Final acknowledgements use channel header `00 32 41 01`.

## 4. The "syscmd" device-control family (normal mode, separate from OTA)

Framing `[00 59][cmd:1][len:3 LE][payload][~sum(payload)]`, dispatched by
`update_cmd_dispatch` with a 32-entry table (V13 `0x02026BC4`, V14
`0x0202730E`) and a transport selector (0 = USB-MIDI unpacked path, 1 =
Bluetooth event `0x72`):

| cmd | behaviour |
| --- | --- |
| 17 / 18 | return fixed 27-byte / 13-byte records |
| 21 | drain the common ring buffer |
| 33–36 | call methods on one of eight callback objects (control / write / read / status shapes) — **object table population unknown** |
| 48 | complete an armed transfer after token and length match — **copies memory** |
| others | no-ops |

AL-255's rule, adopted here: **do not send commands 33–36 or 48** to the only
recoverable device until the callback table's population is understood.

## 5. The step-1 gate: what it blocks and what it does not

AL-255 built structurally valid packages (`tools/build_fwsc.py`, valid CRCs,
correct JLFS entries) and probed the step-1 verifier on hardware
(2026-07-21). Findings:

- The verifier refuses a package it judges a "no-op" against what is installed.
  The first gate compares the incoming `cfg` entry header with the stored one;
  flipping one padding byte in a nested entry name (changing the CRCs, not the
  payload) got past it — the device went from 9 to 49 read requests.
- The next stage loads `ota.bin` to the loader flash area as plaintext (up to
  **19456 bytes**; larger payloads are truncated), the payload CRC passes, and
  then a result handler still takes the error path because a notify byte
  (`b[0x1C0E670+60]`) is left non-zero by an obfuscated check. Everything
  obvious has been ruled out as the compared quantity: loader CRCs, entry
  names, compressed and decompressed loader bytes, UFW header fields, the
  `FM-1_0xx` string, build strings. A genuine `FM-1_014` package with a
  *different application but the same loader* passes, so the check is not a
  simple loader compare.
- Stock packages work both ways: the bundled updater log shows an FM-1 on
  version 10 downgrading to `FM-1_008` successfully.
- **A rebuilt package with a bumped version identity is accepted [reported:
  Echomatter, AL-255 PR #2, 2026-09-04].** They derived a package from stock
  V15, changed its identity to `FM-1_016` (keeping V15's identity checksum,
  which shows the ID block is a literal in the image), and the stock updater
  installed it; the modified build ran with a broken USB configuration
  descriptor and was rolled back to stock V15 over USB-MIDI with AL-255's
  client once its partial-block framing was fixed. So the "no-op" gate is
  version-based host/verifier policy, not a device fuse, and a running
  application with a live update service can always be overwritten by a
  stock package. This is not recovery for an application that does not run.
- **The "no-op" gate is a same-version refusal [reported: Baud Girl, measured
  on hardware 2026-09-25].** `FM-1_079` sent to a synth running `FM-1_079`
  stops after 9 step-1 requests without verification. So does a `FM-1_079`
  that differs only by a CRC-neutral table patch. `FM-1_078` ↔ `FM-1_079`
  install both ways. Whether the device compares the version string or the
  file list is not known. This matches AL-255's 9-request refusals and
  Echomatter's bump. Since then Baud Girl has shipped `FM-1_020` … `FM-1_092`
  through this path, with public installs and rollbacks to V15 (docs/04,
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`). **Content is not
  authenticated; a rebuilt package with a new version number installs.**
- **The OTA loader can rewrite the flash head [reported: Baud Girl FINDINGS
  5.4].** That head is `uboot.boot` plus `isd_config.ini`, `flash.bin`'s first
  16 KB, which is file bytes `[0x414, 0x4414)` of a V15 `.fwsc`. Baud Girl's
  installer refuses any package whose head differs from V15's by SHA-256.
  Keeping the head byte-identical (docs/07 §4 rule 2) is therefore a
  bootloader-safety rule, not just caution.
- **An interrupted step 2 is resumable [reported: Baud Girl].** A synth left in
  its loader after step 1 stays there across power cycles, answers the
  identity query as `ota-FM-1`, and accepts the upgrade command again. Some
  units confirm step 1 but never restart into the loader; nothing is written
  then, and the cause is unknown.
- Therefore the stock update path is a working **install** path for non-stock
  applications. It is **not a recovery mechanism**: it has no way to help a
  device whose application no longer boots or no longer runs the update
  service.

- **Stock packages change the layout.** V15 shrinks the app area by 0x1000 and
  grows VM (docs/01 §2) while keeping `uboot.boot`, `ota.bin`, `cfg` and
  `isd_config.ini` byte-identical to V14 [verified]; since V15 ships through
  the stock path, a partition-boundary change by itself is not what the
  verifier rejects [inferred].

Two ways forward, both in docs/07 and docs/08: explain the check (with a
recoverable device you can iterate freely, patch the verifier in the image, or
read the notify code), or bypass the stock path entirely by flashing through
the mask-ROM USB mode.

## 6. Tools

| Tool | Author | Status |
| --- | --- | --- |
| `tools/fm1_ota.py` (`scan`, `flash`) + `alsalib.py`/`alsaseq.py` + `99-jieli-fm1.rules` | AL-255 | byte-exact reimplementation of the client, 14 offline tests; post-2026-08 timing changes **not yet exercised on hardware** |
| `fm1_flasher.py`, `fm1_sysex_scanner.py` | aroum | derived from the macOS updater; **never tested on hardware** |
| `M-UPGRADE-FM1` (macOS/Windows) | M-VAVE | the stock, proven path; embeds one firmware version |
| `scripts/extract_ota_loader.py`, `tools/build_fwsc.py` (branch `with-custom-firmware`) | AL-255 | package inspection and (experimental) building |
| [FM-1+VA installer](https://baudgirl.com/work/FM-1+VA/install) (Web MIDI, Chrome/Edge) | Baud Girl | a port of AL-255's `fm1_ota.py` with three fixes, a V15 head-region gate, a same-version check and resume-from-loader; used for public installs since 2026-09-26; source readable on the page, no license stated |

Note for Linux hosts: ALSA raw MIDI is unusable while any sequencer client is
subscribed, and PipeWire grabs MIDI inputs; use the sequencer interface (what
RtMidi and M-UPGRADE use) or stop PipeWire's MIDI bridge for the session.
