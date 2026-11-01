#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and canonicalize a browser-exported firmware build request.

This module only checks request/catalogue consistency. It never builds an
image, creates an installable artifact, or communicates with a device.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, field_validator, model_validator

MAX_REQUEST_BYTES = 65_536
MAX_CATALOGUE_BYTES = 4 * 1024 * 1024
GROUPS = ("engines", "effects", "midi", "modulation")
HALL_O2_STAGE7_REQUIRED_BY_GROUP = {
    "engines": frozenset(("macro", "shapes", "sixop", "drums")),
    "effects": frozenset(("hall",)),
}
GROUP_KINDS = {
    "engines": "sound",
    "effects": "audio_fx",
    "midi": "midi_fx",
    "modulation": "mod",
}


class DuplicateKey(ValueError):
    """Raised when JSON repeats an object key."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def decode_json_object(data: bytes, *, limit: int) -> dict[str, object]:
    """Decode one bounded UTF-8 JSON object, rejecting ambiguous encodings."""
    if len(data) > limit:
        raise ValueError("JSON document is too large")
    decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    if not isinstance(decoded, dict):
        raise ValueError("JSON document must be an object")
    return decoded


def canonical_request(request: dict[str, object]) -> bytes:
    """Match the private API's stable canonical request bytes."""
    normalized = dict(request)
    if normalized.get("set_ids") == []:
        normalized.pop("set_ids")
    return (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class BuildRequest(BaseModel):
    """Pydantic v2 strict schema mirrored from installer_service.api."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: StrictInt = Field(ge=1, le=1)
    engines: list[StrictStr] = Field(min_length=1, max_length=128)
    effects: list[StrictStr] = Field(max_length=128)
    midi: list[StrictStr] = Field(max_length=128)
    modulation: list[StrictStr] = Field(max_length=128)
    project_ids: list[StrictStr] = Field(min_length=1, max_length=8)
    startup_index: StrictInt = Field(ge=0)
    set_ids: list[StrictStr] = Field(default_factory=list, max_length=8)
    # Omitted values keep the API's historical default/canonical semantics.
    flash_layout: Literal["expanded-d9000", "expanded-d7000"] = "expanded-d9000"
    runtime_mode: Literal["diagnostic", "song-diagnostic", "continuous"] = "diagnostic"

    @field_validator("engines", "effects", "midi", "modulation", "project_ids", "set_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("IDs must be unique within each list")
        return values

    @model_validator(mode="after")
    def startup_in_range(self) -> BuildRequest:
        if self.startup_index >= len(self.project_ids):
            raise ValueError("startup_index is outside project_ids")
        if self.flash_layout == "expanded-d7000":
            if self.runtime_mode not in ("song-diagnostic", "continuous"):
                raise ValueError("expanded-d7000 requires song-diagnostic or continuous runtime")
            if self.runtime_mode == "song-diagnostic":
                for group, required in HALL_O2_STAGE7_REQUIRED_BY_GROUP.items():
                    if not required.issubset(getattr(self, group)):
                        raise ValueError("named song diagnostic profile prerequisites are missing")
        elif self.runtime_mode != "diagnostic":
            raise ValueError("legacy expanded-d9000 requests use the bounded diagnostic runtime")
        return self


def _catalogue_indexes(catalogue: dict[str, object]) -> tuple[dict[str, str], set[str], dict[str, str]]:
    """Read the generated catalogue's module, project and companion SET IDs."""
    if type(catalogue.get("version")) is not int or catalogue["version"] != 1:
        raise ValueError("unsupported catalogue version")
    groups = catalogue.get("groups")
    projects = catalogue.get("projects")
    sets = catalogue.get("sets")
    if not isinstance(groups, dict) or set(groups) != set(GROUPS):
        raise ValueError("invalid catalogue groups")
    module_kinds: dict[str, str] = {}
    for group in GROUPS:
        identifiers = groups[group]
        if (not isinstance(identifiers, list) or not identifiers
                or any(not isinstance(identifier, str) or not identifier
                       or identifier.startswith("test-") for identifier in identifiers)
                or len(identifiers) != len(set(identifiers))):
            raise ValueError("invalid catalogue module IDs")
        for identifier in identifiers:
            if identifier in module_kinds:
                raise ValueError("module ID appears in multiple catalogue groups")
            module_kinds[identifier] = GROUP_KINDS[group]

    def rows_by_id(value: object, label: str) -> dict[str, dict[str, object]]:
        if not isinstance(value, list):
            raise ValueError(f"invalid catalogue {label}")
        indexed: dict[str, dict[str, object]] = {}
        for row in value:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                raise ValueError(f"invalid catalogue {label}")
            if row["id"] in indexed:
                raise ValueError(f"duplicate catalogue {label} ID")
            indexed[row["id"]] = row
        return indexed

    project_rows = rows_by_id(projects, "projects")
    set_rows = rows_by_id(sets, "sets")
    parents: dict[str, str] = {}
    for set_id, row in set_rows.items():
        parent = row.get("parent_project_id")
        if not isinstance(parent, str) or parent not in project_rows:
            raise ValueError("invalid catalogue SET parent")
        parents[set_id] = parent
    return module_kinds, set(project_rows), parents


def validate_request(request_data: bytes, catalogue_data: bytes) -> dict[str, object]:
    """Validate bytes against a generated catalogue and return normalized data."""
    decoded = decode_json_object(request_data, limit=MAX_REQUEST_BYTES)
    catalogue = decode_json_object(catalogue_data, limit=MAX_CATALOGUE_BYTES)
    model = BuildRequest.model_validate(decoded)
    normalized = model.model_dump(mode="json", exclude_defaults=True)
    module_kinds, project_ids, set_parents = _catalogue_indexes(catalogue)
    for group in GROUPS:
        if any(identifier.startswith("test-") or module_kinds.get(identifier) != GROUP_KINDS[group]
               for identifier in normalized[group]):
            raise ValueError("request contains an unknown or wrong-group module ID")
    projects = normalized["project_ids"]
    startup = normalized["startup_index"]
    set_ids = normalized.get("set_ids", [])
    if any(project not in project_ids for project in projects):
        raise ValueError("request contains an unknown project ID")
    for set_id in set_ids:
        parent = set_parents.get(set_id)
        if parent is None or parent not in projects or parent != projects[startup]:
            raise ValueError("request SET does not belong to the startup project")
    return normalized


def result_for(request: dict[str, object]) -> dict[str, object]:
    """Build a safe response; validation is not image admission or installability."""
    return {"installable": False, "request": request,
            "canonical_request": canonical_request(request).decode("utf-8")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="browser-exported request JSON")
    parser.add_argument("--catalogue", required=True, type=Path,
                        help="generated image catalogue JSON")
    args = parser.parse_args(argv)
    try:
        with args.request.open("rb") as stream:
            request_data = stream.read(MAX_REQUEST_BYTES + 1)
        with args.catalogue.open("rb") as stream:
            catalogue_data = stream.read(MAX_CATALOGUE_BYTES + 1)
        request = validate_request(request_data, catalogue_data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateKey,
            ValueError, ValidationError, RecursionError):
        print(json.dumps({"valid": False, "installable": False,
                          "error": "invalid request or catalogue"}), file=sys.stderr)
        return 2
    print(json.dumps(result_for(request), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
