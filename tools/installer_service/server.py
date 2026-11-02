# SPDX-License-Identifier: MIT
"""Operator-configured private loopback service. No artifact download or device path."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import subprocess

from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import WorkerTemplate, create_app, create_selected_trio_app
from .build_capabilities import SELECTED_TRIO_PROFILE, check_profile_prerequisites
from .catalogue import load_trusted_catalogue
from .docker_adapter import DockerJobAdapter, DockerWorkerConfig, _IMAGE_ID

ROOT = Path(__file__).resolve().parents[2]
# Necessary, deliberately incomplete startup prerequisites. Lower builders still
# verify full inventories, source freshness, exact receipts and link policy.
NATIVE_PREREQUISITES = (
    "tools/native/Makefile", "firmware/native/app.ld",
    "firmware/native/runtime_mode.h",
    *(f"firmware/third_party/{name}/inventory.json"
      for name in ("dinghy", "compiler-rt", "musl", "printf", "tlsf", "tinf")),
)


@dataclass(frozen=True)
class ServiceConfig:
    source_root: Path
    source_commit: str
    toolchain_root: Path
    catalogue_root: Path
    runtime_root: Path
    enable_private_builds: bool = False


def check_native_prerequisites(root: Path, commit: str) -> None:
    """Refuse incomplete committed sources before admission or worker creation."""
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("source must be pinned to a full Git commit")
    # ls-tree names are bounded by the fixed prerequisite list; ignored local
    # copies cannot make an incomplete Git archive pass this gate.
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-rz", "--name-only", commit,
         "--", *NATIVE_PREREQUISITES], check=True, capture_output=True,
        timeout=10).stdout.decode("utf-8").split("\0")
    if any(relative not in tracked or (root / relative).is_symlink()
           or not (root / relative).is_file() for relative in NATIVE_PREREQUISITES):
        raise ValueError("private native build prerequisites are unavailable; no build service was started")


def check_native_audit(root: Path) -> None:
    """Check required audit capabilities without executing a native tool."""
    path = root / "tools/jieli/audit_link.py"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("private native audit prerequisites are unavailable: audit_link.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    required = {"relative_call_payloads", "stub_call_boundary_patterns"}
    missing = sorted(required - functions.keys())
    audit = functions.get("audit")
    parameters = {arg.arg for arg in audit.args.args} if audit is not None else set()
    missing.extend("audit." + name for name in ("call_payloads", "stub_boundaries")
                   if name not in parameters)
    if not any(isinstance(node, ast.Constant) and node.value == "--objdump"
               for node in ast.walk(tree)):
        missing.append("--objdump")
    if missing:
        raise ValueError("private native audit prerequisites are unavailable: " + ", ".join(missing))


def create_private_app(config: ServiceConfig):
    """Use real fixed adapters only after explicit private operator enablement."""
    if config.enable_private_builds is not True:
        raise ValueError("private builds require explicit operator enablement")
    if config.source_root.resolve(strict=True) != ROOT:
        raise ValueError("service must run from its pinned source checkout")
    check_native_audit(config.source_root)
    check_native_prerequisites(config.source_root, config.source_commit)
    worker = DockerWorkerConfig(
        source_root=config.source_root, source_commit=config.source_commit,
        toolchain_root=config.toolchain_root, catalogue_root=config.catalogue_root,
        runtime_root=config.runtime_root, cpu_limit="4", memory_limit="6g")
    kinds, projects, parents = load_trusted_catalogue(worker.source_root, include_sets=True)
    adapter = DockerJobAdapter(worker, capacity=1)
    app = create_app(adapter=adapter,
                     template=WorkerTemplate(_IMAGE_ID, "private-loopback"),
                     module_kinds=kinds, project_ids=projects, set_parents=parents,
                     queue_cap=1)
    # The loopback service accepts no arbitrary Host (DNS rebinding), no CORS
    # origins, no request-supplied paths/images/commands and no downloads.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    return app



@dataclass(frozen=True)
class SelectedTrioServiceConfig:
    """Operator-owned inputs for the separate offline profile; no CLI activation."""
    source_root: Path
    source_commit: str
    toolchain_root: Path
    toolchain_archive: Path
    cxx_headers: Path
    runtime_root: Path
    enable_private_builds: bool = False


def create_selected_trio_private_app(config: SelectedTrioServiceConfig):
    """Refuse by default; require the selected worker and its trusted callback."""
    if config.enable_private_builds is not True:
        raise ValueError("selected Trio builds require explicit operator enablement")
    if config.source_root.resolve(strict=True) != ROOT:
        raise ValueError("service must run from its pinned source checkout")
    check_native_audit(config.source_root)
    check_profile_prerequisites(config.source_root, config.source_commit, SELECTED_TRIO_PROFILE)
    # A source-only API checkout cannot silently substitute the historical worker.
    if not callable(getattr(DockerJobAdapter, "verify_selected_trio_result", None)):
        raise ValueError("selected Trio worker prerequisites are unavailable")
    worker = DockerWorkerConfig(source_root=config.source_root,
        source_commit=config.source_commit, toolchain_root=config.toolchain_root,
        toolchain_archive=config.toolchain_archive, cxx_headers=config.cxx_headers,
        runtime_root=config.runtime_root, profile_id=SELECTED_TRIO_PROFILE,
        cpu_limit="4", memory_limit="6g")
    adapter = DockerJobAdapter(worker, capacity=1)
    return create_selected_trio_app(adapter=adapter,
        template=WorkerTemplate(_IMAGE_ID, "private-loopback"),
        source_commit=config.source_commit, source_tree_oid=worker.source_tree_oid,
        verify_result=adapter.verify_selected_trio_result, enable_private_builds=True,
        queue_cap=1)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--enable-private-builds", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        app = create_private_app(ServiceConfig(
            ROOT, args.source_commit, args.toolchain, args.catalogue,
            args.runtime, args.enable_private_builds))
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        parser.exit(2, "private service unavailable: " + str(error) + "\n")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1,
                proxy_headers=False, server_header=False)
    return 0
