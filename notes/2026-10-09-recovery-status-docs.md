# Recovery status documentation corrections — 2026-10-09

## Evidence and scope

Checked README and docs/05, docs/08 and docs/10 against the completed results
in [the 2026-10-07 bench record](2026-10-07-fm1-softkey-bench.md), and the
current owner-authorized staged policy in docs/07 §4, AGENTS.md and CLAUDE.md.
This is a documentation correction; no hardware command or action was taken.

[verified: bench record] Soft-key UBOOT entry and a pinned recovery loader in
RAM produced two matching full 1 MiB dumps in each session. The bounded
`[0xD8000,0xD9000)` unused 4 KiB sector was programmed, read back and restored
to its original FF bytes. The complete post-test flash dump matched the
fresh and original backups. The owner confirmed normal boots after the
first session and after restoration; normal USB and FM-1_092 identity were
rechecked after the second power cycle.

Whole-image restoration, recovery from a nonbooting application, the
physical dongle on this unit and Lunar application execution remain untested.
The result does not authorize arbitrary writes. Matching private backups,
exact image/range review and a recovery plan remain required by docs/07 §4.

## Changelog

- README: replace claims of no chip execution or device writes with the
  demonstrated recovery work; distinguish it from Lunar application execution
  and the remaining installation/recovery checks.
- docs/05: correct the recovery blocker description, successful entry on the
  owner's unit and the obsolete claim that OTA never accepted non-stock apps.
- docs/08: record bounded restoration, full-flash comparison and confirmed
  boots; remove the superseded blanket whole-image restore prerequisite from
  the Phase 2 instructions.
- docs/10: retain the untried dongle status while recording soft-key/loader
  results, verified enumeration and flash access; replace the obsolete generic
  whole-image write permission with the staged policy and bounded evidence.

## Validation

Documentation-only change. Read each resulting recovery claim against the
named bench evidence; checked local Markdown links and `git diff --check`.
No firmware build, hardware test or new restore proof is implied.

## Current-main integration

Merged main 67d5e12d on 2026-10-09. README conflicts retained the current
product roadmap, envelope description and linked-inert-diagnostic distinction;
its recovery facts were already present on main. The remaining unique changes
are docs/05, docs/08, docs/10 and this evidence note. `git diff --check` passes.
Fresh exact-head CI must pass before automatic integration. No new hardware
traffic, whole-image restore or running Lunar application is implied.
