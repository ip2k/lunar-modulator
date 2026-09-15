"""Synthetic firmware only: corruption checks do not need vendor binaries."""

import json
import pathlib
import struct
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import fm1_package as package


def reference_crc(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


def cipher(data, key=0xffff):
    result = bytearray(data)
    for index in range(len(result)):
        result[index] ^= key & 255
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xffff
    return bytes(result)


def sfc(data, key, base=0):
    return b"".join(cipher(data[i:i + 32], (key ^ ((base + i) >> 2)) & 0xffff)
                    for i in range(0, len(data), 32))


def jlfs(name, offset, data, flags=0x82, last=1, size=None, dcrc=None):
    header = bytearray(struct.pack("<HHIIBBH16s", 0,
                                  reference_crc(data) if dcrc is None else dcrc,
                                  offset, len(data) if size is None else size,
                                  flags, 255, last, name.encode().ljust(16, b"\0")))
    struct.pack_into("<H", header, 0, reference_crc(header[2:]))
    return bytes(header)


KEY = 0x980f
# Sum(first half) = 16 => threshold 0x55. Below threshold encodes a 1.
KEY_BYTES = bytes([1] * 16 + [(0 if KEY & (1 << bit) else 255) ^ 1 for bit in range(16)])
KEY_RECORD = KEY_BYTES + struct.pack("<H", reference_crc(KEY_BYTES))


def app_image(variant=True):
    rows = [list(row) for row in package.MSFA_ALGORITHMS]
    if variant:
        rows[3][0] = rows[5][0] = 0x41
    return b"synthetic FM-1_015\0" + bytes(value for row in rows for value in row)


def synthetic_flash(app=None, mutate=None):
    app = app if app is not None else app_image()
    area_body = jlfs("app.bin", 64, app) + app
    area = bytearray(jlfs("app_area_head", 0, area_body, flags=0x83,
                          size=32 + len(area_body)) + area_body)
    if mutate:
        mutate(area)
    area.extend(b"\xff" * (-len(area) % 32))
    flash = bytearray(0x1000)
    flash[:32] = b"\0" * 16 + b"AC791N_STORY".ljust(16, b"\xff")
    decoded_header = bytearray(cipher(flash[:32]))
    struct.pack_into("<H", decoded_header, 0, reference_crc(decoded_header[2:]))
    flash[:32] = cipher(decoded_header)
    flash[32:64] = cipher(jlfs("isd_config.ini", 0xa0, KEY_RECORD, flags=2, last=0))
    flash[64:96] = cipher(jlfs("app_dir_head", 0x1000, b"", flags=0x81,
                              size=0xffffffff, dcrc=0xffff))
    flash[0xa0:0xa0 + 34] = KEY_RECORD
    flash.extend(sfc(bytes(area), KEY))
    return bytes(flash)


def reinterleave(logical, identity=b"FM-1_015"):
    markers = bytes((byte + index + 1) & 255 for index, byte in enumerate(identity)) + b"\x7d" * 12
    return b"".join(logical[i * 47:i * 47 + 47] + markers[i:i + 1]
                    for i in range(20)) + logical[940:]


def logical_image(raw):
    return bytearray(b"".join(raw[i * 48:i * 48 + 47] for i in range(20)) + raw[960:])


def synthetic_package(flash=None):
    flash = flash if flash is not None else synthetic_flash()
    tail = KEY_RECORD + b"\0" * 14 + b"JLUFW" + b"\0" * 11
    records = [("flash.bin", 0, flash), ("info.log", 2, b""),
               ("script.ver", 251, b"AC791N-synthetic-test"), ("tail.bin", 255, tail)]
    logical = bytearray(0x400)
    table = bytearray()
    for index, (name, kind, data) in enumerate(records):
        offset = len(logical)
        allocation = (len(data) + 31) // 32 * 32
        entry = struct.pack("<HHHHIII44s16s", kind, index, reference_crc(data), 0,
                            offset, len(data), allocation, b"\0" * 44, name.encode().ljust(16, b"\0"))
        table.extend(cipher(entry))
        logical.extend(sfc(data, KEY, offset) if kind == 251 else data)
        logical.extend(b"\xff" * (allocation - len(data)))
    header = bytearray(struct.pack("<HHIHHI48s", 0, reference_crc(table), len(logical),
                                   len(records), 4, 512, b"AC791N\0"))
    struct.pack_into("<H", header, 0, reference_crc(header[2:]))
    logical[:64] = cipher(header)
    logical[64:64 + len(table)] = table
    return reinterleave(bytes(logical))


def edit_record(raw, index, change):
    logical = logical_image(raw)
    start = 64 + index * 80
    record = bytearray(cipher(logical[start:start + 80]))
    change(record)
    logical[start:start + 80] = cipher(record)
    header = bytearray(cipher(logical[:64]))
    count = struct.unpack_from("<H", header, 8)[0]
    struct.pack_into("<H", header, 2, reference_crc(logical[64:64 + count * 80]))
    struct.pack_into("<H", header, 0, reference_crc(header[2:]))
    logical[:64] = cipher(header)
    return reinterleave(logical)


def refresh_area_crc(area):
    size = struct.unpack_from("<I", area, 8)[0]
    struct.pack_into("<H", area, 2, reference_crc(area[32:size]))
    struct.pack_into("<H", area, 0, reference_crc(area[2:32]))


def test_crc_known_vector_and_independent_implementation():
    assert package.crc16(b"123456789") == 0x31c3
    assert package.crc16(bytes(range(256))) == reference_crc(bytes(range(256)))


def test_end_to_end_checks_encrypted_entries_and_derived_application():
    report = package.inspect_package(synthetic_package())
    assert report["identity"]["value"] == "FM-1_015"
    assert report["identity"]["authenticated"] is False
    assert report["integrity"]["entries_verified"] == 4
    assert report["entries"][2]["crc_scope"] == "sfc-decoded payload"
    assert report["entries"][2]["decoded_sha256"] != report["entries"][2]["sha256"]
    app = report["application"]
    assert app["size"] == len(app_image())
    assert app["extraction"]["app_area_offset"] == 0x1000  # Not a fixed stock 0x4000.
    assert app["extraction"]["flash_data_offset"] == 0x1040
    assert app["extraction"]["chip_key"] == "980f"
    assert app["msfa_tables"][0]["classification"] == "dexed-feedback-variant"
    assert app["msfa_tables"][0]["matching_rows"] == 30
    assert report["device_io_performed"] is False
    assert json.loads(json.dumps(report)) == report


@pytest.mark.parametrize("length", [0, 1, 31, 47, 48, 959, 960, 1043])
def test_truncated_headers(length):
    with pytest.raises(package.PackageError):
        package.inspect_package(synthetic_package()[:length])


def test_full_header_but_truncated_payload():
    with pytest.raises(package.PackageError, match="declared UFW size"):
        package.inspect_package(synthetic_package()[:-1])


@pytest.mark.parametrize("offset,error", [(0, "UFW header CRC"), (65, "UFW entry table CRC"),
                                         (1100, "flash.bin CRC")])
def test_corruption_without_repaired_outer_checksums(offset, error):
    logical = logical_image(synthetic_package())
    logical[offset] ^= 1
    with pytest.raises(package.PackageError, match=error):
        package.inspect_package(reinterleave(logical))


def test_identity_marker_corruption_and_filler():
    raw = bytearray(synthetic_package())
    raw[47] = 0
    with pytest.raises(package.PackageError, match="identity"):
        package.inspect_package(bytes(raw))
    raw = bytearray(synthetic_package())
    raw[9 * 48 + 47] = 0
    with pytest.raises(package.PackageError, match="identity"):
        package.inspect_package(bytes(raw))


@pytest.mark.parametrize("field,value,error", [(8, 0x100, "offset or allocation"),
                                             (8, 0xfffffff0, "outside"),
                                             (16, 1, "offset or allocation")])
def test_repaired_table_cannot_hide_invalid_bounds(field, value, error):
    damaged = edit_record(synthetic_package(), 0, lambda record: struct.pack_into("<I", record, field, value))
    with pytest.raises(package.PackageError, match=error):
        package.inspect_package(damaged)


def test_overlapping_allocations():
    raw = synthetic_package()
    damaged = edit_record(raw, 2, lambda record: struct.pack_into("<I", record, 8, 0x400))
    with pytest.raises(package.PackageError, match="allocations overlap"):
        package.inspect_package(damaged)


def test_duplicate_entry_name():
    damaged = edit_record(synthetic_package(), 1,
                          lambda record: record.__setitem__(slice(64, 80), b"flash.bin".ljust(16, b"\0")))
    with pytest.raises(package.PackageError, match="duplicate"):
        package.inspect_package(damaged)


def test_encrypted_payload_corruption():
    logical = logical_image(synthetic_package())
    record = cipher(logical[224:304])
    offset = struct.unpack_from("<I", record, 8)[0]
    logical[offset] ^= 1
    with pytest.raises(package.PackageError, match="script.ver CRC"):
        package.inspect_package(reinterleave(logical))


def test_nested_header_corruption_despite_valid_container_crc():
    def mutate(area):
        area[32] ^= 1
        refresh_area_crc(area)
    with pytest.raises(package.PackageError, match="application directory header CRC"):
        package.inspect_package(synthetic_package(synthetic_flash(mutate=mutate)))


def test_top_payload_out_of_bounds_with_repaired_header_and_outer_crc():
    flash = bytearray(synthetic_flash())
    header = bytearray(cipher(flash[32:64]))
    struct.pack_into("<I", header, 4, len(flash) + 1)
    struct.pack_into("<H", header, 0, reference_crc(header[2:]))
    flash[32:64] = cipher(header)
    with pytest.raises(package.PackageError, match="top isd_config.ini.*outside"):
        package.inspect_package(synthetic_package(bytes(flash)))


def test_top_payload_overlap_with_repaired_headers_and_outer_crc():
    flash = bytearray(synthetic_flash())
    # Make room for a third top record without moving the config data at 0xa0.
    app_pointer = bytearray(cipher(flash[64:96]))
    struct.pack_into("<H", app_pointer, 14, 0)
    struct.pack_into("<H", app_pointer, 0, reference_crc(app_pointer[2:]))
    flash[64:96] = cipher(app_pointer)
    flash[96:128] = cipher(jlfs("uboot.boot", 0xa0, KEY_RECORD, flags=0))
    with pytest.raises(package.PackageError, match="top directory payloads overlap"):
        package.inspect_package(synthetic_package(bytes(flash)))


def test_coverage_is_explicit_and_identity_markers_are_not_authentication():
    logical = logical_image(synthetic_package())
    report = package.inspect_package(reinterleave(logical, b"FM-1_014"))
    assert report["identity"]["value"] == "FM-1_014"
    assert report["application"]["embedded_identities"] == ["FM-1_015"]
    assert report["identity"]["matches_application"] is False
    assert report["identity"]["authenticated"] is False
    assert any("boot payload" in layer for layer in report["unchecked_layers"])
    assert any("Reserved flash" in layer for layer in report["unchecked_layers"])
    assert any("Identity marker" in layer for layer in report["unchecked_layers"])


def test_nested_data_corruption_despite_valid_container_and_area_crc():
    def mutate(area):
        area[70] ^= 1
        refresh_area_crc(area)
    with pytest.raises(package.PackageError, match="app.bin CRC"):
        package.inspect_package(synthetic_package(synthetic_flash(mutate=mutate)))


def test_nested_data_bounds_with_repaired_crcs():
    def mutate(area):
        struct.pack_into("<I", area, 32 + 4, 0xfffffff0)
        struct.pack_into("<H", area, 32, reference_crc(area[34:64]))
        refresh_area_crc(area)
    with pytest.raises(package.PackageError, match="outside"):
        package.inspect_package(synthetic_package(synthetic_flash(mutate=mutate)))


def test_partial_nested_header_never_becomes_a_valid_empty_app():
    def mutate(area):
        struct.pack_into("<I", area, 8, 50)
        refresh_area_crc(area)
    with pytest.raises(package.PackageError, match="too short"):
        package.inspect_package(synthetic_package(synthetic_flash(mutate=mutate)))


def test_msfa_classification_is_exact_and_partial_anchor_is_reported():
    original = package.inspect_application(app_image(variant=False))["msfa_tables"][0]
    assert original["classification"] == "msfa-original"
    changed = bytearray(app_image())
    changed[-1] ^= 1
    assert package.inspect_application(bytes(changed))["msfa_tables"][0]["classification"] == "other-variant"
    partial = package.inspect_application(b"prefix" + package.ANCHOR)["msfa_tables"][0]
    assert partial["classification"] == "truncated" and partial["complete"] is False
    assert partial["matching_rows"] == 3
    assert partial["differences"][-1]["actual"] is None
    assert package.inspect_application(b"nothing here")["msfa_tables"] == []


def test_bounded_input_and_bounded_report(monkeypatch):
    monkeypatch.setattr(package, "MAX_INPUT_SIZE", 16)
    with pytest.raises(package.PackageError, match="1 to 16"):
        package.inspect_application(b"x" * 17)
    monkeypatch.setattr(package, "MAX_INPUT_SIZE", 1024)
    monkeypatch.setattr(package, "MAX_TABLE_HITS", 2)
    with pytest.raises(package.PackageError, match="too many msfa"):
        package.inspect_application(package.ANCHOR * 3)


def test_cli_defaults_to_json_without_writes(tmp_path, capsys):
    source = tmp_path / "supplied.fwsc"
    source.write_bytes(synthetic_package())
    assert package.main(["package", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "fm1-package"
    assert list(tmp_path.iterdir()) == [source]


def test_cli_refuses_overwriting_or_unignored_output(tmp_path):
    source = tmp_path / "supplied.fwsc"
    raw = synthetic_package()
    source.write_bytes(raw)
    with pytest.raises(SystemExit):
        package.main(["package", str(source), "--app-out", str(source)])
    assert source.read_bytes() == raw
    with pytest.raises(package.PackageError, match="ignored"):
        package._output_path(tmp_path / "app.bin")


def test_cli_rejects_same_output_path(tmp_path, monkeypatch):
    source = tmp_path / "supplied.fwsc"
    source.write_bytes(synthetic_package())
    monkeypatch.setattr(package, "_output_path", lambda path: path.resolve())
    output = tmp_path / "report.json"
    with pytest.raises(SystemExit):
        package.main(["package", str(source), "--report", str(output), "--app-out", str(output)])
    assert not output.exists()
