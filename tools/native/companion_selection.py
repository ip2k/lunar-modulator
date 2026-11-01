# SPDX-License-Identifier: MIT
"""Verify prepared SET-to-parent bindings before native catalogue generation."""
import json
from pathlib import Path

try:
    from .prepare_image_profile import bounded_read, sha, unique_object
except ImportError:  # Script execution from tools/native.
    from prepare_image_profile import bounded_read, sha, unique_object

MAX_RECEIPT = 1048576

def companion_parent_indices(prepared_dir, expected_profile_sha256, profile_report, startup_project_index, *, allow_unbound_sets=False):
    """Return one parent catalogue index per asset; projects use -1.

    Standalone SET startup has no parent project. Callers must opt into that
    legacy mode explicitly; project-startup companion SETs remain receipt-bound.
    """
    assets = profile_report.get("content")
    if not isinstance(assets, list) or len(assets) > 64:
        raise ValueError("Prepared profile content is malformed")
    parents = [-1] * len(assets)
    set_positions = [i for i, row in enumerate(assets)
                     if isinstance(row, dict) and row.get("kind") == "set"]
    if not set_positions:
        return parents, None
    if startup_project_index is None and allow_unbound_sets:
        return parents, None
    if type(startup_project_index) is not int or startup_project_index < 0:
        raise ValueError("Companion SETs require a selected parent project")
    prepared_dir = Path(prepared_dir).resolve()
    receipt_path = prepared_dir.parent / "selection.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError("Companion SETs require the trusted adjacent selection receipt")
    raw = bounded_read(receipt_path, MAX_RECEIPT)
    receipt = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(receipt, dict) or receipt.get("version") != 1 or receipt.get("status") != "prepared-build-inputs":
        raise ValueError("Unsupported companion selection receipt")
    for name in ("installable", "native_link_verified", "native_ram_verified", "hardware_tested"):
        if receipt.get(name) is not False:
            raise ValueError("Selection receipt has an invalid admission flag: " + name)
    if receipt.get("prepared_profile_sha256") != expected_profile_sha256:
        raise ValueError("Selection receipt refers to a different prepared profile")
    ids = receipt.get("project_ids")
    selected = receipt.get("selected_content")
    receipt_assets = receipt.get("content")
    startup_id = receipt.get("startup_project_id")
    startup_index = receipt.get("startup_index")
    set_ids = receipt.get("set_ids")
    if (not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids)
            or len(set(ids)) != len(ids) or type(startup_index) is not int
            or not 0 <= startup_index < len(ids) or ids[startup_index] != startup_id
            or not isinstance(set_ids, list) or any(not isinstance(x, str) or not x for x in set_ids)
            or len(set(set_ids)) != len(set_ids) or not isinstance(selected, list)
            or not isinstance(receipt_assets, list) or len(selected) != len(assets)
            or len(receipt_assets) != len(assets)):
        raise ValueError("Selection receipt identity or ordering is malformed")
    if startup_project_index != startup_index:
        raise ValueError("Startup project index differs from the prepared selection")
    if not isinstance(selected[startup_index], dict) or selected[startup_index].get("kind") != "project" or selected[startup_index].get("id") != startup_id:
        raise ValueError("Selected startup project does not match its identity")
    if len(ids) > len(assets) or [row.get("id") for row in selected[:len(ids)] if isinstance(row, dict)] != ids:
        raise ValueError("Prepared project ordering differs from selection receipt")
    if [row.get("id") for row in selected[len(ids):] if isinstance(row, dict)] != set_ids:
        raise ValueError("Prepared SET ordering differs from selection receipt")
    set_by_id = {row.get("id"): row for row in selected[len(ids):] if isinstance(row, dict)}
    if set(set_by_id) != set(set_ids):
        raise ValueError("SET identity list differs from selected content")
    asset_parent = {}
    for i, (prepared, selected_row, receipt_row) in enumerate(zip(assets, selected, receipt_assets)):
        if not all(isinstance(row, dict) for row in (prepared, selected_row, receipt_row)):
            raise ValueError("Selection content row is malformed")
        if selected_row.get("kind") != prepared.get("kind") or receipt_row.get("kind") != prepared.get("kind"):
            raise ValueError("Selection content kind differs from prepared profile")
        for key in ("source", "source_sha256", "packed", "packed_sha256", "bytes"):
            if key in prepared and receipt_row.get(key) != prepared.get(key):
                raise ValueError("Selection content identity differs from prepared profile")
        if selected_row.get("id") != receipt_row.get("id"):
            raise ValueError("Selected content identity differs from prepared receipt")
        if prepared.get("kind") == "set":
            parent = receipt_row.get("parent_project_id")
            if parent != startup_id or selected_row.get("parent_project_id") != startup_id or parent not in ids:
                raise ValueError("Companion SET parent is missing or differs from selected startup")
            if i < len(ids) or i != len(ids) + set_ids.index(receipt_row["id"]):
                raise ValueError("Companion SET catalogue ordering is not canonical")
            parents[i] = ids.index(parent)
            asset_parent[receipt_row["id"]] = parent
        elif prepared.get("kind") != "project":
            raise ValueError("Prepared native content kind is unsupported")
    if set(asset_parent) != set(set_ids):
        raise ValueError("SET parent bindings are incomplete")
    if parents[startup_index] != -1:
        raise ValueError("Startup index must identify a project")
    return parents, sha(raw)


def builder_content_parent_indices(prepared_dir, expected_profile_sha256, profile_report,
                                  startup_project_index, startup_set_index):
    """Choose bound companion or unbound standalone SET catalogue semantics."""
    if startup_project_index is not None and startup_set_index is not None:
        raise ValueError("Standalone SET and PROJECT startup modes are mutually exclusive")
    return companion_parent_indices(
        prepared_dir, expected_profile_sha256, profile_report, startup_project_index,
        allow_unbound_sets=startup_set_index is not None)
