"""Formula proofs, full-table matching and lookup-stage numerical invariants."""

import hashlib
import math
import struct

import pytest

from tools.fm1_dsp import (analyze_dsp_tables, exponent_table, log_sine_table,
                          log_sine_lookup_stage, modulation_sine_table, hyperbolic_tangent_table)


def encoded(values):
    return struct.pack("<1024H", *values)


def test_generated_tables_match_independently_recorded_stock_fingerprints():
    # Fingerprints were measured from V15; no vendor bytes are included here.
    assert hashlib.sha256(encoded(exponent_table())).hexdigest() == "e515a71ae736d92dcb3fd36973dea486c96d1521f1a0bab1f917be2c4ec07794"
    assert hashlib.sha256(encoded(log_sine_table())).hexdigest() == "990c19e90732efe712a19ba4272f97c7c9d884ac0e4e19450a1067165d8aa8a8"


def test_does_not_identify_partial_or_corrupt_table():
    table = bytearray(encoded(log_sine_table()))
    assert analyze_dsp_tables(bytes(table[:-2]))["tables"] == []
    table[-1] ^= 1
    assert analyze_dsp_tables(bytes(table))["tables"] == []


def test_full_table_pair_and_region_mapping():
    prefix = b"synthetic header\0"
    data = prefix + encoded(exponent_table()) + encoded(log_sine_table())
    report = analyze_dsp_tables(data, [{"file_offset": len(prefix), "size": 4096, "runtime_address": 0x1C00000}])
    assert len(report["tables"]) == 2
    assert report["tables"][1]["address"] == 0x1C00800
    assert report["adjacent_pairs"][0]["exponent_file_offset"] == len(prefix)


@pytest.mark.parametrize("generate,fingerprint", [
    (modulation_sine_table, "0e805578a690fbf1eb1eca2bf611e78f6ffedf3cd3a876e76ebb119c56416850"),
    (hyperbolic_tangent_table, "a6c0a24144dc64bc73a4a8955f43e1b5f32f80f61569e33be612c9ac97fcdc61"),
])
def test_float_tables_match_independent_stock_fingerprints(generate, fingerprint):
    data = struct.pack("<513f", *generate())
    assert hashlib.sha256(data).hexdigest() == fingerprint
    result = analyze_dsp_tables(data)["tables"]
    assert len(result) == 1
    assert result[0]["byte_exact"] is True
    assert result[0]["matching_entries"] == 513
    assert result[0]["address"] is None
    assert analyze_dsp_tables(data[:-4])["tables"] == []
    changed = data[:-1] + bytes([data[-1] ^ 1])
    assert analyze_dsp_tables(changed)["tables"] == []


def test_sine_rounding_and_signed_zero_are_material():
    table = modulation_sine_table()
    assert len(table) == 513
    assert struct.pack("<f", table[256]) == bytes.fromhex("00000000")
    assert struct.pack("<f", table[512]) == bytes.fromhex("00000080")
    direct = struct.pack("<513f", *(math.sin(i * math.pi / 256) for i in range(513)))
    assert analyze_dsp_tables(direct)["tables"] == []
    assert table[128] == 1 and table[384] == -1


def test_repeated_table_reports_truncation():
    data = encoded(exponent_table()) * 65
    report = analyze_dsp_tables(data)
    assert len(report["tables"]) == 64
    assert report["truncated_tables"] == ["fractional_exponent"]


def test_sample_lookup_tracks_sine_with_documented_quantization():
    # Mathematical independent reference: half-cell phase, mantissa bias from
    # complementing ten fraction bits, and one's-complement negative values.
    error = []
    for phase_cell in range(4096):
        actual = log_sine_lookup_stage(phase_cell << 12, 0)
        expected = math.sin((phase_cell + 0.5) * 2 * math.pi / 4096) * 8192 * 2 ** (-1 / 1024)
        if phase_cell >= 2048:
            expected -= 1
        error.append(abs(actual - expected))
    assert max(error) < 4


def test_phase_period_and_one_octave_attenuation():
    for position in (0, 123, 511, 1023, 1555, 2048, 3071, 4095):
        phase = position << 12
        value = log_sine_lookup_stage(phase, 0)
        assert log_sine_lookup_stage(phase + (1 << 24), 0) == value
        assert log_sine_lookup_stage(phase + 4095, 0) == value
        attenuated = log_sine_lookup_stage(phase, 1024)
        magnitude = value if value >= 0 else -value - 1
        half = attenuated if attenuated >= 0 else -attenuated - 1
        assert half == magnitude >> 1


def test_signed_model_matches_actual_negative_register_shift():
    for cell in range(2048, 4096):
        for attenuation in (0, 512, 1024, 8192, 16383, 16384):
            signed = log_sine_lookup_stage(cell << 12, attenuation)
            magnitude = -signed - 1
            register = (magnitude | 0x70000) ^ 0xFFFF
            assert ((signed << 13) & 0xFFFFFFFF) == ((register << 13) & 0xFFFFFFFF)


@pytest.mark.parametrize("phase,attenuation", [(0, -1), (0, 16385), (0, True), (0.5, 0)])
def test_invalid_lookup_domain_is_rejected(phase, attenuation):
    with pytest.raises(ValueError):
        log_sine_lookup_stage(phase, attenuation)
