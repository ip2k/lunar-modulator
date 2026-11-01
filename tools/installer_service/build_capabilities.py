# SPDX-License-Identifier: MIT
"""Source-only profile declarations. Nothing here enables a build service."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

SELECTED_TRIO_PROFILE = "sdk-free-selected-trio-offline-diagnostic-v1"
SELECTED_TRIO_PREREQUISITES = (
    "tools/native/build_diagnostic.py", "tools/native/build_selected_trio_diagnostic.py",
    "tools/native/prepare_selected_project.py", "tools/jieli/audit_link.py",
    "tools/jieli/objects.mk", "engines/Makefile", "sim/web/mk/sim.mk",
    "engines/state/examples/init-starters/trio-init.lunar",
    "firmware/native/selected_project.c", "firmware/native/selected_project.h",
    "firmware/native/selected_diagnostic_app.c", "firmware/native/diagnostic_api.h",
    "firmware/native/diagnostic_platform.c", "firmware/native/diagnostic_crt0.S",
    "firmware/native/diagnostic.ld",
    *(f"firmware/third_party/{name}/inventory.json"
      for name in ("dinghy", "compiler-rt", "musl", "printf")),
)


def selected_trio_capability() -> dict:
    """Describe this contract, without advertising an operational capability."""
    return dict(schema=1, request_version=2, profile_id=SELECTED_TRIO_PROFILE,
                runtime_mode="offline", flash_layout="stock-sized-diagnostic",
                service_enabled=False, native_build_verified=False,
                rom_return=False, installable=False, release_admitted=False,
                hardware_admitted=False, hardware_tested=False,
                distribution_admitted=False, internal_dependencies=["arp"])


def check_profile_prerequisites(root: Path, commit: str, profile_id: str) -> None:
    """Check this committed source closure only; not runtime or service admission.

    The legacy launcher's prerequisite list and refusal are deliberately separate.
    Full inventories, external inputs, toolchain and receipt checks remain required.
    """
    if profile_id != SELECTED_TRIO_PROFILE or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("unsupported pinned offline profile")
    root = Path(root).resolve(strict=True)
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-rz", "--name-only", commit,
         "--", *SELECTED_TRIO_PREREQUISITES], check=True, capture_output=True,
        timeout=10).stdout.decode("utf-8").split("\0")
    for relative in SELECTED_TRIO_PREREQUISITES:
        path = root / relative
        if (relative not in tracked or not path.is_file()
                or any(part.is_symlink() for part in (path, *path.parents) if part != root)):
            raise ValueError("selected Trio committed source prerequisites are unavailable")
        expected = subprocess.run(
            ["git", "-C", str(root), "show", commit + ":" + relative],
            check=True, capture_output=True, timeout=10).stdout
        if path.read_bytes() != expected:
            raise ValueError("selected Trio source differs from pinned commit")
