# ROM61 subscribed MIDI diagnostic — 2026-10-15

## Admission

[verified] The preceding compression-answer turn was a status explanation without a source/device change. This continuation corrected the historical sector arithmetic, independently recomputed compression on both original backups and pushed `214e84434988666b8a1086f6ef091a7e3d0e8942` with remote SHA verification. The full release goal remains ACTIVE.

[verified] Passive bench discovery shows ROM bus1/device61 at physical1-1, KA6 device51, Pico device38. The next diagnostic uses installed target `222164721a323bce80a3fd3a0444588c93ef734e577940ddb80b7432402d1ab6`, fresh paired complete flash reads, the existing allowlisted RAM loader, and one FC0C argument1 request. It performs no flash programming and never retries an ambiguous reset response.

[verified] Private base `/home/claude/fm1-trio-subscribed-midi-9ec846-20261015` was newly created with exclusive file creation. Helper SHA `1c42f4d5b086d566a2f5dd56d5d6100275a6dc1114be1ba3fd1e02aa7f51d765`; runner SHA `cf1435b45205c241f15712eeee16c1181cc2951548387f60f10a8500c15cdcea`. Both hashes were verified on bench01, and file-only preflight passed against the unchanged 174-file capture runtime. Combined helper/usbmon/generic-boot verification:45 tests passed. Private retained ROM59 campaign/manifest/journal bytes replay through the new validator after offline device/path/digest adaptation. Incomplete append-only journal prefixes wait within30seconds; completed evidence is hash-bound to the one-shot campaign plus new native same-port enumeration. SG completion remains explicitly ambiguous, not protocol success.

[inferred] Subscribed mido output may fix aseqsend direct-output delivery. Each bounded child holds its output subscription through note-on,2seconds and note-off. Capture covers exact native EP1 bulk OUT plus diagnostic counters and150seconds of KA6 audio. This is a diagnostic hypothesis, not a MIDI acceptance claim.

## Previous native60 audio evidence

[verified] Hera analyzed the complete150second WAV SHA `78a1f3b9ebee3e3577384654c386e396d921afa579d85a866bc2adb4ab2bc8b6` with the checked-in streaming analyzer, using python3.12-slim,2CPUs,256MiB memory/swap ceiling, docker-batch.slice and no network. Exit0; zero clipped samples on both channels. Capture-relative0–15seconds aggregate RMS was approximately-27.4/-27.2dBFS, while15–35,35–55 and55–75second aggregates were approximately-66.0/-65.6dBFS. These aggregate windows are not exact stimulus-clock alignment and do not prove note receipt or perceptual quality. They corroborate an early automatic-signal interval and later near-noise recording. Private output remains on Hera and in ignored coordinator scratch. No publication of audio or owner data.

## Live campaign

[verified] Independent capture-gate review found no blocker for this bounded diagnostic. Coordinator started existing runner once; terminal session79970 reported FRESH_READ_START. This is live acquisition, not completed boot or verification. Poll that same handle and detached capture helper before any next action. No reset retry is permitted.
