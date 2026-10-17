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
    _pinned_source_manifest,
    _source_manifest,
    _verify_catalogue_subset,
    TUPLE_SCHEMA,
    PROVENANCE_SCHEMA,
    _tuple_envelope,
    _toolchain_manifest,
    _generate_wavetables_from_source,
    _verified_generated_inputs,
    _verified_generated_inputs_from_pinned_source,
    canonical,
    sha,
)
from build_demo_image import (
    BASE_INSTANCE_POOL_BYTES,
    CONTINUOUS_TARGET_STORAGE,
    SHAPES8_WAVETABLE_PROFILE,
    build_selection,
)
from module_selection import wavetable_namespaces


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


def test_catalogue_manifest_preserves_and_checks_current_optimization_contract(tmp_path):
    overrides = {"our/src/fx_hall.o": "-O2"}
    payloads = {"our/src/fx_hall.o": b"hall", "our/src/mi_sixop.o": b"sixop"}
    rows = []
    for relative, content in payloads.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        rows.append({"path": "/catalogue/" + relative, "sha256": sha(content),
                     "optimization": overrides.get(relative, "-Oz")})
    receipt = {"catalogue_objects": rows, "catalogue_optimization_overrides": overrides,
               "catalogue_limiter_os": False, "catalogue_hall_o2": True}
    original_rows = json.loads(json.dumps(receipt["catalogue_objects"]))
    manifest = json.loads(_catalogue_manifest(tmp_path, receipt))
    assert manifest["schema"] == 2
    assert manifest["objects"] == sorted(rows, key=lambda row: row["path"])
    assert receipt["catalogue_objects"] == original_rows

    mutations = []
    mutations.append(dict(receipt, catalogue_objects=[dict(rows[0], optimization="-Os"), rows[1]]))
    mutations.append({"catalogue_objects": rows})
    mutations.append(dict(receipt, catalogue_optimization_overrides={"our/src/unknown.o": "-Os"}))
    mutations.append(dict(receipt, catalogue_hall_o2=False))
    mutations.append(dict(receipt, catalogue_objects=[dict(rows[0], optimization="-O3"), rows[1]]))
    mutations.append(dict(receipt, catalogue_objects=[rows[0], dict(rows[1], extra="ignored")]))
    mutations.append(dict(receipt, catalogue_objects=[rows[0], rows[0]]))
    for invalid in mutations:
        with pytest.raises(ValueError):
            _catalogue_manifest(tmp_path, invalid)


