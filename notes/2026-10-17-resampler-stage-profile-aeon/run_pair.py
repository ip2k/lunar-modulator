#!/usr/bin/env python3
"""Build matched schema-7 control and schema-9+IRQ profile from one exact source SHA.

This runs only offline target catalogue/link checks on Aeon. It does not package,
flash, contact hardware, or claim profiling overhead acceptance. The control and
profile differ in the catalogue resampler-stage define and in the linked IRQ +
resampler diagnostic flags; this is a profiling-package comparison, not a pure
resampler-hook comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

SOURCE_COMMIT = "36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f"
RUNNER_SHA = "60448560af6f6bbe479a1510b1af4e4cd84e6186f3d01fdd0e0f61425915f446"
FROZEN_AEON_RUNNER_SHA = "41d1b44b5f7dd303f5d44b4c19fa693b076d26d88abd5d93eaa4d778e661c808"
RECEIPT_SHA = "6db18a773eeb48cd18b64d1d01ad184b6a691182f5800bf9e727f2cafcc0fd56"
STAGE7 = Path("/home/claude/mvave-fm1/resampler-fullfit-frozen-20261016")
SNAPSHOTS = Path("/home/claude/mvave-fm1/resampler-fullfit-exact-snapshots-20261016")
EXCHANGE = Path("/home/claude/.local/share/codex-repos/lunar.git")
CLAIM = Path("/home/claude/.local/share/codex-coordination/claims/lunar--resampler-stage-profile-aeon-20261017-codex")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux" or not (CLAIM / "owner.md").is_file():
        raise RuntimeError("Aeon Linux and acquired task claim are required")
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("choose a fresh explicit output directory")
    stage_runner = STAGE7 / "run-build.py"
    receipt_path = STAGE7 / "output/frozen-build-input-receipt.json"
    frozen_runner = Path(__file__).with_name("frozen-run_aeon-stage7.py")
    runner_path = Path(__file__).with_name("run_aeon_stage9.py")
    if (sha(stage_runner) != RUNNER_SHA
            or sha(frozen_runner) != FROZEN_AEON_RUNNER_SHA):
        raise RuntimeError("reviewed stage-7 runner input differs from external pin")
    if sha(receipt_path) != RECEIPT_SHA:
        raise RuntimeError("stage-7 frozen build receipt differs from external pin")
    original = json.loads(receipt_path.read_text())
    for name, digest in original["outputs"].items():
        if sha(STAGE7 / "output" / name) != digest:
            raise RuntimeError("retained stage-7 output hash mismatch: " + name)
    profile_sha = original["prepared_profile_sha256"]
    selection_sha = original["selection_sha256"]
    if sha(SNAPSHOTS / "prepared/profile.json") != profile_sha or sha(SNAPSHOTS / "selection.json") != selection_sha:
        raise RuntimeError("frozen prepared profile or selection differs from original receipt")

    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("stage9_runner", runner_path)
    runner = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(runner)
    toolchain_manifest = runner.tree_manifest(SNAPSHOTS / "toolchain")
    if runner.sha_bytes(toolchain_manifest) != original["toolchain_snapshot_tree_manifest_sha256"]:
        raise RuntimeError("frozen target compiler/toolchain tree differs from stage-7 receipt")
    if runner.link_args(profile_sha, False) != runner.link_args(profile_sha, True)[:
            len(runner.link_args(profile_sha, False))]:
        raise RuntimeError("schema-9 enabled app flags are not an append-only profile delta")
    base_catalogue = runner.catalogue_args(0, False)
    enabled_catalogue = runner.catalogue_args(0, True)
    if enabled_catalogue != base_catalogue + ["--resampler-stage-profile"]:
        raise RuntimeError("schema-9 catalogue flag delta is not exactly the opt-in profile flag")

    git = ["git", "--git-dir=" + str(EXCHANGE)]
    actual_tree = subprocess.check_output(git + ["show", SOURCE_COMMIT + "^{tree}"], text=True).strip()
    if len(actual_tree) != 40:
        raise RuntimeError("exact target source commit is absent from Aeon exchange")
    output.mkdir(parents=True, mode=0o700)
    checkout = output / "source-checkout"
    subprocess.run(git + ["worktree", "add", "--detach", str(checkout), SOURCE_COMMIT], check=True)
    command_base = [sys.executable, str(runner_path), "--checkout", str(checkout),
        "--commit", SOURCE_COMMIT, "--toolchain", str(SNAPSHOTS / "toolchain"),
        "--headers", str(SNAPSHOTS / "headers"), "--prepared-profile", str(SNAPSHOTS / "prepared"),
        "--selection", str(SNAPSHOTS / "selection.json"),
        "--expected-profile-sha256", profile_sha, "--expected-selection-sha256", selection_sha]
    pair = {
        "schema": 1, "source_commit": SOURCE_COMMIT, "source_tree": actual_tree,
        "host": "aeon", "stage7_runner_sha256": sha(stage_runner),
        "frozen_aeon_runner_sha256": sha(frozen_runner), "stage7_receipt_sha256": sha(receipt_path),
        "schema7_disabled_flags": {"diagnostic_irq_profile": False,
            "diagnostic_resampler_stage_profile": False, "catalogue_resampler_stage_profile": False},
        "schema9_enabled_flags": {"diagnostic_irq_profile": True,
            "diagnostic_resampler_stage_profile": True, "catalogue_resampler_stage_profile": True},
        "comparison_scope": "profiling package delta; IRQ and resampler-stage flags differ, not resampler-only overhead",
        "prepared_profile_sha256": profile_sha, "selection_sha256": selection_sha,
        "hardware_tested": False, "runtime_performance_proven": False, "results": {},
    }
    (output / "pair-input.json").write_text(json.dumps(pair, indent=2) + "\n")
    for label, enabled in (("schema7-control", False), ("schema9-enabled", True)):
        out = output / label
        command = command_base + ["--output", str(out)]
        if enabled:
            command.append("--resampler-stage-profile")
        (output / (label + "-command.json")).write_text(json.dumps(command, indent=2) + "\n")
        with (output / (label + ".log")).open("wb") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=7200)
        receipt = out / "frozen-build-input-receipt.json"
        data = json.loads(receipt.read_text())
        if data["source_commit"] != SOURCE_COMMIT or data["prepared_profile_sha256"] != profile_sha:
            raise RuntimeError(label + " receipt source/profile mismatch")
        expected_flags = pair["schema9_enabled_flags" if enabled else "schema7_disabled_flags"]
        if data.get("profile_flags") != expected_flags:
            raise RuntimeError(label + " receipt profile flag mismatch")
        pair["results"][label] = {"receipt_sha256": sha(receipt), "outputs": data["outputs"],
                                  "catalogue_container_policy": data["catalogue_container_policy"],
                                  "link_container": data["link_container"],
                                  "link_command": data["link_command"]}
        (output / "pair-result.json").write_text(json.dumps(pair, indent=2) + "\n")


if __name__ == "__main__":
    main()
