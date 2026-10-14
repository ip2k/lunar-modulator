# RAM-streaming WebMIDI bootstrap feasibility — 2026-10-14

## Finding

[verified] A full expanded application does not need to fit in on-chip RAM to
install over WebMIDI. The pinned Felucca/Dinghy update loader is an existing
streaming design: the stock SPL decompresses a loader into RAM at
`0x01C0A800`; the linker reserves at most `0x14000` (80 KiB) for the complete
loader image and BSS (`reference/dinghy/firmware/loader/loader.ld:1-20`,
`crt0_ldr.S:1-12`). The loader polls USB-MIDI, fetches a UFW image in 512-byte
M-UPGRADE reads, buffers one 4 KiB sector, and erases/programs/verifies that
sector before moving on (`loader.c:3-8,29-32,58-75`, `ldr_core.c:108-180`,
`firmware/third_party/dinghy/src/ota.c:147-207`). This avoids buffering an
862 KiB application in Lunar's 432 KiB application arena. The app's separate
24 KiB `.ram_text` is only a RAM flash-driver region; its XIP code cannot
continue executing while the flash is unavailable (`firmware/native/app.ld:8-9,29-34`).

The transfer and write behavior has useful safety properties already present
in this maintained GPL-3.0-only implementation: chip-key/package check before
app erases, only the configured app interval is written, each changed sector
is read back, the entire image CRC is checked, and the host must return
`0xF0000000` success before the loader drops its persistent update record.
Interrupted writes retain that record and re-enter the loader after power loss;
the next pass skips sectors that already match (`ldr_core.c:12-18,91-106,117-180`,
`loader.c:80-115`). These are source-level design properties, not FM-1
installation or recovery acceptance.

## Exact compatibility blockers

The existing loader is not safe to deploy unchanged for the approved recorded
FM-1_092 expanded layout:

- Its application end is hard-coded to `0x93000`; it rejects a shorter image
  and never writes the expanded app/profile records through `0xD9000`
  (`ldr_core.c:31-33,117-166`; `loader.c:19-20`). A compatible variant would
  need a new authenticated profile-bound high limit of `0xD9000`, exact
  geometry/package correspondence, and write ordering that keeps the
  application directory sector last. The offline geometry helper currently
  records `[0x04000,0xD9000)` as the app/PRCT area and preserves everything
  after it (`notes/2026-10-14-expanded-storage-ownership-review.md:21-45`,
  `tools/jieli/expanded_flash_profile.py:12-28,44-58`).
- More critically, Dinghy stages the RAM loader and its persistent resume
  record in `[0xE0000,0xE5000)` (`firmware/third_party/dinghy/src/ota.c:24-25,308-371`).
  The exact 092 profile identifies `[0xD9000,0xE9000)` as the VM bank, so
  that staging range would overwrite preserved VM data. It cannot be called
  a safe bootstrap route without a separately proven, recoverable staging
  allocation and migration plan (`notes/2026-10-14-expanded-storage-ownership-review.md:37-45`).
- Loader completion scans and may erase valid update-record sectors throughout
  `[0x93000,0xFC000)` (`ldr_core.c:32-33,91-101`). That broad interval overlaps
  the 092 profile's VM, BTIF and USR reservations. A new variant must resolve
  the exact SPL record locations/format and clear only records it owns; simply
  moving the app high-water mark is unsafe. The 092 profile marks VM
  `[0xD9000,0xE9000)`, BTIF `[0xE9000,0xEA000)`, and USR `[0xEA000,0xFC000)`
  as preserved (`notes/2026-10-14-expanded-storage-ownership-review.md:37-45`).
- USB is polled with interrupts off: the loader calls `usb_poll()` about every
  500 microseconds (`loader.c:29-32,80-99`), and its flash erase can hold the
  poll loop for up to 500 ms (`fm1_flash.h:166-181`). M-UPGRADE waits up to
  three five-second windows per 512-byte request and imposes a 120-second
  session deadline (`ota.c:147-175,350-351`). The timings look bounded on
  paper, but the browser adapter still needs fake-transport timeout/sequence
  tests and a later physical throughput/timeout gate. Do not assume USB
  back-pressure or browser send completion during erase.

The upstream source is the pinned local reference at
`reference/dinghy` commit `d44df7db09b98ccad2f1233b8f83f5f09c04829e`;
tracked adaptation provenance is `firmware/third_party/dinghy/UPSTREAM.md`.
The loader is GPL-3.0-only. Any derivative belongs in that isolated GPL profile
with notices retained; the project instructions prohibit distributing a
firmware binary linked with the closed JieLi SDK libraries. No firmware source,
package, staging record, device, USB port, or flash was changed in this review.

## Recommended next implementation boundary

First resolve storage ownership and SPL mechanics; do not start by widening
`LDR_APP_HI`. Inspect the exact boot-record scan semantics and prove a
recoverable loader staging extent that does not overlap the current device's
VM/BTIF/USR/key data, with an export/migration/rollback plan for any data it
reuses. If no safe staging extent exists, the proposed stock-OTA bootstrap is
blocked for the preserved 092 profile and needs a different owner-approved
bootstrap mechanism.

Once those inputs are proven, the smallest prototype is an offline, private
GPL loader variant that takes a fixed profile identity and explicit extent
constants (not caller-provided addresses), uses the existing bounded 512-byte
pull/4 KiB sector loop, writes only `[0x04000,0xD9000)`, verifies package and
per-sector bytes, writes directory metadata last, and clears only its own
update record. Add host-side synthetic UFW fixtures for extent, key, CRC,
sector-order, interruption/resume and foreign-profile rejection before any
hardware phase. Keep package admission and physical writer disabled until the
owner's current-device backup, storage migration, rollback and boot-recovery
gates are separately satisfied. Browser MIDI remains the preferred delivery
surface if the safe bootstrap/staging prerequisite can be met; a native
companion is not substituted by this note.

## Inspection limits

Serena selected the authoritative worktree and the inspected symbols matched
the source excerpts above. Rarefaction remained selected on the primary
checkout and rejected this worktree as outside its configured root; no shared
semantic-server root was redirected. This is a bounded source/geometry review:
there was no loader link/map measurement, browser-session test, fresh physical
flash read, SPL experiment, device command, or hardware operation.
