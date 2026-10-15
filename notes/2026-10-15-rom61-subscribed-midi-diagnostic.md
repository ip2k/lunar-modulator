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

## Completed native62 capture

[verified] Both fresh complete flash reads matched the installed target SHA `222164721a323bce80a3fd3a0444588c93ef734e577940ddb80b7432402d1ab6`. The sole FC0C argument1 response was ambiguous and was not retried. Independent native enumeration appeared as bus1/device62 on physical1-1. The helper completed, audio and telemetry children exited0, bounded usbmon exited124 at its timeout with636 captured bytes, and passive enumeration subsequently showed ROM bus1/device63. No flash programming occurred. There is no aggregate `diagnostic-audio/receipt.json`; terminal evidence is the append-only helper journal plus the telemetry receipt and actual artifacts.

[verified] The100 decoded telemetry frames span device uptime1006–100963ms. USB messages increased0→6, UART bytes0→18, accepted note-ons0→6 and rejected messages stayed0. The scheduled TRS notes caused the first three note-on increments; the USB notes caused the next three. The exact native62 EP1 OUT trace contains six matched submissions/completions, each4bytes, successful status0/full actual length, decoding into channel1 C4/E4/G4 Note On/Off pairs. No malformed trace rows, unmatched completions or unfinished submissions were found. This establishes subscribed-host delivery and native handler dispatch for this diagnostic, correcting the earlier direct-addressed sender failure. It is not full-song or broad MIDI conformance acceptance.

[verified] Audio underruns stayed84 throughout the sampled interval; produced blocks increased212→69116. Maximum recorded render time1154us and draw time6436.7us remained unchanged. These are sampled cumulative diagnostics, not worst-case scheduling proof. Minimum observed user/system stack margins15064/7724bytes are not exhaustive bounds.

[verified] The150second six-channel48kHz signed32bit KA6 recording SHA `7636d91740a834aba1ca2bc4bc750cc05833257c6dbc9b6eca9cd185a255dd1a` matches on bench01 and Hera. The checked-in streaming analyzer completed on Hera in a networkless2CPU/256MiB memory+swap docker-batch.slice container. Both signal channels had zero clipped samples; peaks0.33837/0.34499. Channel1 windows18–19,22–23,26–27,41–42,45–46 and49–50seconds were approximately−23dBFS against approximately−66dBFS idle windows, consistent with six separate stimuli after capture/epoch offset. Exact timestamp alignment and spectral review remain separate; this does not establish subjective sound quality, Event Horizon playback or release acceptance. Private evidence is retained at the bench base above, ignored coordinator `scratch/trio61-subscribed-results`, and Hera `/home/claude/.local/share/codex-private/trio62-analysis`.

Next: decouple telemetry from the content-free Trio pulse so a fresh all13 Event Horizon+SET diagnostic can measure the actual song workload. SAVE remains disarmed; full recovery, migration, installer and public-release gates remain open.
