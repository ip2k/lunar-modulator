"""Focused offline tests for the pinned FM-1_092 package model.

The large public source fixture and target-linked app are ignored retained inputs,
so the integration tests skip when those local artifacts are not present.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "jieli"))
import model_092_app_replacement as model  # noqa: E402

SOURCE = ROOT / "scratch/092-package-model/FM-1_092.fwsc"
REFERENCE = ROOT / "scratch/092-package-model/FM-1_092.fwsc_unpack"
APP = Path("/home/claude/mvave-fm1/shapes8-target-fit-20261014/link/artifact/app.bin")


def retained_inputs():
    if not (SOURCE.is_file() and APP.is_file() and REFERENCE.is_dir()):
        pytest.skip("retained public FWSC, unpack reference, or linked candidate is unavailable")
    return SOURCE.read_bytes(), REFERENCE, APP.read_bytes()


def test_original_092_physical_roundtrip_and_legacy_offset_are_explicit():
    raw, _, _ = retained_inputs()
    logical = model._logical(raw)
    assert model._physical(logical, raw) == raw
    legacy = model._outer_parse(raw, legacy_092=True)
    assert legacy["identity"] == "FM-1_092"
    # The unmodified 092 suffix ciphertext uses its inherited V15 logical offsets.
    with pytest.raises(ValueError, match="payload CRC mismatch"):
        model._outer_parse(raw, legacy_092=False)


def test_pinned_candidate_models_with_exact_logical_protected_payloads():
    raw, reference, app = retained_inputs()
    report = model.model(raw, reference, app)
    assert report["candidate_app_bytes"] == 845036
    assert report["app_slack_to_max"] == 14644
    assert report["modeled_flash_bytes"] == 0xD7000
    assert report["nested_boundaries"]["slack_to_stage"] == 14644
    assert report["logical_protected_components_preserved"] is True
    assert report["binary_emitted"] is False
    assert report["packaging_ready"] is report["hardware_admitted"] is report["installable"] is False
    assert report["outer_integrity"] == {
        "header_crc_verified": True,
        "entry_list_crc_verified": True,
        "all_payload_crcs_verified": True,
    }
    for name in ("USR", "isd_config.ini", "script.ver", "blimit.bin"):
        assert report["relocated_outer_payloads"][name]["changed"] is True


def test_overbound_and_wrong_candidate_refuse_before_build():
    raw, reference, app = retained_inputs()
    with pytest.raises(ValueError, match="preserved-tail D7000 profile"):
        model._build(raw, reference, b"x" * (model.MAX_APP_BYTES + 1))
    wrong = bytearray(app)
    wrong[0] ^= 1
    with pytest.raises(ValueError, match="pinned Shapes8/Event-Horizon"):
        model._build(raw, reference, bytes(wrong))


def test_source_tamper_and_modeled_outer_corruption_refuse():
    raw, reference, app = retained_inputs()
    changed_source = bytearray(raw)
    changed_source[-1] ^= 1
    with pytest.raises(ValueError, match="pinned public FM-1_092 fixture"):
        model._build(bytes(changed_source), reference, app)

    modeled, *_ = model._build(raw, reference, app)
    corrupted = bytearray(modeled)
    corrupted[-1] ^= 1
    with pytest.raises(ValueError):
        model.verify_modeled(raw, bytes(corrupted), reference, app)
