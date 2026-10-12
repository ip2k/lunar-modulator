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
