# SPDX-License-Identifier: MIT
"""Pure source/contract checks; no service, worker, compiler or device is run."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError
from tools.installer_service import build_capabilities as capabilities
from tools.installer_service import selected_trio_profile as profile
from tools.installer_service.request_contract import canonical_request, validate_request as v1_request
from tools.installer_service.server import check_native_prerequisites

ROOT = Path(__file__).resolve().parents[1]
BASE = "7ab2810420999629d170531a6f2f78fd44a8484f"


def request(**changes):
    value = dict(version=2, profile_id=capabilities.SELECTED_TRIO_PROFILE,
                 runtime_mode="offline", flash_layout="stock-sized-diagnostic",
                 engines=["trio"], effects=[], midi=[], modulation=[],
                 project_ids=["init-starter-trio"], startup_index=0)
    value.update(changes)
    return json.dumps(value).encode()


def test_fixed_request_canonical_and_no_internal_arp_selection():
    validated = profile.validate_request(request())
    assert validated["midi"] == []
    assert "arp" not in canonical_request(validated).decode()
    assert canonical_request(validated) == canonical_request(profile.validate_request(request(set_ids=[])))
    assert validated["version"] == 2 and validated["runtime_mode"] == "offline"


@pytest.mark.parametrize("changes", [
    {"version": True}, {"version": 1}, {"version": 2.0}, {"version": "2"},
    {"profile_id": "sdk-free-single-fm6-diagnostic-v1"},
    {"profile_id": "fm1-500-d7000-hall-o2-stage7-v1"},
    {"runtime_mode": "diagnostic"}, {"runtime_mode": "song-diagnostic"},
    {"runtime_mode": "continuous"}, {"runtime_mode": "rom20"},
    {"flash_layout": "expanded-d9000"}, {"flash_layout": "expanded-d7000"},
    {"flash_layout": "stock-protected"}, {"engines": ["dx7"]},
    {"engines": ["trio", "trio"]}, {"engines": []}, {"engines": [True]},
    {"effects": ["hall"]}, {"midi": ["arp"]}, {"modulation": ["lfo"]},
    {"project_ids": ["init-starter-trio", "init-starter-trio"]},
    {"project_ids": ["packet-bloom"]}, {"startup_index": 1},
    {"startup_index": False}, {"set_ids": ["companion"]},
    {"command": "builder"}, {"installable": True}, {"source_commit": BASE},
])
def test_fixed_request_refuses_other_selections_and_claims(changes):
    with pytest.raises((ValueError, ValidationError)):
        profile.validate_request(request(**changes))


@pytest.mark.parametrize("raw", [b'{"version":2,"version":2}', b'[]', b'{"version":NaN}',
    b'{"value":1e999}', b'\xff', b' ' * 65537])
def test_fixed_request_uses_shared_bounded_strict_json(raw):
    with pytest.raises((ValueError, UnicodeError)):
        profile.validate_request(raw)


def test_v1_canonical_bytes_and_rejection_stay_unchanged():
    catalogue = (ROOT / "tests/fixtures/installer-request-catalogue.json").read_bytes()
    old = dict(version=1, engines=["trio"], effects=[], midi=[], modulation=[],
               project_ids=["init-starter-trio"], startup_index=0)
    expected = b'{"effects":[],"engines":["trio"],"midi":[],"modulation":[],"project_ids":["init-starter-trio"],"startup_index":0,"version":1}\n'
    assert canonical_request(v1_request(json.dumps(old).encode(), catalogue)) == expected
    with pytest.raises(ValueError):
        v1_request(request(), catalogue)
    with pytest.raises(ValueError, match="native build prerequisites are unavailable"):
        check_native_prerequisites(ROOT, BASE)


def test_source_declaration_never_enables_any_capability():
    result = capabilities.selected_trio_capability()
    assert result["internal_dependencies"] == ["arp"]
    for field in ("service_enabled", "native_build_verified", *profile.DENIED):
        assert result[field] is False
    assert result["flash_layout"] == "stock-sized-diagnostic"
    result["internal_dependencies"].append("other")
    assert capabilities.selected_trio_capability()["internal_dependencies"] == ["arp"]


def test_current_fixed_source_prerequisites_pass_separately_from_legacy_gate():
    capabilities.check_profile_prerequisites(ROOT, BASE, capabilities.SELECTED_TRIO_PROFILE)


@pytest.fixture
def committed_source(tmp_path):
    for relative in capabilities.SELECTED_TRIO_PREREQUISITES:
        path = tmp_path / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source only\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    sha = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"]).decode().strip()
    return tmp_path, sha


@pytest.mark.parametrize("failure", ["missing", "changed", "symlink"])
def test_source_preflight_refuses_missing_changed_or_aliased_source(committed_source, failure):
    root, sha = committed_source
    path = root / capabilities.SELECTED_TRIO_PREREQUISITES[0]
    if failure == "missing": path.unlink()
    elif failure == "changed": path.write_text("changed\n")
    else:
        path.unlink(); path.symlink_to(root / capabilities.SELECTED_TRIO_PREREQUISITES[1])
    with pytest.raises(ValueError):
        capabilities.check_profile_prerequisites(root, sha, capabilities.SELECTED_TRIO_PROFILE)


@pytest.mark.parametrize("raw", [b"", b"ELF", bytes(52), bytes(100)])
def test_malformed_elf_refuses_without_tools_or_unbounded_reader(raw):
    with pytest.raises(ValueError):
        profile._elf(raw)


# Golden bytes of the repository's MIT fixed starter PROJECT, not firmware or SDK.
# Exact 597-byte strict-packed source pin; target evidence is checked separately.
FIXED_PROJECT = bytes.fromhex(
    "894c756e61720d0a0100010020000900140000005502000003000100c2395e0b696e666f01000000d8000000a4000000"
    "b7bc675b554e4954010000007c01000087000000fc3022af554e4954010000000402000009000000283cffc8554e4954"
    "0100000010020000090000009c37886e554e4954010000001c020000090000007300d83d554e49540100000028020000"
    "09000000900757b3554e49540100000034020000090000000e07fd7f554e49540100000040020000090000006b2884df"
    "554e4954010000004c02000009000000df23f379d1285c04050001000400040068616e640400040009005452494f2049"
    "4e49540500040011005472696f20496e697420537461727465720600040063005472696f2064656661756c7420706174"
    "636820696e20536f756e6420312e204e6f2073657175656e6365206f7220736f6e672e204e617469766520636f6e7472"
    "6f6c7320616e6420706c61796261636b2072656d61696e20756e76657269666965642e0800040003004d495401000000"
    "047472696f0e000100ff01000000000200ff00000000000300ff00000040c10400ff000000c0400500ff010000000006"
    "00ff0066cec3440700ff000000fc410800ff00269349420900ff00000000000a00ff00e17a04400b00ff00333320430c"
    "00ff00cdcc8d420d00ff0033339b420e00ff003333333f01000100030004000000c84200020000000000000000000000"
    "020001000000000000000000010100000000000000000000010200000000000000000000010300000000000000000000"
    "030000000000000000000000030001000000000000"
)


def synthetic_elf():
    """Small ELF-format witness, never a compiled/executable acceptance artifact."""
    import struct
    xip, ram = 0x02000120, 0x01C08000
    text = bytes(16) + FIXED_PROJECT
    data = bytes(16)
    bss = ram + 16
    sections = [(".text", 1, 6, xip, text, len(text)),
                (".data", 1, 3, ram, data, len(data)),
                (".bss", 8, 3, bss, b"", 0x9000),
                (".noinit", 8, 3, 0x01C7C000, b"", 64)]
    syms = [("_start", xip, 8, 1), ("app", bss, 64, 3),
            ("sound", bss + 64, 16384, 3), ("arenas", bss + 16448, 8, 3),
            ("reader_space", bss + 16464, 16384, 3),
            ("lunar_selected_project_blob", xip + 16, 597, 1),
            ("_data_load", xip + len(text), 0, 1), ("_bss_end", bss + 0x9000, 0, 3)]
    syms += [(n, v, 0, 0xFFF1) for n, v in dict(_guard0=0x01C74000,
             _ustack_lo=0x01C74100, _ustack_top=0x01C7A000, _guard1=0x01C7A000,
             _sstack_lo=0x01C7A100, _sstack_top=0x01C7C000).items()]
    strings = bytearray(b"\0"); entries = [bytes(16)]
    for name, value, size, section in syms:
        offset = len(strings); strings.extend(name.encode() + b"\0")
        entries.append(struct.pack("<IIIBBH", offset, value, size, 0x11, 0, section))
    shstrings = bytearray(b"\0"); names = {}
    for name in [s[0] for s in sections] + [".shstrtab", ".strtab", ".symtab"]:
        names[name] = len(shstrings); shstrings.extend(name.encode() + b"\0")
    sections += [(".shstrtab", 3, 0, 0, bytes(shstrings), len(shstrings)),
                 (".strtab", 3, 0, 0, bytes(strings), len(strings)),
                 (".symtab", 2, 0, 0, b"".join(entries), len(entries) * 16)]
    body = bytearray(); headers = [bytes(40)]
    for name, kind, flags, address, content, size in sections:
        offset = 52 + len(body); body.extend(content)
        headers.append(struct.pack("<10I", names[name], kind, flags, address, offset,
                       size, 6 if kind == 2 else 0, 0, 4, 16 if kind == 2 else 0))
    start = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9)
    header = start + struct.pack("<HHIIIIIHHHHHH", 2, 0xF1, 1, xip, 0, 52 + len(body),
                                0, 52, 0, 0, 40, len(headers), 5)
    return header + body + b"".join(headers), text + data


@pytest.fixture
def evidence():
    from tools.jieli.audit_link import Elf, audit
    elf, app = synthetic_elf()
    source = {profile.SOURCE_PATH: profile.SOURCE_SHA256, "unit.c": "1" * 64}
    headers = {"__config": "2" * 64}
    binding = dict(schema=1, archive_sha256=profile.ARCHIVE_SHA256, archive_root="fixed",
                   tree_manifest={"unit": dict(kind="file", bytes=1, execute_bits=0, sha256="3" * 64)})
    binding["tree_sha256"] = profile._sha(profile._canonical(binding["tree_manifest"]))
    tools = dict(renderer="4" * 64, state_tool="5" * 64, metadata="6" * 64)
    preparation = dict(schema=1, selection="init-starter-trio", source_path=profile.SOURCE_PATH,
        source_sha256=profile.SOURCE_SHA256, packed_sha256=profile.PACKED_SHA256,
        packed_bytes=597, records=30, parameters=14, renderer_sha256=tools["renderer"],
        state_tool_sha256=tools["state_tool"], metadata_sha256=tools["metadata"],
        linked_hal=dict(name="Dinghy", upstream_commit=profile.GPL_SOURCES["dinghy"],
                        licence="GPL-3.0-only", linked_here=False),
        distribution_reviewed=False, release_candidate=False, installable=False,
        hardware_admitted=False, native_link_verified=False, native_ram_verified=False)
    files = {"selected_project.bin": FIXED_PROJECT, "selected_project_blob.c": b"fixture c",
             "selected_project_blob.h": b"fixture h", "receipt.json": json.dumps(preparation).encode()}
    flags = ("-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin "
        "-ffunction-sections -fdata-sections -DFM1_APP_EXTERNAL_ARENAS=1 -DNDEBUG "
        "-D_GNU_SOURCE -D_XOPEN_SOURCE=700 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1 "
        "-D_LIBCPP_HAS_NO_THREADS -D_LIBCPP_DISABLE_EXTERN_TEMPLATE -isystem /headers "
        "-isystem /toolchain/pi32v2/include").split()
    trusted = profile.TrustedInputs(BASE, "7" * 40, source, binding, headers, headers, tools,
              files, {"obj/unit.o": b"synthetic object"}, (("unit.c", 1, "void unit(void) {}"),),
              tuple(flags), "synthetic compiler version")
    image = Elf(elf)
    sizes = dict(sections={s["name"]:dict(address=s["addr"],bytes=s["size"])
                for s in image.sections if s["flags"] & 2},
                user_stack_bytes=0x5F00, supervisor_stack_bytes=0x1F00,
                globals_to_stack_guard_bytes=0x01C74000-image.symbol_value("_bss_end"),
                flash_bytes=len(app))
    for key, name in dict(app="app", arena="sound", descriptors="arenas",
                         reader_workspace="reader_space", selected_blob="lunar_selected_project_blob").items():
        s = next(s for s in image.symbols if s["name"] == name)
        sizes[key] = dict(address=s["value"], bytes=s["size"])
    receipt = dict(profile=capabilities.SELECTED_TRIO_PROFILE, hardware_admitted=False,
        release_candidate=False, sdk_archives=[], modules=["trio"], external_arenas=True,
        arena_bytes=16384, cpu1=False, usb=False, persistence=False, fail_open=False,
        toolchain_archive_sha256=profile.ARCHIVE_SHA256, toolchain_binding=binding,
        compiler_version=trusted.compiler_version, cxx_headers_manifest=headers,
        configured_cxx_headers_manifest=headers, source_manifest=source, compile_flags=flags,
        objects=[dict(path=k,sha256=profile._sha(v)) for k,v in trusted.objects.items()],
        elf_sha256=profile._sha(elf), app_sha256=profile._sha(app), sizes=sizes,
        audit_link=audit([("fixture.elf",image)], [("app.bin",app)],True,
                         sources=trusted.audit_sources,runtime="sdk-free"),
        audit_limit="synthetic coherence fixture, never target acceptance",
        selected_project=preparation, fixed_project_startup=True, rom_return=False,
        distribution_reviewed=False, linked_blob=dict(sha256=profile.PACKED_SHA256,
            bytes=597,address=sizes["selected_blob"]["address"]),
        combined_licence="GPL-3.0-only", gpl_sources=profile.GPL_SOURCES,
        prepared_input_manifest={k:profile._sha(v) for k,v in files.items()},
        renderer_input=dict(path="/renderer",sha256=tools["renderer"]),
        state_tool_input=dict(path="/state",sha256=tools["state_tool"]))
    return receipt, app, elf, trusted


def validate(evidence):
    receipt, app, elf, trusted = evidence
    return profile.validate_receipt(request(), json.dumps(receipt).encode(),
                                    app=app, elf=elf, trusted=trusted)


def test_synthetic_coherence_never_returns_admission(evidence):
    result = validate(evidence)
    assert result["artifact_bytes"] == 629
    assert result["app_budget_bytes"] == 0x8DFBC
    assert result["request_sha256"] == profile._sha(canonical_request(profile.validate_request(request())))
    for field in profile.DENIED:
        assert result[field] is False


@pytest.mark.parametrize("field,value", [
    ("profile", "sdk-free-single-fm6-diagnostic-v1"), ("modules", ["trio", "dx7"]),
    ("hardware_admitted", True), ("release_candidate", True), ("distribution_reviewed", True),
    ("rom_return", True), ("cpu1", True), ("usb", True), ("persistence", True),
    ("fail_open", True), ("sdk_archives", ["system.a"]), ("arena_bytes", 65536),
    ("toolchain_archive_sha256", "0" * 64), ("source_manifest", {}),
    ("cxx_headers_manifest", {"__config":"0"*64}), ("configured_cxx_headers_manifest", {}),
    ("compile_flags", ["-O2"]), ("compiler_version", "other"),
    ("app_sha256", "0" * 64), ("elf_sha256", "0" * 64),
    ("prepared_input_manifest", {}), ("objects", []), ("selected_project", {}),
    ("linked_blob", dict(sha256="0"*64,bytes=597,address=0x02000130)),
    ("gpl_sources", {}), ("combined_licence", "MIT"),
    ("installable", True), ("runtime_configuration", {"return_to_rom_seconds":20}),
])
def test_receipt_mutations_refuse(evidence, field, value):
    evidence[0][field] = value
    with pytest.raises(ValueError): validate(evidence)


@pytest.mark.parametrize("field", ["app", "arena", "reader_workspace", "selected_blob"])
def test_claimed_storage_cannot_override_actual_elf(evidence, field):
    evidence[0]["sizes"][field]["bytes"] += 1
    with pytest.raises(ValueError, match="ELF sizes"): validate(evidence)


@pytest.mark.parametrize("field,value", [("n_pending",1),("n_fail",1),("passed",False),
                                       ("checks",[]),("runtime","sdk")])
def test_audit_must_be_complete_and_recomputed(evidence, field, value):
    evidence[0]["audit_link"][field] = value
    with pytest.raises(ValueError): validate(evidence)


def test_flat_bytes_must_match_elf_even_with_rehashed_receipt(evidence):
    receipt, app, elf, trusted = evidence
    app = app[:-1] + b"x"; receipt["app_sha256"] = profile._sha(app)
    with pytest.raises(ValueError, match="flat image differs"):
        validate((receipt, app, elf, trusted))


def test_duplicate_object_rows_and_unhashable_paths_refuse(evidence):
    evidence[0]["objects"] *= 2
    with pytest.raises(ValueError): validate(evidence)
    evidence[0]["objects"] = [dict(path=[],sha256="1"*64)]
    with pytest.raises(ValueError): validate(evidence)


def change_symbol(raw, name, *, value=None, size=None):
    import struct
    from tools.jieli.audit_link import Elf
    image = Elf(raw)
    table = next(s for s in image.sections if s["type"] == 2)
    index = next(i for i, s in enumerate(image.symbols) if s["name"] == name)
    raw = bytearray(raw)
    if value is not None: struct.pack_into("<I", raw, table["offset"] + 16 * index + 4, value)
    if size is not None: struct.pack_into("<I", raw, table["offset"] + 16 * index + 8, size)
    return bytes(raw)


def rehashed_elf(evidence, elf, app=None):
    receipt, old_app, _, trusted = evidence
    if app is None: app = old_app
    receipt["elf_sha256"] = profile._sha(elf)
    receipt["app_sha256"] = profile._sha(app)
    return receipt, app, elf, trusted


@pytest.mark.parametrize("symbol,value", [("_guard0", 0x01C74004), ("_bss_end", 0x01C74001)])
def test_actual_guard_symbols_cannot_be_repaired_by_receipt_claims(evidence, symbol, value):
    elf = change_symbol(evidence[2], symbol, value=value)
    with pytest.raises(ValueError, match="guard"):
        validate(rehashed_elf(evidence, elf))


def test_actual_storage_overlap_refuses_with_consistent_receipt(evidence):
    address = evidence[0]["sizes"]["arena"]["address"]
    elf = change_symbol(evidence[2], "reader_space", value=address)
    evidence[0]["sizes"]["reader_workspace"]["address"] = address
    with pytest.raises(ValueError, match="overlaps"):
        validate(rehashed_elf(evidence, elf))


def test_linked_blob_bytes_are_checked_even_with_rehashed_elf_and_flat(evidence):
    elf = evidence[2].replace(FIXED_PROJECT, FIXED_PROJECT[:-1] + b"x")
    app = evidence[1].replace(FIXED_PROJECT, FIXED_PROJECT[:-1] + b"x")
    with pytest.raises(ValueError, match="ELF selected blob"):
        validate(rehashed_elf(evidence, elf, app))


@pytest.mark.parametrize("replacement", [b"malloc", b"ota_tx", b"sdk_tx", b"free"])
def test_forbidden_retained_symbols_refuse_without_audit_translation(evidence, replacement):
    elf = evidence[2].replace(b"reader_space\0", replacement + b"\0" * (13-len(replacement)))
    with pytest.raises(ValueError, match="forbidden"):
        profile._elf(elf)


@pytest.mark.parametrize("mutation", ["overlap", "relocation", "symbol_stride", "symbol_count"])
def test_elf_reader_work_is_bounded_before_shared_parser(evidence, mutation):
    import struct
    raw = bytearray(evidence[2]); shoff = struct.unpack_from("<I", raw, 32)[0]
    # Test-only synthetic image: .text row1; .data row2; symtab row7.
    if mutation == "overlap": struct.pack_into("<I", raw, shoff+2*40+16, 53)
    if mutation == "relocation": struct.pack_into("<I", raw, shoff+7*40+4, 9)
    if mutation == "symbol_stride": struct.pack_into("<I", raw, shoff+7*40+36, 1)
    if mutation == "symbol_count": struct.pack_into("<I", raw, shoff+7*40+20, 1600016)
    with pytest.raises(ValueError): profile._elf(bytes(raw))


@pytest.mark.parametrize("field", ["source_manifest", "cxx_headers_manifest", "configured_cxx_headers_manifest", "host_tools"])
def test_missing_external_trust_anchors_refuse(evidence, field):
    from dataclasses import replace
    receipt, app, elf, trusted = evidence
    trusted = replace(trusted, **{field: {}})
    with pytest.raises(ValueError): validate((receipt, app, elf, trusted))


def test_changed_actual_object_and_prepared_bytes_refuse(evidence):
    from dataclasses import replace
    receipt, app, elf, trusted = evidence
    with pytest.raises(ValueError, match="object inputs"):
        validate((receipt, app, elf, replace(trusted, objects={"obj/unit.o":b"different"})))
    files = dict(trusted.prepared_files); files["selected_project_blob.c"] += b"changed"
    with pytest.raises(ValueError, match="prepared inputs"):
        validate((receipt, app, elf, replace(trusted, prepared_files=files)))
