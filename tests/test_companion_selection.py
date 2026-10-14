"""Trusted SET parent metadata is derived from the prepared selection receipt."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
from companion_selection import companion_parent_indices
from embed_image_content import content_source

PROFILE = "a" * 64

def fixture(tmp_path):
    root = tmp_path / "selection"
    prepared = root / "prepared"
    prepared.mkdir(parents=True)
    project = dict(kind="project", source="prepared/project.native", source_sha256="1" * 64,
                   packed="content-00.bin", packed_sha256="2" * 64, bytes=40)
    aset = dict(kind="set", source="prepared/set.native", source_sha256="3" * 64,
                packed="content-01.bin", packed_sha256="4" * 64, bytes=40)
    receipt = dict(version=1, status="prepared-build-inputs", prepared_profile_sha256=PROFILE,
                   installable=False, native_link_verified=False, native_ram_verified=False,
                   hardware_tested=False, project_ids=["event-horizon"], startup_index=0,
                   startup_project_id="event-horizon", set_ids=["event-horizon-companion"],
                   selected_content=[dict(kind="project", id="event-horizon"),
                                     dict(kind="set", id="event-horizon-companion",
                                          parent_project_id="event-horizon")],
                   content=[dict(id="event-horizon", **project),
                            dict(id="event-horizon-companion", parent_project_id="event-horizon", **aset)])
    (root / "selection.json").write_text(json.dumps(receipt))
    profile = dict(content=[project, aset])
    return prepared, profile, receipt

def test_parent_index_from_trusted_selection(tmp_path):
    prepared, profile, _ = fixture(tmp_path)
    parents, digest = companion_parent_indices(prepared, PROFILE, profile, 0)
    assert parents == [-1, 0]
    assert digest == hashlib.sha256((prepared.parent / "selection.json").read_bytes()).hexdigest()

def test_project_only_profile_keeps_legacy_without_receipt(tmp_path):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    profile = dict(content=[dict(kind="project")])
    assert companion_parent_indices(prepared, PROFILE, profile, None) == ([-1], None)

@pytest.mark.parametrize("mutation, startup, message", [
    (lambda receipt: receipt["content"][1].__setitem__("parent_project_id", "other"), 0, "parent"),
    (lambda receipt: receipt.__setitem__("startup_project_id", "other"), 0, "identity"),
    (lambda receipt: receipt.__setitem__("prepared_profile_sha256", "b" * 64), 0, "different"),
    (lambda receipt: receipt["content"][1].__setitem__("packed_sha256", "5" * 64), 0, "identity"),
    (lambda receipt: receipt["content"][1].pop("parent_project_id"), 0, "parent"),
])
def test_malformed_parent_or_profile_binding_refuses(tmp_path, mutation, startup, message):
    prepared, profile, receipt = fixture(tmp_path)
    mutation(receipt)
    (prepared.parent / "selection.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match=message):
        companion_parent_indices(prepared, PROFILE, profile, startup)

def test_missing_receipt_refuses_set_but_wrong_startup_refuses(tmp_path):
    prepared, profile, _ = fixture(tmp_path)
    (prepared.parent / "selection.json").unlink()
    with pytest.raises(ValueError, match="trusted adjacent"):
        companion_parent_indices(prepared, PROFILE, profile, 0)
    _, profile2, _ = fixture(tmp_path / "other")
    with pytest.raises(ValueError, match="Startup project index"):
        companion_parent_indices(tmp_path / "other/selection/prepared", PROFILE, profile2, 2)

def test_embedding_encodes_parent_and_refuses_unknown_set_parent():
    inputs = SimpleNamespace(report=dict(content=[dict(kind="project"), dict(kind="set")]),
                              packed_content=(bytes(40), bytes([1]) * 40))
    source = content_source(inputs, [-1, 0]).decode()
    assert "FM1_STATE_SET" in source and "UINT32_MAX" in source and "0u" in source
    with pytest.raises(ValueError, match="trusted parent"):
        content_source(inputs)
