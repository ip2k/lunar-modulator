# Changelog

All notable changes to this project are recorded here, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The project
has no releases yet; work before this file existed (research phase, bench
session 1, the `USB_KEY` dongle, the 2026-09-08 desk review) is in the git
history.

## [Unreleased]

### Added
- docs/11: feasibility of a Schwung-style plugin platform on the FM-1. It
  covers which Schwung modules could compile through a shim, why Mutable
  Instruments' MIT code is the best engine source (with the RAM, flash and
  porting steps per engine), a staged loader design modelled on logue, OWL,
  disting NT and CTAG TBD, licence constraints, and a desk-then-bench plan.
- Baud Girl's FM-1+VA, the first third-party FM-1 firmware that users install
  from a browser, is recorded as prior art: what it is, how it installs, and
  what it settles about the stock update path (docs/04,
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`).
- A byte-level comparison of Baud Girl's `FM-1_092` package with M-VAVE's
  V15. It is V15's application with 90 small patches and 110 KB of new code
  appended, and the settings (VM) partition is moved to make room. The
  bootloader, OTA loader and configuration are untouched.
- The owner's unit now runs FM-1+VA (identifies as `FM-1_092`); the status
  lines say so.
- Photos of the owner's opened unit and the evidence crops, in
  `photos/2026-09-29/`.
- Observations from photos of the owner's opened unit: SoC lot marking
  `C188612-11B8`, board batch `260708`, the MIDI IN photocoupler, an
  unidentified `SLS316D` part, and the knob layout matched to the control
  names in Baud Girl's manual.

### Changed
- docs/06 and docs/08: the FM-1 has four free parameter knobs, not eight, so
  a Movy-style page becomes two pages of four. The roadmap gains the engine
  platform.
- The identity reply's checksum is not reliable on modified firmware:
  FM-1+VA keeps V15's checksum byte, so parse the version and do not gate on
  the checksum (docs/03).
- The stock update gate is now described as a same-version refusal with
  unauthenticated content, and the docs say the stock path installs non-stock
  firmware routinely; it is still not a recovery path (docs/03, 05, 07, 08,
  README, HANDOFF).
- New risk recorded: the OTA loader can rewrite the flash head (`uboot.boot`,
  `isd_config.ini`), so any package must keep that region byte-identical to
  V15 (docs/07).

### Fixed
- The "unpopulated 3-pin header" (candidate UART) from the 2026-09-08 desk
  review is the battery connector's through-hole leads, and `J14` carries the
  electrolytics' leads. The board has no debug header (docs/01, 07, 09).
- `U2`/`U3` are SOIC-16 `74HC595`, not SOIC-20; `U5` is a QFN, not a SOIC-8.