def test_catalogue_manifest_rejects_metadata_free_rows_when_overrides_would_be_lost(tmp_path):
    path = tmp_path / "our/src/fx_limit.o"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"limiter")
    receipt = {"catalogue_objects": [{"path": "/catalogue/our/src/fx_limit.o",
                                      "sha256": sha(b"limiter")}],
               "catalogue_optimization_overrides": {"our/src/fx_limit.o": "-Os"},
               "catalogue_limiter_os": True, "catalogue_hall_o2": False}
    with pytest.raises(ValueError, match="cannot discard optimization metadata"):
        _catalogue_manifest(tmp_path, receipt)
    with pytest.raises(ValueError, match="cannot discard optimization metadata"):
        _catalogue_manifest(tmp_path, {"catalogue_objects": receipt["catalogue_objects"],
                                       "catalogue_optimization_overrides": {},
                                       "catalogue_limiter_os": False, "catalogue_hall_o2": False})



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
            {"path": "/output/build/link/generated/b.o", "sha256": sha(gen.read_bytes())},
        ],
    }
    manifest = _linked_object_manifest(output, catalogue, verification)
    assert json.loads(manifest)["objects"] == [
        {"path": "/catalogue/shard/obj/a.o", "sha256": sha(cat.read_bytes())},
        {"path": "/output/build/link/generated/b.o", "sha256": sha(gen.read_bytes())},
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
    wrong_prefix = {"path": "/output/attacker/link/obj.o", "sha256": sha(b"generated")}
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



def test_inspection_mounts_use_exact_sorted_docker_contract():
    from capture_trusted_build_tuple import _verify_inspection_mounts

    rows = [
        {"source": "/workspace-src", "destination": "/workspace", "read_only": True},
        {"source": "/request.json", "destination": "/input/request.json", "read_only": True},
        {"source": "/toolchain", "destination": "/opt/pi32v2", "read_only": True},
        {"source": "/catalogue", "destination": "/catalogue", "read_only": True},
        {"source": "/output", "destination": "/output", "read_only": False},
    ]
    actual = dict(container_name="/lunar-continuous-0123456789abcdef01234567",
                  mounts=sorted(rows, key=lambda row: row["destination"]))
    _verify_inspection_mounts(actual, rows, "lunar-continuous-0123456789abcdef01234567")

    with pytest.raises(ValueError, match="exact name"):
        _verify_inspection_mounts(dict(actual, container_name="lunar-continuous-0123456789abcdef01234567"),
                                  rows, "lunar-continuous-0123456789abcdef01234567")
    with pytest.raises(ValueError, match="exact name"):
        _verify_inspection_mounts(dict(actual, container_name="//lunar-continuous-0123456789abcdef01234567"),
                                  rows, "lunar-continuous-0123456789abcdef01234567")
    with pytest.raises(ValueError, match="exact name"):
        _verify_inspection_mounts(dict(actual, container_name="/lunar-continuous-ffffffffffffffffffffffff"),
                                  rows, "lunar-continuous-0123456789abcdef01234567")

    changed_path = [dict(row) for row in actual["mounts"]]
    changed_path[0]["source"] = "/other/output"
    with pytest.raises(ValueError, match="exact fixed mounts"):
        _verify_inspection_mounts(dict(actual, mounts=changed_path), rows,
                                  "lunar-continuous-0123456789abcdef01234567")
    changed_mode = [dict(row) for row in actual["mounts"]]
    changed_mode[0]["read_only"] = False
    with pytest.raises(ValueError, match="exact fixed mounts"):
        _verify_inspection_mounts(dict(actual, mounts=changed_mode), rows,
                                  "lunar-continuous-0123456789abcdef01234567")


def test_worker_source_and_provenance_have_distinct_invocation_pins(tmp_path):
    from capture_trusted_build_tuple import _read_pinned_worker_source, _verify_worker_bindings

    root = tmp_path / "source"
    source_path = root / "tools/native/trusted_continuous_worker.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"tracked worker source")
    provenance_path = tmp_path / "worker-provenance.json"
    provenance_path.write_bytes(b"{\"request_sha256\":\"fixture\"}")
    invocation = {
        "worker_sha256": sha(source_path.read_bytes()),
        "worker_provenance_sha256": sha(provenance_path.read_bytes()),
    }

    worker_source = _read_pinned_worker_source(root, source_path)
    provenance = provenance_path.read_bytes()
    _verify_worker_bindings(invocation, worker_source, provenance)

    with pytest.raises(ValueError, match="does not bind worker source bytes"):
        _verify_worker_bindings(invocation, b"mutated worker source", provenance)
    with pytest.raises(ValueError, match="does not bind worker provenance bytes"):
        _verify_worker_bindings(invocation, worker_source, b"mutated provenance")

    changed_source_pin = dict(invocation, worker_sha256=sha(b"other source"))
    with pytest.raises(ValueError, match="does not bind worker source bytes"):
        _verify_worker_bindings(changed_source_pin, worker_source, provenance)
    changed_provenance_pin = dict(invocation, worker_provenance_sha256=sha(b"other provenance"))
    with pytest.raises(ValueError, match="does not bind worker provenance bytes"):
        _verify_worker_bindings(changed_provenance_pin, worker_source, provenance)

    with pytest.raises(ValueError, match="pinned source-snapshot member"):
        _read_pinned_worker_source(root, tmp_path / "same-bytes.py")


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


def test_capture_reaches_inspection_after_contract_and_name_validation(monkeypatch):
    """Exercise capture orchestration against retained private inputs without writing a tuple."""
    import capture_trusted_build_tuple as capture

    run_root = Path("/home/claude/.local/share/codex-private/continuous-tuple-20261014/run-298ff12")
    output = run_root / "build-output" / "build"
    invocation_root = run_root / "build-output"
    source = run_root / ".build-output-source-f5c0b2322e130311"
    catalogue = run_root / ".build-output-catalogue-762487aecc203a84"
    toolchain = Path("/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1")
    invocation = invocation_root / "container-invocation.json"
    provenance = invocation_root / "worker-provenance.json"
    wrapper = source / "tools/native/run_trusted_continuous_build.py"
    required = (output, source, catalogue, toolchain, invocation, provenance, wrapper)
    if not all(path.exists() for path in required):
        pytest.skip("retained private continuous-build fixture is unavailable")

    class ReachedInspectionBoundary(Exception):
        pass

    def stop_at_inspection(contract, expected_mounts, container_name):
        assert isinstance(contract, dict)
        assert container_name == "lunar-continuous-9a63f4354d753f89230b3fcd"
        assert {row["destination"] for row in expected_mounts} == {
            "/workspace", "/input/request.json", "/opt/pi32v2", "/catalogue", "/output",
        }
        assert contract["container_name"] == "/" + container_name
        assert contract["mounts"] == sorted(expected_mounts, key=lambda row: row["destination"])
        raise ReachedInspectionBoundary

    monkeypatch.setattr(capture, "_verify_inspection_mounts", stop_at_inspection)
    with pytest.raises(ReachedInspectionBoundary):
        capture.capture_trusted_build_tuple(
            source, catalogue, output, toolchain,
            invocation_path=invocation,
            worker_source_path=source / "tools/native/trusted_continuous_worker.py",
            worker_provenance_path=provenance,
            wrapper_path=wrapper,
        )


def test_tuple_schema_is_v2_while_capture_sidecars_keep_independent_versions():
    assert TUPLE_SCHEMA == 2
    fields = {"schema": 1, "profile_id": "fm1-092-d7000", "installable": False}
    raw = _tuple_envelope(fields, "a" * 64, "b" * 40, "c" * 64, "d" * 64)
    value = json.loads(raw)
    assert raw == canonical(value)
    assert value["schema"] == 2
    assert value["build_provenance_sha256"] == "a" * 64
    assert value["tuple_id"].startswith("continuous-")
    assert value["installable"] is False

    provenance = dict(value)
    provenance["schema"] = PROVENANCE_SCHEMA
    assert provenance["schema"] == 1


def test_tuple_capture_requires_matching_enabled_trs_receipts():
    from copy import deepcopy
    from capture_trusted_build_tuple import _verify_continuous_midi_receipts
    from test_native_demo_image_controller import continuous_inputs
    verification = continuous_inputs()[2]
    image = {'native_midi_input': deepcopy(verification['native_midi_input'])}
    _verify_continuous_midi_receipts(image, verification)
    for field, value in [('enabled', False), ('enabled', 1),
                         ('bytes_per_poll', 64), ('hardware_tested', True)]:
        changed = deepcopy(image)
        changed['native_midi_input'][field] = value
        with pytest.raises(ValueError, match='TRS MIDI'):
            _verify_continuous_midi_receipts(changed, verification)
    with pytest.raises(ValueError, match='TRS MIDI'):
        _verify_continuous_midi_receipts({}, verification)


def _generated_capture_fixture(tmp_path, selected, source_root=ROOT):
    import shutil

    output = tmp_path / "output"
    prepared_dir = output / "selection/prepared"
    link_dir = output / "link"
    (prepared_dir / "modules/gen").mkdir(parents=True)
    (link_dir / "gen").mkdir(parents=True)
    (link_dir / "module-all/gen").mkdir(parents=True)
    (link_dir / "module-selection/gen").mkdir(parents=True)
    header = b"/* selected module header */\n"
    (prepared_dir / "fm1_modules.h").write_bytes(header)
    module_selection = {"selected": selected, "header_sha256": sha(header)}
    for rel in (
        "selection/prepared/modules/gen/fm1_modules.h",
        "link/gen/fm1_modules.h",
        "link/module-all/gen/fm1_modules.h",
        "link/module-selection/gen/fm1_modules.h",
    ):
        path = output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rel.encode("ascii"))

    namespaces = wavetable_namespaces(selected, flash_plaits=False)
    generator_output = tmp_path / "generator-output"
    generator_output.mkdir()
    rows = _generate_wavetables_from_source(source_root, generator_output, namespaces)
    for generated_file in generator_output.iterdir():
        shutil.copy2(generated_file, link_dir / generated_file.name)
    verification = {
        "module_selection": module_selection,
        "compressed_wave_tables": rows,
        "indexed_tft": True,
        "shapes_voices": 8,
        "flash_plaits_wavetables": False,
        "target_app_storage": dict(CONTINUOUS_TARGET_STORAGE),
        "instance_pool_bytes": (BASE_INSTANCE_POOL_BYTES
                                + CONTINUOUS_TARGET_STORAGE["pool_credit_bytes"]
                                - sum(row["raw_bytes"] for row in rows)),
    }
    image = {
        "module_selection": module_selection,
        "wavetable_profile": SHAPES8_WAVETABLE_PROFILE,
        "compressed_wave_tables": rows,
        "shapes_voices": 8,
        "flash_plaits_wavetables": False,
    }
    return output, {"module_selection": module_selection}, image, verification


