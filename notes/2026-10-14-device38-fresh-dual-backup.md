# Fresh device38 dual backup

[verified] The Mac coordinator passively observed bench01 port `1-1`, bus 1,
device 38, ROM `4c4a:8057`. The new exact-enumeration adapter passed preflight
and ran once, uploading only the previously reviewed RAM recovery loader.
It issued the pinned 8,757-command inquiry/upload/dual-read inventory, with
zero flash operations, zero reset operations and no retry.

[verified] Both complete 1,048,576-byte reads matched SHA-256
`c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903`,
the previously installed FIRST ORBIT image. Adapter SHA-256:
`a513ca23ff448d58fd12be586def4b6a9632e1614010b1291d44cbd49f6d47fb`.
Campaign SHA-256:
`28daf0f605e9373c2832a5da14eaa99337ca021215fbe4b4ecf67c13655d2175`.
Manifest SHA-256:
`2bed49db98cf7268d7cab7ff3283dd8d5eade233cf45d39505099a0095e44812`.
Command transcript SHA-256:
`fb3f60fb4344b72e3887283ed9b046e9109ef7f3d2a83f2ed0d8cdf67d8e259f`.

Private originals are under
`/home/claude/fm1-device38-read-source-20261014/fresh-backup-001` on bench01.
A receipt archive, including both dumps and the consumed marker, is retained
in ignored `build/native-device38-backup-20261014/receipts.tar` on the Mac;
an offline copy is in Hera's private `device38-backup-20261014` directory.
No vendor or owner flash bytes are committed.

[verified] The revised adapter passed 16 mocked admission/execution tests on
Hera and independently on the Mac. The live run establishes matching current
backup bytes and a functioning RAM read path. It does not establish recovery
after corruption, rollback, screen/audio acceptance, SAVE persistence or release
acceptance. The FIRST ORBIT watched-boot observations remain pending.

Next: validate the named eight-voice compressed-table receipt profile, prepare
exact current-to-Event-Horizon and rollback transactions, independently review
the physical adapter and installation plan, then install/read back before
announcing the two-minute watched boot. Event Horizon is approved as the default
song; this approval does not substitute for its hardware acceptance.
