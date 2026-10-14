import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
sys.path.insert(0, str(ROOT))

from capture_trusted_build_tuple import (
    _catalogue_manifest,
    _source_manifest,
    canonical,
    sha,
)
from build_demo_image import (
    SHAPES8_WAVETABLE_PROFILE,
    build_selection,
)


def test_source_manifest_binds_clean_tracked_bytes_and_rejects_dirty_tree(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tracked.txt").write_bytes(b"source")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "-qm", "fixture"], check=True)

    commit, manifest = _source_manifest(tmp_path)
    decoded = json.loads(manifest)
    assert decoded == {
        "schema": 1,
        "commit": commit,
        "objects": [{"path": "tracked.txt", "sha256": sha(b"source")}],
    }
    assert manifest == canonical(decoded)

    (tmp_path / "tracked.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="must be clean"):
        _source_manifest(tmp_path)


def test_catalogue_manifest_rehashes_exact_receipt_inventory(tmp_path):
    obj = tmp_path / "shard-00/obj/module.o"
    obj.parent.mkdir(parents=True)
    obj.write_bytes(b"object")
    verification = {"catalogue_objects": [{
        "path": "/catalogue/shard-00/obj/module.o",
        "sha256": sha(b"object"),
    }]}
    manifest = _catalogue_manifest(tmp_path, verification)
    assert manifest == canonical({
        "schema": 1,
        "objects": [{
            "path": "/catalogue/shard-00/obj/module.o",
            "sha256": sha(b"object"),
        }],
    })

    obj.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        _catalogue_manifest(tmp_path, verification)



def test_unsupported_runtime_is_refused_before_creating_build_output(tmp_path):
    output = tmp_path / "should-not-exist"
    with pytest.raises(ValueError, match="Unsupported private runtime mode"):
        build_selection(
            {}, "unused-state-tool", "unused-toolchain", "unused-catalogue", output,
            runtime_mode="unbounded",
        )
    assert not output.exists()


def test_continuous_runtime_is_explicit_and_still_not_an_admission():
    from test_native_demo_image_controller import inputs
    receipt = __import__("build_demo_image").checked_link_receipt(
        *inputs("continuous"), runtime_mode="continuous")
    assert receipt["runtime_configuration"]["runtime_mode"] == "continuous"
    assert receipt["runtime_configuration"]["return_to_rom_seconds"] is None
    assert receipt["installable"] is False
    assert receipt["hardware_admitted"] is False