def _minimal_captured_wavetable_source(tmp_path):
    import shutil

    source_root = tmp_path / "captured-source"
    for relative in (
        "tools/native/prepare_wavetables.py",
        "tools/native/evaluate_wavetables.py",
        "engines/third_party/mutable/plaits/resources.cc",
        "engines/third_party/mutable/plaits/resources.h",
    ):
        source = ROOT / relative
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    subprocess.run(["git", "init", "-q", str(source_root)], check=True)
    subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(source_root), "-c", "user.name=Test", "-c",
         "user.email=test@example.invalid", "commit", "-qm", "captured source"],
        check=True,
    )
    return source_root


def test_wavetable_regeneration_uses_clean_captured_checkout_not_service_modules(
        tmp_path, monkeypatch):
    import prepare_wavetables as service_generator

    captured_root = _minimal_captured_wavetable_source(tmp_path)
    assert captured_root.resolve() != ROOT.resolve()
    source_commit, source_manifest = _source_manifest(captured_root)
    _pinned_source_manifest(captured_root, source_commit, sha(source_manifest))
    monkeypatch.setattr(
        service_generator, "prepare",
        lambda *_args, **_kwargs: pytest.fail("service generator must not be executed"),
    )

    output, prepared, image, verification = _generated_capture_fixture(
        tmp_path, ["macro"], source_root=captured_root,
    )
    generated, rows = _verified_generated_inputs(
        captured_root, output, prepared, image, verification,
    )
    assert {row["path"] for row in rows} == set(generated)
    assert all(row["sha256"] == sha(generated[row["path"]]) for row in rows)
    assert json.loads(generated["link/wave_tables.json"].decode("utf-8")) == (
        verification["compressed_wave_tables"]
    )
    assert generated["link/resources_plaits.cc"] == (
        output / "link/resources_plaits.cc"
    ).read_bytes()

    service_output = tmp_path / "service-generated"
    service_output.mkdir()
    _generate_wavetables_from_source(ROOT, service_output, ["plaits"])
    assert (service_output / "resources_plaits.cc").read_bytes() == (
        output / "link/resources_plaits.cc"
    ).read_bytes()

    source_file = captured_root / "engines/third_party/mutable/plaits/resources.cc"
    source_file.write_bytes(source_file.read_bytes() + b"/* mutated after capture */\n")
    with pytest.raises(ValueError, match="must be clean"):
        _pinned_source_manifest(captured_root, source_commit, sha(source_manifest))


