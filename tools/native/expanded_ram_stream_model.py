#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline pull scheduler for a future RAM-resident expanded-image loader.

This module only serves hash-pinned bytes in bounded chunks. It does not open
USB/MIDI, call a flash HAL, erase/program NOR, stage a loader, or admit a
candidate. A caller must obtain the transport manifest from the guarded
expanded_transport_manifest builder and pin its canonical SHA-256 separately.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jieli"))
import raw_flash_profile as raw
import expanded_flash_profile as expanded

SECTOR_BYTES = 4096
MAX_PULL_BYTES = 512
PROFILE = "expanded-d9000-recorded-092"


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class PullRequest:
    """One exact host-pull response request, not a NOR write command."""
    sequence: int
    sector_offset: int
    image_offset: int
    length: int


class ExpandedRamStreamModel:
    """Serve a verified transport plan as sequential <=512-byte responses.

    The model's input buffers live on the host. A possible target consumer
    would need a separate audited RAM-resident sector erase/program/readback
    implementation; this class deliberately provides none.
    """

    def __init__(self, baseline, target, manifest, expected_manifest_sha256):
        if not isinstance(baseline, bytes) or not isinstance(target, bytes):
            raise ValueError("Immutable complete baseline and target bytes required")
        if len(baseline) != raw.FLASH_BYTES or len(target) != raw.FLASH_BYTES:
            raise ValueError("Exact 1 MiB baseline and target required")
        if not isinstance(manifest, dict):
            raise ValueError("Guarded transport manifest required")
        if (not isinstance(expected_manifest_sha256, str)
                or len(expected_manifest_sha256) != 64
                or any(c not in "0123456789abcdef" for c in expected_manifest_sha256)):
            raise ValueError("Pinned canonical transport-manifest SHA-256 required")
        if _sha256(canonical_json(manifest)) != expected_manifest_sha256:
            raise ValueError("Transport manifest differs from its pinned hash")
        if (manifest.get("schema") != 1
                or manifest.get("status") != "offline-expanded-transport-manifest"
                or manifest.get("profile") != PROFILE
                or manifest.get("target_bytes") != len(target)
                or manifest.get("target_sha256") != _sha256(target)
                or manifest.get("baseline_sha256") != _sha256(baseline)):
            raise ValueError("Transport manifest is stale or targets another image")
        if (manifest.get("geometry_verified") is not True
                or manifest.get("receipt_correspondence_verified") is not True
                or manifest.get("hardware_admitted") is not False
                or manifest.get("physical_writer_ready") is not False
                or manifest.get("settings_migration_verified") is not False
                or manifest.get("recovery_verified") is not False
                or manifest.get("installable") is not False
                or manifest.get("device_io_performed") is not False):
            raise ValueError("Only guarded, explicitly unadmitted offline manifests are accepted")
        if manifest.get("protected_ranges") != [[0, raw.APP_BASE],
                                                  [expanded.AREA_END, raw.FLASH_BYTES]]:
            raise ValueError("Transport manifest protected ranges differ from this profile")
        if (target[:raw.APP_BASE] != baseline[:raw.APP_BASE]
                or target[expanded.AREA_END:] != baseline[expanded.AREA_END:]):
            raise ValueError("Target changes bytes outside the expanded app region")

        changed = [off for off in range(raw.APP_BASE, expanded.AREA_END, SECTOR_BYTES)
                   if baseline[off:off + SECTOR_BYTES] != target[off:off + SECTOR_BYTES]]
        ordered = [off for off in changed if off != raw.APP_BASE] + [raw.APP_BASE]
        if (not changed
                or manifest.get("changed_sectors") != changed
                or manifest.get("sector_order") != ordered
                or manifest.get("directory_sector") != raw.APP_BASE):
            raise ValueError("Manifest sector plan differs from image bytes or directory-last policy")
        for off in ordered:
            if (type(off) is not int or off % SECTOR_BYTES
                    or off < raw.APP_BASE or off + SECTOR_BYTES > expanded.AREA_END):
                raise ValueError("Manifest contains an out-of-profile sector")

        self._target = target
        self._sector_order = tuple(ordered)
        self._requests = tuple(
            PullRequest(sequence, sector, sector + within,
                        min(MAX_PULL_BYTES, SECTOR_BYTES - within))
            for sequence, (sector, within) in enumerate(
                ( (sector, within) for sector in ordered
                  for within in range(0, SECTOR_BYTES, MAX_PULL_BYTES) )))
        self._cursor = 0

    @property
    def sector_order(self):
        """The exact planned order; the app directory sector is last."""
        return self._sector_order

    @property
    def complete(self):
        return self._cursor == len(self._requests)

    @property
    def max_response_bytes(self):
        return MAX_PULL_BYTES

    def next_request(self):
        """Return the one outstanding request, or None when all data was served."""
        if self.complete:
            return None
        return self._requests[self._cursor]

    def respond(self, request):
        """Return the expected bounded bytes; reject replay/reorder/arbitrary offsets."""
        if self.complete or request != self._requests[self._cursor]:
            raise ValueError("Pull request is not the next authorized stream chunk")
        expected = self._requests[self._cursor]
        data = self._target[expected.image_offset:expected.image_offset + expected.length]
        if len(data) != expected.length:
            raise ValueError("Truncated source image")
        self._cursor += 1
        return data
