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

## Results
`node --test sim/web/test/recovery-*.test.mjs`: 40 tests, 39 pass, 1 skipped when
the git-ignored stock V15 package is absent; with `FM1_V15_FWSC` set to it, 40
pass, including extracted image == the research shim's `raw[0x414:0x414+0x93000]`.
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
