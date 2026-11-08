# Browser recovery page (M12w part 2), 2026-11-08

## What was built
`sim/web/www/recovery.html`, `recovery-page.js` (DOM glue), `recovery-serial.js`
(Web Serial adapter), `recovery-transporter.js` (protocol and safety logic),
`recovery.css`. Tests: `sim/web/test/recovery-{transporter,serial,page}.test.mjs`
plus `recovery-fake-port.mjs`, a model of the transporter firmware.

## Sources
- Protocol: FM-1-transporter `a7fb5e8` `src/transporter_proto.c` (status has four
  fields; read = `DATA n`, bytes, `END crc|FAIL`; `wsec`, `ldr`) [verified: read
  from the git-ignored `reference/` clone]. Upstream `web/index.html` (MIT) is
  already a Web Serial client; ours differs as listed in
  `tools/fm1-transporter/UPSTREAM.md`.
- Policy: `tools/fm1t.py` `cmd_write` (ref compare over [0, 0x93000), only
  differing sectors, none below 0x4000, final full read).
- Rules: docs/17 section 8, owner decision D2.

## Safety design
- Allowlist `ping status rekey info read ldr wsec`: `uboot`, `runapp`, `jump`,
  `memw`, `memr` cannot be sent (tested, nothing reaches the fake wire).
- Flash commands need (a) fresh `status` with `v15=0`, (b) the user's "FM-1 is
  off" confirmation, (c) `uboot=1`. `v15=1` is refused regardless of the checkbox.
- Only the data port is opened. The console port treats letters as commands
  (`i`, `n`, `k` ...), so the page never probes ports; the user picks.
- Loader size/SHA-256, package SHA-256 (stock V15 only), image boot-area diff
  refused, in-session two-dump backup required before a dry run, flash recheck
  immediately before the write, write failure stops at once.

## Review hardening (same day)
- Write provenance: `RecoverySession` records `identified` (identify),
  `loaderReady` (uploadLoader, which now also requires the off confirmation
  and `uboot=1`) and the backup; `rekey()` forgets them and closes the link.
  `plan()` returns a frozen summary and keeps the sectors and private copies
  of the image and flash read inside the session (a WeakMap keyed by the
  summary). `write()` refuses (`not-identified`, `no-loader`, `no-backup`,
  `plan-foreign`, `plan-stale`, `port-closed`) before asking for
  confirmation, re-checks every sector against `[0x4000, 0x93000)`
  (`assertWritableSectors`), and accepts each plan once.
- `uploadLoader()` returning `already-loaded` (the page was reloaded without
  a rekey) still counts as the loader step: the chosen file was checked in
  this session, and the transporter reports a loader. A stricter reading
  would force a rekey in that case; not done.
- Request lines must match whole-line templates (`REQUEST_TEMPLATES`,
  `checkRequest`), with payload length tied to `ldr`/`wsec` and read/write
  ranges checked, so `ping\nuboot` or `read 0x0 16 uboot` never leave the page.
- The page closes the old link before forgetting it (one `dropLink()`), clears
  the plan on port-closed, rekey and reconnect, and shows each chosen image's
  hashes against the session backup (`describeImage`). A raw dump has no
  readable `FM-1_0xx` string, the app being encrypted in flash (docs/02).
- Page and docs/17 §7a: units with a replaced boot area (Felucca, SLOOP)
  refuse a stock restore by design.

## Results
`node --test sim/web/test/recovery-*.test.mjs`: 40 tests, 39 pass, 1 skipped when
the git-ignored stock V15 package is absent; with `FM1_V15_FWSC` set to it, 40
pass, including extracted image == the research shim's `raw[0x414:0x414+0x93000]`.
After the review hardening: 54 tests, 53 pass, 1 skipped (54 pass with the package);
`tests/test_sim_web.py`: 215 passed. The page itself was not reloaded in a
browser after the hardening (syntax and import checks only).
Page loaded over localhost in the browser pane: no console errors.

## Not tested / limits
- No hardware at all: the Pico was not connected; Web Serial itself, picker
  behaviour and the rekey reconnect were not exercised. The fake port is our
  reading of the firmware source, not the firmware.
- Reconnect after `rekey` needs the user to re-pick the port (the page does not
  probe ports automatically, see above).
- A 1 MiB backup that differs from the flash at/above 0x93000 (for example a
  092 backup) cannot be fully restored: the firmware refuses sectors there. The
  dry run reports it. Restoring the owner's FM-1_092 remains untested.
- Large backup size in memory: two 1 MiB buffers plus plan copies, fine.
- No LAN builds: the work is pure JavaScript, nothing needed aeon/hera/ares.
- Commit trailer: the task asked for "Claude Opus 5.5"; this session runs
  Sonnet 5.5, so the trailer names Sonnet 5.5.
