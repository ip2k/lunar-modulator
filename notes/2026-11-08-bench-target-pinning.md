# 2026-11-08: ROM target pinning for the bench tools

## Problem
In mask-ROM mode the AC79 dev kit and the FM-1 both enumerate as USB `4c4a:8057`
[verified: CLAUDE.md hardware table; both devices were plugged into the bench
host in this session]. `tools/fm1_uboot_read.py` selected its SG device by
VID:PID only, `fm1_softkey_probe.py` accepted any `8057` after the soft key, and
the dev-kit adapters inherited the same reader. With both boards in ROM, a tool
could have opened the wrong one.

## Change
- `tools/bench_target.py`: one helper, sysfs-read only. `pin_rom_target(role,
  usb_path, device, ...)` refuses unless the path is well formed, allowed for the
  role by `tools/bench_targets.json`, not the other role's exact path, the only
  `4c4a:8057` device on the host, the one `/dev/sgN` resolves to, and (optionally)
  the expected devnum. It logs `target_pinned`.
- `Reader.__init__` (and so `DevkitReader`, `Writer`, `ResetReader`,
  `RestoreReader`) takes mandatory keyword `usb_path`; `Reader.ROLE` is `fm1`,
  `DevkitReader.ROLE` is `devkit`. Every CLI gained or already had `--usb-path`.
- `fm1_softkey_probe.py`: mandatory `--usb-path`; the MIDI device must be on it;
  soft key refused if any `8057` is already present; a post-reset ROM device at
  another path is an error. Only the check was added: no new message can be sent.

## Recorded bus paths (read-only sysfs listing over ssh, 2026-11-08, no device opened)
- FM-1: `1-2`, `4c4a:c755`, bus 1 (normal mode).
- Dev kit side: bus 3: hub `3-1` (`0424:2514`) with Tigard V1.1 at `3-1.4`
  (`0403:6010`), and Komplete Audio 6 at `3-2` (`17cc:1001`).
- The dev kit was not enumerated as a ROM device at the time, so its ROM-mode
  port is unknown; only bus 3 is pinned until it is observed once.

## Tests
`tests/test_bench_target.py` (fake sysfs tree; includes two ROM devices present,
FM-1 in ROM while the dev kit is requested and the reverse, wrong SG node, devnum
change, malformed paths, bad configs, pin-before-open for the readers, soft-key
refusals) plus the existing probe/uboot/devkit suites; see the PR for counts.

## Limits
- No hardware traffic; real SG behaviour with the new check is untested on the
  bench. A real ROM-mode session will exercise it.
- The FM-1's ROM-mode port equalling `1-2` is inferred (same physical port).
- The check reads sysfs at one instant; a device replugged between the check and
  the open is only caught by the devnum check where a tool passes one
  (the dev-kit tools do; `fm1_uboot_read` relies on its entry-log path/devnum match).
