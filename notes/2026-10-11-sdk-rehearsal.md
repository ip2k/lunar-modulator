# Exact private diagnostic install/readback/restore rehearsal

Work in progress, 2026-10-11. No physical erase/program has run.

The new `tools/fm1_sdk_rehearsal.py` accepts one exact target
`df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`
and saved baseline `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
It binds both SDK policy directions, replays the actual fixed-loader backup
commands, pins its complete helper snapshot, and permits only FC0A geometry
query, aligned FD05 reads, exact derived-sector FB01 erase and exact
direction-bound FB04 program. The durable one-use marker precedes device open.
[verified: source inspection; independent review and tests pending final freeze]

Full NOR readback is required before and after each direction, with erase and
sector readback and the application-directory sector committed last. Each SG
intent/completion is fsynced; completion includes input-response hashes for an
independent later verifier. Bad status, sense, residue, changed FD/sysfs binding,
log failures and close exceptions stop without retry. Sticky BaseException
close state prevents inherited cleanup from hiding failed closure.
[verified: source; no physical acceptance]

The accepted source's physical meaning still depends on the separately reviewed
[native NOR paths](2026-10-11-fixed-loader-nor-write-review.md). FB04 has no
visible native CRC check and does not return ordinary input data. Correct host
framing alone cannot establish a successful write; actual readback gates it.

Current adapter freeze: `f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4`.
Focused tests and independent review are running against that freeze in 16
Hera chunks. A previous file-only bench preflight of source38527d0e accepted
campaign7846820f without constructing transport; that earlier packet is not
authority for this changed source. Parent must stage a new exact packet and
repeat its file-only checks before hardware. No source or mock pass claims
physical installation, boot, display or recovery.

Next: accepted final test/review evidence, new frozen bench packet, one bounded
install/full-readback/restore/full-readback rehearsal. Then a separate reviewed
post-rehearsal reset policy; baseline-only no-later-commands reset is invalid
after rehearsal. Diagnostic boot/display/recovery and interrupted-write
physical acceptance remain later goal dependencies. All private SDK/vendor
artifacts remain ignored and undistributed.

## Frozen bench packet v2

[verified: file-only preflight] The final f696 adapter packet was exclusively
staged at `/home/claude/fm1-fixed-backups-20261011/attempt-001/rehearsal-stage-v2`.
Archive SHA is `12983d60194dba22b6716319549d126e24f002ee753db9040e7581f9a4539b46`;
packet inventory SHA is `682dcf487fd3217cc6f5a057f0859a9e015f70f5c72dc99355c033b0db46cdd9`;
campaign SHA is `7ff0f504d4ea12953532caf20223173925131d1541d4f5e5103a7b4f95076de4`.
Every staged inventory member was checked, then the production factory accepted
actual files without constructing transport or opening hardware. USB 3-2 remains
ROM device 23 and the rehearsal marker is absent. The earlier packet is parked.

[verified: independent source review; tests pending] Private wrapper SHA
`173a9705476223ee2047d89e2dc37d7d0747e1c1be62bc4e98b3bfe0607dbd6e`
owns one passive usbmon reader and one exact isolated Python child. Acceptance
requires actual wrapper exit 0, child exit 0, capture-stop receipt, no wrapper
ambiguity receipts, complete adapter result/log and independent capture review.
Text usbmon records only 32 payload bytes; it cannot prove full page payloads.
The source's input-response hashes and transaction readback are separate gates.

[verified: device-free smoke] Tests `95879aa0905fff810f8a31eba3ac7e1134a609ea1c3c5d9bf8c4182c33b32605`
collected 125 unique cases. Actual factory/native/raw gates and modeled complete
install/readback/restore smoke passed against the actual private files. The final
16 chunks are still running. The model uses a controlled monotonic clock; it
does not establish physical throughput within the 900-second live lease.
