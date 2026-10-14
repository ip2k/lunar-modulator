# Streaming application project collector verification

[verified] 76 tests passed in 30 concurrent Hera containers on 2026-10-14.
All 30 full logs were inspected: no skips, failures, errors or OOM kills;
process and container exit codes were zero. Fourteen source hashes match
the local checkout. Source snapshot `seq-collector-source-v1`; output
`seq-collector-v2`. Full logs remain in the ignored local
`build/native-seq-record-export-20261014/collector-v2/` directory.

The 64 sequencer export cases use ASan/UBSan and compile the exporter and
record adapter with the pinned pi32v2 compiler. The 12 application-state
cases build the real desktop application at O2 and verify its existing
project/set save, import and schema acceptance paths. They are not hardware
tests or an ASan build of the whole application.

The earlier collector-v1 run skipped three schema cases because jsonschema
was missing. The complete v2 run used a separate Python 3.11 dependency
directory, without changing the existing pytest environment. The container
image is pinned in the launcher; the supplemental dependency directory is
not yet a reproducible lockfile and this receipt does not claim hermeticity.

[verified] Project and binary-set collectors now stream sequencer LINE
records instead of staging the complete set text. Sink refusal is sticky
and an exporter failure fails collection. Actual compact binary-codec
parity/reader checks and 10,208 binary callback failures are recorded in
`../2026-10-14-seq-record-export-verification/`.

Limits: the global text buffer still serves raw text, clip and import paths.
No native SAVE callback, firmware link/RAM-fit proof, storage allocation,
physical flash write, migration or rollback is established by this run.
The next dependency is a bounded native project collector/writer workspace
and an admitted storage layout, followed by hardware persistence tests.
