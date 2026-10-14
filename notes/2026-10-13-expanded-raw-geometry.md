# Expanded raw-image geometry and recovery

The owner-approved profile ends the application/configuration area at 0xD9000.
`tools/jieli/expanded_flash_profile.py` constructs and independently verifies
private raw candidates from two equal baseline copies plus pinned stock reference
components. It supports only the strict recorded FM-1_092 baseline geometry.
The existing unchanged-layout parser and physical admission paths are unchanged.

The aligned application budget is 868,836 bytes. Configuration-tool and cfg
contents move after the application; directory extents and CRCs are regenerated,
and the expanded area is transformed with the recorded SFC origin. Raw bytes
before 0x4000 and from 0xD9000 onward must remain identical. Reserved descriptors,
entry address, names, flags, terminators and directory gap are checked; unnamed
padding must be erased. The verifier compares actual tool/cfg contents even if
an altered candidate has valid recomputed CRCs.

Initial Hera campaign `expanded-geometry-v1`: 103 audit/artifact/geometry cases
passed in thirty containers, including exact maximum budget, overflow, changed
protected bytes, cipher/header corruption and the original parser's refusal of
the expanded layout [verified synthetic]. All logs were inspected; no OOM.

The second campaign adds repaired-CRC tampering and persistent expanded-image
install/rollback faults. It finished with 115 passing cases and two 120-second subprocess timeout
failures at commit erase (install and restore); no OOM. All thirty logs were
inspected. `expanded-geometry-v3` reruns the 37 geometry/recovery cases with a
900-second worker bound and exact interrupted-sector byte assertions; its
terminal result remains pending. Receipts are private under the Hera root
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/`; local mirrors
are under `build/native-external-arenas-16-20261012/`. Reproduction launcher:
`notes/2026-10-13-expanded-geometry-verification/launch.py`.

## Acceptance limits and next dependency

Geometry verification does not establish baseline provenance, ELF admission,
OTA package verification, settings migration, hardware admission or installability;
receipts explicitly mark these false. No device command was sent. Synthetic
boot registrations and USB_KEY entry remain model assumptions. No vendor binary
is committed. The profile is not wired into a live flasher.

The FM-1_092 VM bank remains at 0xD9000 and is protected byte for byte in this
profile; its contents are not interpreted as Lunar settings. V15's different VM
location/capacity requires separate export/migration and rollback treatment.
Before hardware: bind an audited actual native artifact, verify private baseline
provenance and concrete recovery plan, then refresh identity and obtain two
matching full backups. Full startup, persistence, timing, browser installation,
selectable builder and review/CI/integration remain required release work.

## Actual private construction [verified offline]

The retained matching stock copies (SHA-256 `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`)
passed the strict recorded baseline parser against the private FM-1_092 reference.
The actual audited all-thirteen application, 838,712 bytes, produced a complete
1 MiB candidate with SHA-256 `400fcbcc883af0a6fdbb60e17759ae8a0778f16adb9490519b9935d11a32d907`.
The independent geometry verifier passed; protected raw banks and configuration
contents remain identical. The experiment checked the application/ELF hashes
against the previous artifact receipt; it did not repeat its full admission
audit or grant physical permission. Candidate and receipt are private under
`out/expanded-private-geometry-v1`; local receipt mirror is in the ignored
build directory. No physical installation or OTA acceptance is claimed.
