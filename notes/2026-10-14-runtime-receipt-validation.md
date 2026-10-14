# Installer runtime receipt validation

The installer API now validates the worker receipt's runtime configuration against tools/native/runtime_mode.py instead of accepting an arbitrary runtime description. The canonical helper describes diagnostic (20 seconds), song-diagnostic (120 seconds), and continuous; the actual image builder (tools/native/build_demo_image.py:112-115,209-211) permits only the two bounded diagnostic modes. The API therefore accepts only those two modes and requires exactly the canonical fields and values (runtime_mode, return_to_rom_seconds, define, release_accepted). It compares value types as well as values, so true cannot stand in for an integer duration. Missing, extra, malformed, continuous, or internally inconsistent values fail the worker result closed.

The request schema does not select a runtime mode, so this check proves internal receipt consistency, not a binding between a user's request and the runtime mode. Existing admission and hardware-result flags remain required false; this validation does not make artifacts installable or establish hardware acceptance.

Focused checks on Hera used the pinned service-test environment and retained full-song result:

    LUNAR_RETAINED_BUILD=/home/claude/mvave-fm1/fullsong-current-build-20261014/result /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest tests/test_installer_service.py tests/test_native_demo_image_controller.py -q

Result: all focused service and controller tests passed. Coverage includes valid canonical 120-second song diagnostics and refusal of missing config, continuous mode, wrong duration/mode/define, bool-as-duration, release acceptance, and unknown fields. Retained tuple used by the controller tests: app 862296 bytes, SHA-256 b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956; ELF 994540 bytes, SHA-256 f370fdb840b723e78388b81f56a076d30a130ad560485281fbe6c2ad406d294a.

Semantic MCP selection remained on the Mac primary checkout, not this Hera worktree, so this task used direct source inspection and the focused tests; no semantic-index result is claimed. No device, deployment, or installability action was performed. GitHub backup remains with the coordinator after Hera bare-branch handoff.
