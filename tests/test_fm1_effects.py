"""Hash-gating, callback evidence, and the explicitly assumed float model."""

import hashlib
import json
import math
import os
from pathlib import Path
import struct

import pytest

from tools.fm1_dsp import hyperbolic_tangent_table
from tools.fm1_effects import V15_SHA256, analyze_effects, tanh_output_stage_f32


def model(sample, gain=1.0):
    return tanh_output_stage_f32(sample, gain, rounding_assumption="nearest-even")


@pytest.mark.parametrize("blob", [b"synthetic", b"FM-1_015\0" + bytes(581555)], ids=["unknown", "spoofed-identity"])
def test_unknown_and_identity_spoof_withhold_all_effect_annotations(blob):
    report = analyze_effects(blob)
    assert report["sha256"] == hashlib.sha256(blob).hexdigest()
    assert report["profile"]["matched"] is False
    assert report["profile"]["name"] is None
    assert report["effects"] == []
    for field in ("dispatch_table", "label_table", "dispatcher", "state_layout"):
        assert report[field] is None
    assert report["device_io_performed"] is False
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("blob", [b"", bytearray(b"x"), "FM-1_015", None])
def test_invalid_application_is_rejected(blob):
    with pytest.raises(ValueError):
        analyze_effects(blob)


@pytest.fixture
def private_v15():
    filename = os.environ.get("FM1_V15_APPLICATION")
    if not filename:
        pytest.skip("Set FM1_V15_APPLICATION to an extracted stock V15 application for private evidence checks")
    blob = Path(filename).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == V15_SHA256
    return blob


def test_private_stock_callbacks_and_corrected_dispatcher(private_v15):
    report = analyze_effects(private_v15)
    assert report["profile"]["matched"] is True
    assert report["dispatch_table"]["sha256"] == "b0a6e5f01ce6f24f10e5a5814d25a0a4cc5e28ba4a7f2db94d5b37606c5e87d1"
    assert report["dispatcher"]["size"] == 656
    assert report["dispatcher"]["sha256"] == "2575f84297ba0bfbe772fb8cc46cf632fd1440c0a559ebef449c2d7e47833760"
    expected_process = (0x0201A8E4, 0x0201AECE, 0x0201C2F6, 0x0201C8D6, 0x0201D20E, 0x0201D6CC)
    assert len(report["effects"]) == 6
    for effect, address in zip(report["effects"], expected_process):
        assert effect["name_confidence"] == "inferred"
        assert len(effect["callbacks"]) == 3
        for callback in effect["callbacks"]:
            assert "size" not in callback  # No guessed callback function extent.
            assert callback["file_offset"] == callback["runtime_address"] - 0x02000120
            assert callback["role_confidence"] == ("verified" if callback["role"] == "process" else "inferred")
        assert effect["callbacks"][2]["runtime_address"] == address
    assert report["state_layout"]["base_runtime_address"] == 0x01C0E840
    assert report["label_table"]["dispatch_binding_confidence"] == "inferred"
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("offset", [0, 0x457A4, 0x872BE, 581563])
def test_private_edited_image_loses_annotations_everywhere(private_v15, offset):
    changed = bytearray(private_v15)
    changed[offset] ^= 1
    report = analyze_effects(bytes(changed))
    assert report["profile"]["matched"] is False
    assert report["effects"] == []
    assert report["state_layout"] is None


def test_reference_requires_explicit_rounding_assumption():
    with pytest.raises(TypeError):
        tanh_output_stage_f32(0.25)
    with pytest.raises(ValueError):
        tanh_output_stage_f32(0.25, rounding_assumption="device-default")


def test_table_cell_endpoints_sign_and_separate_gain():
    table = hyperbolic_tangent_table()
    for index in range(512):
        sample = index / 512
        assert model(sample) == table[index]
        assert model(-sample) == -table[index]
    assert model(0.125, 0.5) == hyperbolic_tangent_table()[64] / 2
    assert struct.pack("<f", model(-0.0)) == bytes.fromhex("00000080")


def test_interpolation_is_bounded_monotone_and_tracks_scaled_tanh():
    samples = [i / 2048 for i in range(2048)]
    outputs = [model(value) for value in samples]
    assert all(a <= b for a, b in zip(outputs, outputs[1:]))
    assert max(abs(actual - math.tanh(8 * sample)) for sample, actual in zip(samples, outputs)) < 2.5e-5
    # A mid-cell value must use adjacent samples, not nearest-neighbor lookup.
    assert hyperbolic_tangent_table()[3] < model(3.5 / 512) < hyperbolic_tangent_table()[4]


def test_clamp_uses_one_not_last_table_entry():
    assert hyperbolic_tangent_table()[512] < 1.0
    for sample in (1.0, 1.25, 100.0):
        assert model(sample) == 1.0
        assert model(-sample, 0.5) == -0.5


@pytest.mark.parametrize("sample,gain", [(float("nan"), 1), (float("inf"), 1),
                                          (1, float("inf")), (True, 1), ("0.5", 1),
                                          (2**22, 1), (1e100, 1)])
def test_unresolved_numeric_domains_are_rejected(sample, gain):
    with pytest.raises(ValueError):
        model(sample, gain)
