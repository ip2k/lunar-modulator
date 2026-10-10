# FM-1 live bring-up continuation, 2026-10-10

Personal MIT stream `chore/2026-10-10@fm1-live-bringup`, based on main
`bdba4476570b0a77d13c76a38dfb3bcfd364277b`. The owner authorized parallel
firmware preparation and bounded read-only bring-up with the powered FM-1
still directly on Bench01. The browser candidate and shared MCP projects
remain separate. No soft key, loader upload, flash erase/program, eFuse,
new application execution, or topology change occurred in this checkpoint.

## Fresh physical state

[verified, 07:21–07:25 UTC] Bench01 is reachable as `claude` and enumerates
USB `4c4a:c755` FM-1 at direct root port `3-2`, 12 Mbps, ALSA card 2 /
`hw:2,0,0`; no process owned its raw MIDI node. A separate USB Analyzer
`1d50:615b` is also enumerated. This does not imply the FM-1 has been moved
onto the analyzer. Keep the direct connection for initial checks.

[verified] One updater identity request, exactly
`F0 00 32 45 00 00 00 40 7F F7`, returned a complete 41-byte `FM-1_092`
reply. It is byte-identical to the previously recorded owner-unit frame
`KNOWN_092`, SHA-256
`7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d`.
The decoder's checksum remains **false**, as documented previously; this
is not a new checksummed identity or a general checksum exception. Only
identity was transmitted. The capture is private in the worktree's ignored
`scratch/fm1-bench-20261010/identity.syx` and Bench01
`/tmp/fm1-identity-20261010-0725.syx`. The nonbinary
[receipt](data/2026-10-10-fm1-live-inventory.json) records the exact frame.

Bench01's system Python has no `mido`; no packages or services were changed.
The reviewed `amidi` raw-MIDI request used the same exact ten bytes as the
Python tool, with three seconds of silence termination, then the existing
Python decoder read the saved reply without accessing the device. Focused
identity/probe tool tests: **19 passed**.

## Recovery evidence, freshly rehashed

[verified] On both Bench01 and this Mac, session2 `dumpA.bin`/`dumpB.bin`
and restore1 `beforeA.bin`/`beforeB.bin`/`after.bin` are each 1,048,576 bytes
with SHA-256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Bench01 directories are root-private; unprivileged enumeration initially
returned no files, and explicit `sudo -n` read-only hashing resolved this
without permissions changes. Private storage paths remain
`/home/claude/fm1-backups/2026-10-07-{session2,restore1}/` and the original
Mac checkout's ignored `scratch/fm1-bench-20261007/` directory. No vendor
or flash binary is tracked here.

This preserves the historical bounded sector program/restore proof in
[the bench note](2026-10-07-fm1-softkey-bench.md). It does not establish
full-image restoration or broken-application recovery. No Lunar application
has executed on this unit.

## Semantic tooling for this continuation

Rarefaction `status` reports the original checkout, on-open clangd and no
root compilation database. That checkout does not contain the newer
handover capture file; its attempted orientation failed ENOENT. A corrected
exact-position Python `query_device` orientation resolves the 27-line body,
`main` caller and `hexs` callee, consistent with source. No tests are indexed
in that result. The wrong initial line resolved a noncallable position and
is not useful coverage evidence. Python interpreter advice remains present.

Serena initial instructions/config reports ready servers at the separate
semantic-tools-config worktree (`cpp`, `typescript`, `python`). Its
`find_symbol(query_device)` body agrees with actual source. SHA-256 of the
identity tool is identical in both MCP roots and this branch
(`684342b034b1a97b0e070ff758edf9bff20714523316a968952ccf48f52c0de0`).
No shared activation/restart occurred; these results do not index this new
worktree or prove pi32v2 ABI/device behavior. New firmware code is inspected
with file tools and actual target build evidence when available.

## Next bounded milestone

Continue from the reviewed linked diagnostic, panel-protocol link and
stock handover layout analysis. Current PR134/136 are not green/merged;
their source/artifact evidence is useful but does not authorize execution.
Identify an observable RAM-only proof and the exact startup/private-RAM,
clock/watchdog/vector/secondary-core/MMIO contracts needed before a
stock-preserving application experiment. Prepare and test offline first;
message the parent with the concrete image, ranges, operation sequence and
recovery plan before any proposed risky device action. No arbitrary vendor
command, blanket erase, eFuse operation or automatic soft-key retry is
permitted.