def test_captured_source_mutation_during_generator_is_rejected(tmp_path, monkeypatch):
    import capture_trusted_build_tuple as capture

    captured_root = _minimal_captured_wavetable_source(tmp_path)
    source_commit, source_manifest = _source_manifest(captured_root)
    expected_source_sha = sha(source_manifest)
    output, prepared, image, verification = _generated_capture_fixture(
        tmp_path, ["macro"], source_root=captured_root,
    )
    generate = capture._generate_wavetables_from_source
    source_file = captured_root / "engines/third_party/mutable/plaits/resources.cc"

    def mutate_after_generation(root, destination, namespaces):
        rows = generate(root, destination, namespaces)
        source_file.write_bytes(source_file.read_bytes() + b"/* changed during regeneration */\n")
        return rows

    monkeypatch.setattr(capture, "_generate_wavetables_from_source", mutate_after_generation)
    with pytest.raises(ValueError, match="tracked source tree must be clean"):
        _verified_generated_inputs_from_pinned_source(
            captured_root, output, prepared, image, verification,
            source_commit, expected_source_sha,
        )


@pytest.mark.parametrize(("selected", "expected_namespaces"), [
    (["trio"], []),
    (["macro"], ["plaits"]),
    (["shapes"], ["braids"]),
    (["macro", "shapes"], ["braids", "plaits"]),
])
def test_generated_bank_inventory_follows_digest_bound_selected_modules(
        tmp_path, selected, expected_namespaces):
    output, prepared, image, verification = _generated_capture_fixture(tmp_path, selected)
    generated, rows = _verified_generated_inputs(
        ROOT, output, prepared, image, verification,
    )
    actual_namespaces = [name for name in ("braids", "plaits")
                         if f"link/resources_{name}.cc" in generated]
    assert actual_namespaces == expected_namespaces
    paths = [row["path"] for row in rows]
    assert "link/wave_tables.json" in paths
    assert "link/wave_tables.inc" in paths
    assert all((output / path).is_file() for path in paths)
    if expected_namespaces == ["braids", "plaits"]:
        # This is the historical all-bank generated path ordering retained by
        # all-55 tuple/provenance captures.
        assert paths == [
            "selection/prepared/fm1_modules.h",
            "selection/prepared/modules/gen/fm1_modules.h",
            "link/gen/fm1_modules.h",
            "link/module-all/gen/fm1_modules.h",
            "link/module-selection/gen/fm1_modules.h",
            "link/wave_tables.json",
            "link/resources_braids.cc",
            "link/resources_plaits.cc",
            "link/resources_braids.h",
            "link/resources_plaits.h",
            "link/wave_tables.inc",
        ]


