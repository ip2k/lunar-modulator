#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect pinned demo-project sources and emit a non-admitting preload catalogue.

This inventory deliberately does not alter the production image catalogue.  It
reads source blobs with ``git show`` so it can inspect demo assets that are not
yet materialized on the installable branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import PurePosixPath
from typing import Any


ORIGINALS = {
    "category": "legacy-example",
    "branch": "feature/2026-10-10@demo-songs",
    "manifest_commit": "05a8740943e2a158c068ad7a71c862fd5a02f996",
    "manifest_path": "sim/web/test/demo-songs.json",
    "asset_commit": "3e6eaa5fea7a38822b60a2a742af4b932856b8cc",
    "receipt_commit": "53cd518c417adf34a91b8032de3357d8d9801f0e",
    "receipt_path": "notes/data/2026-10-10-demo-song-round-5-runtime.json",
    "owner_disposition": "rejected as showcases; retained as legacy examples",
}

REPLACEMENTS = {
    "category": "replacement-showcase-candidate",
    "branch": "chore/2026-10-10@demo-song-acceptance",
    "manifest_commit": "fb92cc0d4c312bbc77866c915d6fb8f159f5f92d",
    "manifest_path": "sim/web/test/showcase-songs.json",
    "asset_commit": "fb92cc0d4c312bbc77866c915d6fb8f159f5f92d",
    # This receipt predates the serialization-only Packet/Satellite repair.
    "receipt_commit": "54246b65",
    "receipt_path": "notes/2026-10-11-four-showcase-integration-0085f2f2/aeon-runtime.json",
    "owner_disposition": "showcase candidate; owner musical acceptance pending",
}

GROUPS = (ORIGINALS, REPLACEMENTS)


class CatalogueError(RuntimeError):
    """Raised when a pinned source or manifest cannot be verified."""


def _git_blob(repo: str, revision: str, path: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", repo, "show", f"{revision}:{path}"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise CatalogueError(f"cannot read {revision}:{path}: {detail}") from exc


def _json_blob(repo: str, revision: str, path: str) -> Any:
    try:
        return json.loads(_git_blob(repo, revision, path))
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"invalid JSON in {revision}:{path}: {exc}") from exc


def _slug(title: str) -> str:
    return "-".join(title.lower().replace("&", "and").split())


def _module_dependencies(project: dict[str, Any]) -> dict[str, list[str]]:
    sound = set()
    audio_fx = set()
    midi_fx = set()
    for unit in project.get("sounds", []):
        if unit.get("engine"):
            sound.add(unit["engine"])
        audio_fx.update(
            item["engine"] for item in unit.get("inserts", [])
            if isinstance(item, dict) and item.get("engine")
        )
        midi_fx.update(
            item["engine"] for item in unit.get("midi_fx", [])
            if isinstance(item, dict) and item.get("engine")
        )
    master_fx = {
        item["engine"] for item in project.get("master", [])
        if isinstance(item, dict) and item.get("engine")
    }
    modulation = {
        item["kind"] for item in project.get("mod", {}).get("rack", [])
        if isinstance(item, dict) and item.get("kind")
    }
    return {
        # These are project-file engine identifiers, not canonical module IDs.
        # Image admission must resolve them against the registry and packed image.
        "sound_engines": sorted(sound),
        "audio_effects": sorted(audio_fx),
        "master_effects": sorted(master_fx),
        "midi_effects": sorted(midi_fx),
        "modulation_modules": sorted(modulation),
    }


