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
    _linked_object_manifest,
    _source_manifest,
    _verify_catalogue_subset,
    _toolchain_manifest,
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


def test_linked_object_inventory_rehashes_catalogue_and_generated_rows(tmp_path):
    catalogue = tmp_path / "catalogue"
    output = tmp_path / "output"
    (catalogue / "shard/obj").mkdir(parents=True)
    (output / "link/generated").mkdir(parents=True)
    cat = catalogue / "shard/obj/a.o"
    gen = output / "link/generated/b.o"
    cat.write_bytes(b"catalogue-object")
    gen.write_bytes(b"generated-object")
    verification = {
        "catalogue_objects": [{"path": "/catalogue/shard/obj/a.o", "sha256": sha(cat.read_bytes())}],
        "linked_objects": [
            {"path": "/catalogue/shard/obj/a.o", "sha256": sha(cat.read_bytes())},
            {"path": "/out/build/link/generated/b.o", "sha256": sha(gen.read_bytes())},
        ],
    }
    manifest = _linked_object_manifest(output, catalogue, verification)
    assert json.loads(manifest)["objects"] == [
        {"path": "/catalogue/shard/obj/a.o", "sha256": sha(cat.read_bytes())},
        {"path": "/out/build/link/generated/b.o", "sha256": sha(gen.read_bytes())},
    ]

    gen.write_bytes(b"mutated")
    with pytest.raises(ValueError, match="differ from the build receipt"):
        _linked_object_manifest(output, catalogue, verification)


def test_linked_object_inventory_rejects_duplicate_rows_and_unknown_catalogue_objects(tmp_path):
    catalogue = tmp_path / "catalogue"
    output = tmp_path / "output"
    (catalogue / "a").mkdir(parents=True)
    (catalogue / "a/obj.o").write_bytes(b"x")
    row = {"path": "/catalogue/a/obj.o", "sha256": sha(b"x")}
    with pytest.raises(ValueError, match="duplicate linked object"):
        _linked_object_manifest(output, catalogue, {"catalogue_objects": [row], "linked_objects": [row, row]})
    with pytest.raises(ValueError, match="absent from catalogue receipt"):
        _linked_object_manifest(output, catalogue, {"catalogue_objects": [], "linked_objects": [row]})
    generated = output / "link/obj.o"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"generated")
    wrong_prefix = {"path": "/out/attacker/link/obj.o", "sha256": sha(b"generated")}
    with pytest.raises(ValueError, match="outside the fixed mounts"):
        _linked_object_manifest(output, catalogue, {"catalogue_objects": [], "linked_objects": [wrong_prefix]})


def test_catalogue_selected_rows_must_match_the_complete_snapshot():
    tree = canonical({"schema": 1, "objects": [
        {"path": "engine.o", "kind": "file", "sha256": sha(b"engine")},
        {"path": "unused.o", "kind": "file", "sha256": sha(b"unused")},
    ]})
    selected = canonical({"schema": 1, "objects": [
        {"path": "/catalogue/engine.o", "sha256": sha(b"engine")},
    ]})
    _verify_catalogue_subset(tree, selected)
    changed = canonical({"schema": 1, "objects": [
        {"path": "/catalogue/engine.o", "sha256": sha(b"other")},
    ]})
    with pytest.raises(ValueError, match="subset of the immutable snapshot"):
        _verify_catalogue_subset(tree, changed)


def test_full_tree_manifest_binds_directory_modes_and_contents(tmp_path):
    from shutil import copytree
    root = tmp_path / "catalogue"
    (root / "empty").mkdir(parents=True)
    (root / "obj.o").write_bytes(b"object")
    copied = tmp_path / "copy"
    copytree(root, copied, symlinks=True)
    assert _toolchain_manifest(root) == _toolchain_manifest(copied)
    (copied / "obj.o").write_bytes(b"changed")
    assert _toolchain_manifest(root) != _toolchain_manifest(copied)
    (copied / "obj.o").write_bytes(b"object")
    (copied / "empty").chmod(0o700)
    assert _toolchain_manifest(root) != _toolchain_manifest(copied)


def test_full_tree_manifest_entry_cap_accepts_8192_and_rejects_8193(tmp_path):
    import capture_trusted_build_tuple as capture
    root = tmp_path / "bounded-tree"
    root.mkdir()
    for index in range(capture.MAX_TREE_ENTRIES - 1):
        (root / f"entry-{index:04}.bin").write_bytes(b"x")
    manifest = json.loads(capture._toolchain_manifest(root))
    assert len(manifest["objects"]) == capture.MAX_TREE_ENTRIES

    (root / f"entry-{capture.MAX_TREE_ENTRIES - 1:04}.bin").write_bytes(b"x")
    with pytest.raises(ValueError, match="tree exceeds the fixed manifest bounds"):
        capture._toolchain_manifest(root)


def test_selection_receipt_requires_exact_prepared_build_inputs_status():
    from capture_trusted_build_tuple import _verify_selection_receipt
    image = {
        "prepared_profile_sha256": "a" * 64,
        "selected_content": [{"kind": "project", "id": "demo"}],
        "startup_project_id": "demo",
        "set_ids": [],
    }
    selection = {
        "version": 1,
        "status": "prepared-build-inputs",
        "prepared_profile_sha256": image["prepared_profile_sha256"],
        "selected_content": image["selected_content"],
        "startup_project_id": image["startup_project_id"],
        "set_ids": image["set_ids"],
        "request_sha256": "b" * 64,
    }
    _verify_selection_receipt(selection, image, "b" * 64)
    for bad_status in ("prepared", "linked-private-continuous", "prepared-other"):
        changed = dict(selection, status=bad_status)
        with pytest.raises(ValueError, match="selection receipt differs"):
            _verify_selection_receipt(changed, image, "b" * 64)
    with pytest.raises(ValueError, match="selection receipt differs"):
        _verify_selection_receipt(dict(selection, version=True), image, "b" * 64)



def test_app_receipts_bind_exact_bytes_without_duplicate_verification_size():
    from capture_trusted_build_tuple import _verify_app_receipts
    app, elf = b"app-bytes", b"elf-bytes"
    expected_app = sha(app)
    expected_elf = sha(elf)
    image = {"app_sha256": expected_app, "app_bytes": len(app), "elf_sha256": expected_elf}
    artifact = dict(image)
    verification = {"elf_sha256": expected_elf}

    # The retained producer's verification.json binds the ELF but has no app_bytes field.
    assert _verify_app_receipts(image, artifact, verification, app, elf) == (expected_app, expected_elf)

    for image_receipt, artifact_receipt in (
        (dict(image, app_sha256="0" * 64), artifact),
        (dict(image, app_bytes=len(app) + 1), artifact),
        (image, dict(artifact, app_sha256="0" * 64)),
        (image, dict(artifact, app_bytes=len(app) + 1)),
    ):
        with pytest.raises(ValueError, match="does not bind exact app and ELF bytes"):
            _verify_app_receipts(image_receipt, artifact_receipt, verification, app, elf)
    with pytest.raises(ValueError, match="does not bind exact ELF/app length"):
        _verify_app_receipts(image, artifact, {"elf_sha256": "0" * 64}, app, elf)
