# Schema-9 private diagnostic receipt review

[verified: bounded source review] Coordinator reviewed worker
`cc46a1a3270823237de5824e06553aeff80cfc38` and integrated it as `14eda129`.
The dedicated SONG branch requires exact schema-9 field names, JSON types,
counter order, 189-byte/63-packet frame geometry, stride 32 and raw TIMER4/IRQ
semantics. It also requires exact engine, render-stage and IRQ receipts,
disabled Trio pulse, enabled diagnostic transport and a bounded PLAY or explicit
no-autoplay receipt. CPU-rate and producer-gap composition is rejected;
malformed schema-9 presence cannot fall through to legacy admission.

Existing schema-7 exclusions and public installer behavior are preserved.
The change adds no device opener, public endpoint or hardware acceptance.
Worker focused checks passed 72 tests. The coordinator independently passed
141 focused diagnostic/reopen/SG/boot/public-profile tests after integration. Coordinator refreshed the SG adapter's
policy pin and boot adapter's policy/SG pins after review. A file-only live
`_source_evidence()` check validated all eleven evidence entries.

Policy source fingerprints intentionally changed. Previously sealed policies
remain bound to their original validation sources; this change does not migrate
or grant authority to old seals.

Aeon target build fit and output/container verification are recorded separately
in `2026-10-17-schema9-aeon-independent-review.md`. Physical FM1 recovery is
still required before any diagnostic installation or boot. No clean audio,
profiler overhead, persistence, public installation or release acceptance is
established by receipt validation or host tests.
