# Device38 Event Horizon transaction plans (offline)

[verified] This task prepared durable offline transaction plans for the owner-designated Shapes8/Event Horizon 120-second target. It created no transport, sent no command, performed no reset, and made no flash or power operation. Every output admission field remains false. The pending independent transport-manifest check is a hard stop before physical use.

## Pinned evidence

- Fresh device38 pair: /home/claude/.local/share/codex-private/device38-backup-20261014/fresh-backup-001/; matching dumpA.bin and dumpB.bin, each 1,048,576 bytes, SHA-256 c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903.
- The paired fresh manifest SHA-256 is 2bed49db98cf7268d7cab7ff3283dd8d5eade233cf45d39505099a0095e44812; its pinned command transcript SHA-256 is fb3f60fb4344b72e3887283ed9b046e9109ef7f3d2a83f2ed0d8cdf67d8e259f. The manifest identifies exact ROM USB 1-1, VID/PID 4c4a:8057, device number 38, 8,757 commands, zero flash operations and zero reset operations, and binds installation proof 1798734ef5d8a0754cd17e039e7747a306e34177ebaabcdc591ad06f3a25e41c.
- Target NOR image: /home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014/target.bin, 1,048,576 bytes, SHA-256 145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657. Its adjacent candidate-receipt.json SHA-256 is 1c53f94ba57001f30901a2f33081f26c223f1789781abaa0f5325e83880684db; the receipt binds app payload 845,036 bytes / 5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573 and marks hardware admission, physical writer readiness, installation and settings migration false. The candidate is still awaiting the separate transport-manifest checker; this plan does not clear that gate.
- Stock target reference: the matching full-flash pair at /home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/stock{A,B}.bin, both SHA-256 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4. This is a retained October 12 historical stock pair, not part of today’s fresh device38 capture and not a new observation of current device state.

## Plan results

The helper is tools/native/event120_bench_transactions.py. It pins the exact fresh manifest/transcript/current image, target NOR image and candidate receipt, checks matching A/B reads, binds device38 and the prior installation proof, computes changed sectors from bytes, refuses changes outside raw application area [0x4000,0xD9000), and seals 0x4000 as the last directory/commit sector. It uses the existing durable tools/fm1_flash_transaction.py journal, readback and full-image verification logic.

Private prepared artifacts are under /home/claude/.local/share/codex-private/device38-event120-transactions-20261014/prepared-002/ (not tracked). The preparation receipt SHA-256 is ecdd5a2444b3c146123b364916b7b3ff029c700d29a1ff5ab7ce849491c48484. Candidate plan: 208 sectors, target 145c0280…a4657, plan SHA-256 46425c0e3e12f5a61737c4160af595afb1c6955453bff8ee6a14d0c53279d25a, commit sector 0x4000 last. Stock plan: 213 sectors, target 96006a51…c4e4, plan SHA-256 ed934f5476fb02891ebe43bae3f885e8b0900573ec78b927739681744c67455a, commit sector 0x4000 last. Candidate changes end at 0xD4000; stock restoration changes end at 0xD9000. All bytes outside the candidate/stock transaction’s derived ranges match the fresh baseline.

Recovery model: if a candidate operation is interrupted, reacquire a fresh approved session and use the candidate transaction’s restore direction to reconstruct and fully verify the fresh c543… baseline; then the separately prepared stock plan can be applied and fully verified to 96006a51…. If the stock transaction itself is interrupted, its restore direction targets the fresh c543… baseline. The model keeps the original journal’s ambiguous-operation rule; it does not retry on a stale session. This demonstrates behavior of the existing offline transaction state machine only, not the physical loader, ROM recovery route, or power-loss behavior of NOR.

The summary receipt explicitly leaves candidate_transport_manifest_admitted, physical_writer_ready, hardware_admitted, installable, and physical_recovery_verified false. Both plans are proposals for coordinator review, not an authorization or admission to write.

## Checks and limits

- python3 -m py_compile tools/native/event120_bench_transactions.py tests/test_event120_bench_transactions.py passed on Hera.
- Ran prepare() directly against the pinned private evidence; both sealed plans reopened through load_transaction() and matched their baseline/target bytes, prepared journal state and directory-last order.
- Bounded offline Hera pytest container (lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d, docker-batch.slice, 2 CPUs, 3 GiB memory/swap, network none, read-only root, no capabilities): 2 passed, 1 skipped. The skipped exact-private-input pytest fixture could not read mode-restricted private evidence under container UID 1000. Direct helper execution on Hera did read and verify those private inputs; this is documented separately rather than weakening their permissions.
- Synthetic failure test tore a page write, observed recovery_required, recovered via a fresh fake session to the original full baseline, then applied the independent stock plan. This is a software model, not physical acceptance.
- No new target link, USB/MIDI, flash, reset, power, install, or boot experiment was performed.

Next dependency: coordinator must obtain and review the independent transport-manifest checker result for this exact candidate and its currently fresh device38 evidence before deciding whether any physical transaction is in scope. The historical stock pair and pre-existing physical recovery gates remain independently reviewable.