def _receipt_for(repo: str, group: dict[str, str], title: str, asset_sha: str) -> dict[str, Any]:
    try:
        receipt = _json_blob(repo, group["receipt_commit"], group["receipt_path"])
    except CatalogueError:
        return {"status": "unavailable", "duration_seconds": None}
    song = next((row for row in receipt.get("songs", []) if row.get("title") == title), None)
    if song is None:
        return {"status": "missing-song", "duration_seconds": None}
    receipt_sha = song.get("projectSha256")
    if receipt_sha != asset_sha:
        return {
            "status": "stale-asset-hash",
            "receipt_asset_sha256": receipt_sha,
            "duration_seconds": None,
            "receipt_commit": group["receipt_commit"],
            "receipt_path": group["receipt_path"],
        }
    duration = song.get("durationSeconds", song.get("duration"))
    if duration is None:
        frames = song.get("native", {}).get("frames")
        rate = receipt.get("rate")
        if frames is not None and rate:
            duration = frames / rate
    return {
        "status": "exact-asset-match",
        "receipt_asset_sha256": receipt_sha,
        "duration_seconds": duration,
        "receipt_commit": group["receipt_commit"],
        "receipt_path": group["receipt_path"],
    }


def build_catalogue(repo: str) -> dict[str, Any]:
    candidates = []
    for group in GROUPS:
        manifest = _json_blob(repo, group["manifest_commit"], group["manifest_path"])
        for row in manifest:
            title = row["title"]
            filename = PurePosixPath(row["file"]).name
            asset_path = f"engines/state/examples/{filename}"
            raw = _git_blob(repo, group["asset_commit"], asset_path)
            asset_sha = hashlib.sha256(raw).hexdigest()
            try:
                project = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CatalogueError(f"invalid project JSON in {group['asset_commit']}:{asset_path}") from exc
            receipt = _receipt_for(repo, group, title, asset_sha)
            local_asset = os.path.join(repo, asset_path)
            materialized = os.path.isfile(local_asset)
            local_sha = None
            if materialized:
                with open(local_asset, "rb") as stream:
                    local_sha = hashlib.sha256(stream.read()).hexdigest()
            bpm = row["bpm"]
            bars = row["bars"]
            candidates.append({
                "id": f"{group['category']}-{_slug(title)}",
                "title": title,
                "category": group["category"],
                "source": {
                    "branch": group["branch"],
                    "manifest_commit": group["manifest_commit"],
                    "manifest_path": group["manifest_path"],
                    "asset_commit": group["asset_commit"],
                    "asset_path": asset_path,
                    "sha256": asset_sha,
                    "materialized_in_current_checkout": materialized,
                    "materialized_sha256": local_sha,
                    "materialized_exact_source": local_sha == asset_sha if materialized else False,
                },
                "duration": {
                    "bpm": bpm,
                    "bars": bars,
                    "scenes": row["scenes"],
                    # Four beats/bar is the sequencer's current song convention.
                    "nominal_seconds_from_manifest": round(bars * 4 * 60 / bpm, 6),
                    "runtime_receipt": receipt,
                },
                "module_dependencies": _module_dependencies(project),
                "dependency_scan_complete": False,
                "dependency_identifier_kind": "raw-project-engine-identifiers",
                "dependency_admission_requires": [
                    "resolve project engine identifiers through the canonical registry",
                    "verify exact embedded module data and linked image profile with the packed-image decoder",
                ],
                "owner_disposition": (
                    "owner-approved musical full-song default; native playback and release admission pending"
                    if group is REPLACEMENTS and title == "Event Horizon"
                    else group["owner_disposition"]
                ),
                "default_candidate": False,
                "admission": {
                    "catalogue_only": True,
                    "blocked_on_exact_asset_embedding_and_link_fit": True,
                    "blocked_on_owner_musical_acceptance": not (
                        group is REPLACEMENTS and title == "Event Horizon"
                    ),
                    "blocked_on_native_full_song_playback_and_save_reload": True,
                },
            })
    return {
        "schema": "lunar-demo-preload-candidates/v1",
        "production_catalogue_changed": False,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Git repository containing the pinned source commits")
    args = parser.parse_args()
    try:
        print(json.dumps(build_catalogue(args.repo), indent=2, sort_keys=True))
    except CatalogueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
