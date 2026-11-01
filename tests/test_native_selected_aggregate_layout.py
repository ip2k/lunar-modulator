"""Source-only gates for the private aggregate target layout experiment."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "aggregate_builder", ROOT / "tools/native/build_diagnostic.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
ROOT_SOURCE = ROOT / "firmware/native/selected_aggregate_layout_roots.c"


def test_named_plan_preserves_existing_plans(tmp_path):
    default = BUILDER.diagnostic_plan()
    selected = BUILDER.diagnostic_plan(True, tmp_path)
    returned = BUILDER.diagnostic_plan(True, tmp_path, return_candidate=True)
    assert default["profile"] == "sdk-free-single-fm6-diagnostic-v1"
    assert default["modules"] == "dx7,arp,lfo,env,chance"
    assert default["arena_bytes"] == 65536 and "reader_bytes" not in default
    assert selected["profile"] == "sdk-free-selected-trio-offline-diagnostic-v1"
    assert selected["arena_bytes"] == 16384 and "reader_bytes" not in selected
    assert returned["profile"] == "sdk-free-selected-trio-return-binding-candidate-v1"
    assert returned["linker"] == ROOT / "firmware/third_party/selected-return/selected_return_candidate.ld"
    assert "reader_bytes" not in returned and "undefined_root" not in returned
    assert not any("aggregate" in p.name for p in returned["extra"])

    aggregate = BUILDER.diagnostic_plan(True, tmp_path, return_candidate=True,
                                        aggregate_layout=True)
    assert aggregate["profile"] == "sdk-free-selected-trio-aggregate-layout-experiment-v1"
    assert aggregate["modules"] == "trio"
    assert aggregate["arena_bytes"] == 16384 and aggregate["reader_bytes"] == 65536
    assert aggregate["linker"] == returned["linker"]
    assert aggregate["undefined_root"] == "lunar_selected_aggregate_layout_roots"
    assert aggregate["extra"][:len(returned["extra"])] == returned["extra"]
    assert aggregate["extra"][len(returned["extra"]):] == [
        ROOT / "firmware/native" / (name + ".c") for name in (
            "selected_interactive_owner", "selected_interactive_platform",
            "diagnostic_transport", "diagnostic_display",
            "diagnostic_spi_model", "selected_aggregate_layout_roots")]
    manifest = BUILDER.manifest(True, return_candidate=True, aggregate_layout=True)
    assert manifest["tools/native/build_selected_trio_aggregate_layout.py"] == \
        BUILDER.digest(ROOT / "tools/native/build_selected_trio_aggregate_layout.py")
    assert manifest["firmware/native/selected_aggregate_layout_roots.c"] == \
        BUILDER.digest(ROOT_SOURCE)
    with pytest.raises(ValueError, match="aggregate layout requires"):
        BUILDER.diagnostic_plan(True, tmp_path, aggregate_layout=True)
    with pytest.raises(ValueError, match="aggregate layout requires"):
        BUILDER.manifest(True, aggregate_layout=True)


def test_link_root_requires_advertised_vendor_option():
    root = "lunar_selected_aggregate_layout_roots"
    assert BUILDER.undefined_root_option("  -u <symbol>  Force undefined\n", root) == ["-u", root]
    assert BUILDER.undefined_root_option("  --undefined=<symbol>  Force undefined\n", root) == [
        "--undefined=" + root]
    with pytest.raises(ValueError, match="does not advertise"):
        BUILDER.undefined_root_option("  --gc-sections  Eliminate unused sections\n", root)


def test_exact_aggregate_flags_and_real_root_relocations(tmp_path):
    expected = [
        "-DLUNAR_SELECTED_INTERACTIVE_PROOF=1",
        "-DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1",
        "-DLUNAR_SELECTED_PROJECT_STAGE_PROOF=1",
        "-DLUNAR_DIAGNOSTIC_PI32V2_PUBLICATION=1",
        "-DLUNAR_DIAGNOSTIC_CPU0_ONLY=1",
    ]
    assert BUILDER.AGGREGATE_DEFINES == expected
    compiler = shutil.which("cc")
    nm = shutil.which("nm")
    assert compiler and nm
    extra = ["-DFM1_APP_EXTERNAL_ARENAS=1", "-DFM1_APP_STATE_EXTERNAL_WORKSPACE=1",
             "-DLUNAR_DIAGNOSTIC_PUBLICATION_INJECTED=1", *expected]
    includes = ["-I" + str(ROOT / name) for name in (
        "firmware/native", "engines/state", "engines/include", "sim/web/src")]
    base = [compiler, "-std=gnu11", "-ffunction-sections", "-fdata-sections",
            *includes, *extra]
    obj = tmp_path / "roots.o"
    subprocess.run([*base, "-c", str(ROOT_SOURCE), "-o", str(obj)],
                   check=True, capture_output=True, timeout=30)
    inventory = subprocess.run([nm, str(obj)], check=True, capture_output=True,
                               text=True, timeout=30).stdout
    for symbol in ("lunar_selected_aggregate_layout_roots",
                   "lunar_selected_aggregate_platform", "lunar_selected_aggregate_input",
                   "lunar_selected_aggregate_pcm", "lunar_selected_interactive_stage",
                   "lunar_selected_owner_init", "lunar_selected_owner_step",
                   "lunar_selected_platform_start", "lunar_selected_platform_main",
                   "lunar_selected_platform_timer", "lunar_selected_platform_audio",
                   "lunar_selected_platform_matrix", "lunar_selected_platform_encoder",
                   "lunar_diagnostic_init"):
        assert symbol in inventory
    for define in expected:
        missing = [x for x in base if x != define]
        failed = subprocess.run([*missing, "-fsyntax-only", str(ROOT_SOURCE)],
                                capture_output=True, timeout=30)
        assert failed.returncode and b"error" in failed.stderr
        zero = ["-D" + define[2:].split("=")[0] + "=0" if x == define else x
                for x in base]
        failed = subprocess.run([*zero, "-fsyntax-only", str(ROOT_SOURCE)],
                                capture_output=True, timeout=30)
        assert failed.returncode and b"error" in failed.stderr