@pytest.mark.parametrize("mutation, message", [
    ("missing-selected", "generated resource banks differ"),
    ("tamper-selected", "generated selected resource differs"),
    ("extraneous-bank", "generated resource banks differ"),
    ("tamper-metadata", "wave_tables.json differs from regenerated selected bank metadata"),
    ("missing-inc", "wave_tables.inc"),
    ("tamper-inc", "wave_tables.inc is not the exact generated table file"),
])
def test_generated_bank_inventory_rejects_missing_tampered_and_extra_resources(
        tmp_path, mutation, message):
    output, prepared, image, verification = _generated_capture_fixture(
        tmp_path, ["macro", "shapes"],
    )
    if mutation == "missing-selected":
        (output / "link/resources_braids.cc").unlink()
    elif mutation == "tamper-selected":
        path = output / "link/resources_plaits.cc"
        path.write_bytes(path.read_bytes() + b"/* changed */\n")
    elif mutation == "extraneous-bank":
        (output / "link/resources_unselected.cc").write_bytes(b"unexpected")
    elif mutation == "tamper-metadata":
        (output / "link/wave_tables.json").write_text("[]\n")
    elif mutation == "missing-inc":
        (output / "link/wave_tables.inc").unlink()
    elif mutation == "tamper-inc":
        path = output / "link/wave_tables.inc"
        path.write_bytes(path.read_bytes() + b"/* changed */\n")
    with pytest.raises((ValueError, OSError), match=message):
        _verified_generated_inputs(ROOT, output, prepared, image, verification)


def test_empty_bank_profile_still_rejects_unexpected_resources_and_metadata_drift(tmp_path):
    output, prepared, image, verification = _generated_capture_fixture(tmp_path, ["trio"])
    (output / "link/resources_plaits.h").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="generated resource banks differ"):
        _verified_generated_inputs(ROOT, output, prepared, image, verification)

    (output / "link/resources_plaits.h").unlink()
    image["compressed_wave_tables"] = [{"namespace": "plaits"}]
    with pytest.raises(ValueError, match="image wavetable metadata"):
        _verified_generated_inputs(ROOT, output, prepared, image, verification)


@pytest.mark.parametrize("mutation, message", [
    ("prepared-image", "prepared, image and link module selections differ"),
    ("link", "prepared, image and link module selections differ"),
    ("header", "prepared module selection does not bind its generated header"),
])
def test_generated_bank_selection_requires_prepared_and_link_receipts_to_agree(
        tmp_path, mutation, message):
    output, prepared, image, verification = _generated_capture_fixture(tmp_path, ["trio"])
    if mutation == "prepared-image":
        image["module_selection"] = dict(prepared["module_selection"], selected=["macro"])
    elif mutation == "link":
        verification["module_selection"] = dict(prepared["module_selection"], selected=["shapes"])
    elif mutation == "header":
        (output / "selection/prepared/fm1_modules.h").write_bytes(b"changed header")
    with pytest.raises(ValueError, match=message):
        _verified_generated_inputs(ROOT, output, prepared, image, verification)
