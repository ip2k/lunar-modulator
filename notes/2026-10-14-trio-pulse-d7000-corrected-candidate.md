# Trio-pulse D7000 worker handoff

- Outcome: rebuilt the corrected UART-overflow source and prepared a private expanded-D7000 candidate offline. Only the dated source note is intended for Git.
- Source checkout: /home/claude/worktrees/trio-pulse-d7000-corrected
- Branch/base: codex/2026-10-14-trio-pulse-d7000-corrected at 66196f54f3295cfdec14a2924c767235bbd5cc2c
- Note: notes/2026-10-14-trio-pulse-d7000-corrected-candidate.md
- Build: /home/claude/.local/share/codex-private/trio-pulse-d7000-corrected-66196-20261014/build
- Candidate: /home/claude/.local/share/codex-private/trio-pulse-d7000-corrected-66196-20261014/candidate
- Build app SHA-256: 3de52e9bddd24c19fbabaa3cc7cec97ea78ef0a2397debfc009befb1f8b9b6bc (807320 bytes)
- ELF SHA-256: a07fbd8e966873c154bfc4f62fc1d9b608004e7d1c56640f59a762959d324e6e
- Candidate target SHA-256: c240999ca08479defa07b10b0ed8d4a07891155c37ea84572629212efcaddbe8 (1 MiB)
- Candidate receipt SHA-256: 3118f107811a77b01904518d5ead706191c3a1ff13a7dce54087deefc44c1ccb
- Baseline: matched stockA/stockB, each 1 MiB and SHA-256 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4; manifest SHA-256 1449ba1ec680efeb2900fa04d8198dc16f50fa4643529b88a2293656322f4e94.
- Changed sectors: 4 through 214 inclusive (211 sectors); protected [0,0x4000) and [0xD7000,0x100000) match baseline. All hardware/install/storage/SAVE admission flags remain false.
- Checks: target link/audit completed with zero failures/pending; tests/test_expanded_native_candidate.py passed 27/27 in bounded Hera container; git diff --check passed.
- No device, USB, MIDI, flash, power, reboot, deployment, or publication action occurred. Build used the manual builder, which emits no image.json/build_tuple/provenance sidecar; do not claim those.
- Next: coordinator review of this exact candidate with the content-free D7000 diagnostic receipt/factory. Any physical action remains exclusively with the Mac coordinator.
- Hera bare push pending at handoff creation; update this line with commit and verified remote SHA before release.
