# ARP refusal fixture after immutable lock-event storage

[verified] Exact failure: PR165 CI run `41302493347`, MIT/BSD job
`124836168333`, source `bb9187f393f5c5b48ae782ef31a137928f91c167`.
`test_the_ram_meter_refuses_an_arp_that_would_not_fit` failed during initial
setup, before its first ARP gesture. The chain Macro + Shapes + Room + Ensemble
+ a Diffuse insert costs 388,536 B against the unchanged 387,924 B budget;
Diffuse is refused with `FM1_APP_SELECT_RAM` (-4). This is an obsolete fixture,
not evidence of a new ARP runtime failure. The original test reproduces RED in
fresh native MIT/BSD and default builds from that exact source.

[verified] Both native profiles measured the same 64-bit costs at 44,118 Hz:
fixed meter 82,408 B; Macro 32,880; Shapes 207,872; Room 41,200; Ensemble 4,752;
Diffuse 18,912; extra sound scratch 512. The original chain exceeds the limit
by 612 B. Removing only Ensemble leaves 383,784 B, with 4,140 B remaining.
The first enabled ARP needs its host stage (8,056 B) plus instance (736 B):
8,792 B, for a refused hypothetical total of 392,576 B (102%, 4,652 B over).
Removing Diffuse instead was probed and rejected as a fixture choice: that
chain plus ARP fits at 378,416 B, so it cannot prove ARP refusal.

[verified] Changed only this test's setup to omit the unused Ensemble. All
original assertions remain: initial chain fits, adding ARP crosses the budget,
tap and hold leave ARP off, tap leaves HOME selected, and the popup reports the
calculated percentage. Added assertions that refused tap/hold preserve the RAM
figure. The former oversized arrangement remains an explicit -4 setup-refusal
witness. No production source, resource guard, budget, quality, timing, rate or
sequencer code changed; no hardware commands or WASM build occurred.

[verified] Focused validation used all of `tests/test_sim_arp.py`: **MIT/BSD
26 passed, 2 GPL-only skipped; default 28 passed**. Fresh native builds and
RED/green runs used the regular pytest build fixture (no fixture override).
No ASan run: changes are Python fixture/assertions only. This is bounded native
validation, not a complete CI result or device acceptance. Parent owns the
other CI failures and integration/retry.

[verified] Branch `fix/2026-11-01@arp-meter-fixture`, isolated worktree
`/Users/likwid/.codex/worktrees/lunar-arp-meter-fixture-20261101`, exact base above.
Only the test and this note are committed. Both are outside the WASM source-hash
inputs; existing engine/sim hashes remain
`8811a7d551ae37405bcabee91b2f1270ded208e9d65f49f0ff930be35ca68d33` and
`05ab17baab5e58627c4340947e6e44f1757b226edbdf5267328d12380096b3bd`.

[verified] Rarefaction status/orient/scope and Serena initial/config/find_symbol
matched the test and its local helper. Both servers select shared main, not
this isolated absolute worktree; no global activation/restart was performed.
Pinned worktree source, exact-base archive and runtime probes supply the final
evidence. Pyright has no project venv configured; semantic coverage is bounded.
The advisory co-change files (sequence/editor UI tests) have no needed changes.

[verified] Parent assigned CPU12–15 after native_app_adapter explicitly released
it. Aeon jobs used four CPUs, 6 GiB memory/swap, `docker-batch.slice`, `--rm`,
project=lunar/session=arp-meter-fixture-20261101. Local evidence/scripts are in
ignored `scratch/arp-meter-fixture-20261101/`; remote evidence is under
`/home/likwid/datasets/lunar/arp-meter-fixture-20261101/logs/`. Exact source
archive, native objects/binaries and pytest scratch are reproducible and removed
after logs/probe JSON capture; small logs/scripts and source.sha remain. Worktree
stays for parent review and normal removal after integration. Mac free space
at this checkpoint: 1,117 GiB, above the 500 GiB floor.
