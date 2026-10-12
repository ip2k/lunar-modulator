# Fresh entry stopped before SG readiness

[verified, physical] Initial-entry V2 ran once. A fresh identity query returned
FM-1_092 with its known checksum quirk. The vetted soft key was sent once at
1791813156.294717. Passive USB enumeration observed same-port UBOOT at
1791813157.0415945: topology 1-1, bus 1/device 4, 4c4a:8057,
WL80UBOOT1.00. The original reviewed source and consumed entry are retained.

[verified] The file/sysfs-only backup preparer stopped at discover_sg with
`Exactly one SG device on pinned topology required`. This happened before
opening SG or issuing any loader/flash command. No backup campaign, backup
directory or backup consumed marker was created. The wrapper stopped its own
usbmon capture; return -15 and absent leader/reader were retained. A later
passive observation at 1791813247.23028 found /dev/sg0 on the same topology.
Stock flash remains unchanged by this attempt.

[inferred] USB enumeration completed before Linux created the SG node. A
successor should wait boundedly for passive SG readiness on the exact newly
observed ROM binding, rejecting ambiguity or topology drift. This does not
permit repeating the soft key, retrying a device command or refreshing the
original entry timestamp.

[verified, source only] A continuation was prepared and reviewed but was never
staged or invoked. Its original 600-second entry window expired before review
finished. Preserve it as an unexecuted proposal; it must not be run with altered
timestamps. Source SHA-256:
88e6ca9b170b59a945bc943404fd7e344464708d9fc3928e4137907c122e99eb.

The ignored retained evidence is under
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/failed-initial-entry-backup-v2/`.
The safe regular-file archive has SHA-256
18041660eb5898f9cedae3e665666b0c42db24e5d9398d9f3c66dedd60405df7.
The actual entry log is c2d1950ba56268d8bd40bdfc90fd2b8130ab2eeec5d2fbe23761409cc9788f15;
the capture-stop receipt is 0b91a0b7eef4c52a4a05ca450d3d9a18e2928bf24d7547c118f449a7dfe80a18;
the preparation failure is 64fdaea69afa57a714395818a1a36a0dbedb2e366a5f0a0ec5fdad5cb81f1a81.

[verified, source/model scope] The trace decoder previously rejected panel
protocol errors INVALID=1, TRANSFER_FAILED=2 and DELAY_FAILED=3, although the
native worker preserves those values. The decoder now recognizes exactly
-4 through 3. It retains phase, clock and repeated-read coherence checks;
recognition records progress, and never establishes displayed pixels or
physical recovery. The 76 focused checks passed with zero failures/errors/skips
(60 unselected cases); diff check passed. Source SHA-256 is
411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051;
test SHA-256 is 7c72bb5fb0450b3b16eeedd80406dfe8d8c7f0a0bf41b9ef9e802072fa5b2a1d.
Existing frozen physical decoder pins were not changed. The shared semantic
services still select the primary checkout, so this worktree used source
inspection without retargeting another active session.

[verified, connector response] Computer Use again returned no native apps and
the same lock/automatic-unlock error, despite the owner's confirmation that
the Mac is unlocked and use while locked is enabled. Chrome inventory works.
This is an unresolved connector failure; current Packetry GUI state is not
verified. Bench usbmon capture is the available physical evidence path.

Next: use a fresh normal enumeration and distinct entry/backup root, with a
bounded passive SG wait; obtain two matching full-flash backups before any
erase/program. If physical cycling is unavailable, prepare and review a
separate minimal RAM-reset successor. Trace installation, visible display,
physical recovery and final review/CI/integration remain required.
