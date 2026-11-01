#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the fixed Trio diagnostic PROJECT as a source-bound C blob.

This is a host-only input stage, not an image builder or installer admission.
Only an exact current-build fm1-state with opt-in strict packing is accepted.
The output directory must be fresh; all temporary products are owned there.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import lunar_state
from tools.installer_service.process_capture import run_bounded

SELECTION = "init-starter-trio"
SOURCE = ROOT / "engines/state/examples/init-starters/trio-init.lunar"
SOURCE_SHA256 = "46541967e4fa7321f4efe1105632de3613064a2fbcf7d71490cb647247a97c1b"
PACKED_SHA256 = "dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4"
MAX_SOURCE = 65536
MAX_PACKED = 98304
MAX_META = 1048576


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bounded(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"oversized input: {path}")
    return data


def tool_output(tool, *args):
    # Full legacy metadata is about 255 KiB; selected Trio metadata is 39 KiB.
    # Refuse overflow rather than parse a truncated success. Descendants share
    # the existing capture helper's process-group and post-exit drain bound.
    result = run_bounded([str(tool), *args], cwd=ROOT, timeout_seconds=90,
                         max_stream_bytes=MAX_META)
    overflow = any(n > MAX_META for n in result.observed.values())
    reason = "output_limit" if overflow else result.failure_reason
    if reason or result.returncode:
        raise ValueError(f"{tool.name} {' '.join(args)} refused ({reason or 'nonzero_exit'}): "
                         + result.logs["stderr"][:1024].decode(errors="replace"))
    return result.logs["stdout"]


def write_blob(path, packed):
    lines = ["/* Generated from fixed init-starter-trio; see receipt.json. MIT. */",
             '#include "selected_project_blob.h"',
             "const uint8_t lunar_selected_project_blob[] = {"]
    for off in range(0, len(packed), 12):
        lines.append("  " + ", ".join(f"0x{b:02x}" for b in packed[off:off + 12]) + ",")
    lines += ["};", "const uint32_t lunar_selected_project_blob_bytes = "
              "(uint32_t)sizeof lunar_selected_project_blob;", ""]
    (path / "selected_project_blob.c").write_text("\n".join(lines))
    (path / "selected_project_blob.h").write_text(
        "/* Generated from fixed init-starter-trio; see receipt.json. MIT. */\n"
        "#ifndef LUNAR_SELECTED_PROJECT_BLOB_H_\n"
        "#define LUNAR_SELECTED_PROJECT_BLOB_H_\n"
        "#include <stdint.h>\n"
        "extern const uint8_t lunar_selected_project_blob[];\n"
        "extern const uint32_t lunar_selected_project_blob_bytes;\n"
        "#endif\n")


def prepare(renderer: Path, state_tool: Path, out: Path):
    renderer, state_tool, out = renderer.resolve(), state_tool.resolve(), out.absolute()
    if out.exists() or not out.parent.is_dir():
        raise ValueError("output must be a fresh directory with an existing parent")
    source = read_bounded(SOURCE, MAX_SOURCE)
    if digest(source) != SOURCE_SHA256:
        raise ValueError("selected project source changed")
    render_hash = digest(read_bounded(renderer, 64 * 1024 * 1024))
    tool_hash = digest(read_bounded(state_tool, 64 * 1024 * 1024))
    render_meta = tool_output(renderer, "--meta")
    state_meta = tool_output(state_tool, "meta")
    if len(render_meta) > MAX_META or len(state_meta) > MAX_META or render_meta != state_meta:
        raise ValueError("renderer and state tool have different metadata exports")
    names = lunar_state.Names(lunar_state.Names.parse(render_meta.decode()))
    meta = lunar_state.Names.parse(render_meta.decode())
    if ([(entry["id"], entry["kind"]) for entry in meta["engines"]]
            != [("trio", "sound")] or meta["build"]["rate"] != 44118):
        raise ValueError("selected build is not Trio-only at the native rate")
    expected_records, source_report = lunar_state.read_json(source, names)
    if (source_report.code != "OK" or source_report.skipped or source_report.repaired
            or source_report.unknown or
            len([r for r in expected_records if r["rec"] == "param"]) != 14):
        raise ValueError("selected source cannot be resolved exactly")

    # The fixed bytes are prepared in private fresh storage and only published
    # after strict native packing, an independent binary read and all hashes.
    out.mkdir(mode=0o700)
    try:
        source_snapshot = out / "source.lunar"
        source_snapshot.write_bytes(source)
        packed_path = out / "selected_project.bin"
        tool_output(state_tool, "pack", str(source_snapshot), "--strict", "--store",
                    "-o", str(packed_path))
        packed = read_bounded(packed_path, MAX_PACKED)
        if digest(packed) != PACKED_SHA256:
            raise ValueError("strict native packed bytes differ from selected pin")
        actual_records, bin_report = lunar_state.read_bin(packed)
        if (bin_report.code != "OK" or bin_report.skipped or bin_report.repaired
                or bin_report.unknown or
                lunar_state.records_text(actual_records) !=
                lunar_state.records_text(expected_records)):
            raise ValueError("native packed record stream differs from selected source")
        if (read_bounded(SOURCE, MAX_SOURCE) != source or
                digest(read_bounded(renderer, 64 * 1024 * 1024)) != render_hash or
                digest(read_bounded(state_tool, 64 * 1024 * 1024)) != tool_hash or
                tool_output(renderer, "--meta") != render_meta or
                tool_output(state_tool, "meta") != state_meta):
            raise ValueError("selected build inputs changed during preparation")
        write_blob(out, packed)
        receipt = dict(schema=1, selection=SELECTION,
                       source_path=SOURCE.relative_to(ROOT).as_posix(),
                       source_sha256=SOURCE_SHA256, renderer_sha256=render_hash,
                       state_tool_sha256=tool_hash, metadata_sha256=digest(render_meta),
                       packed_sha256=PACKED_SHA256, packed_bytes=len(packed),
                       records=len(expected_records), parameters=14,
                       linked_hal=dict(name="Dinghy", upstream_commit=
                                        "d44df7db09b98ccad2f1233b8f83f5f09c04829e",
                                        licence="GPL-3.0-only", linked_here=False),
                       distribution_reviewed=False, release_candidate=False,
                       installable=False, hardware_admitted=False,
                       native_link_verified=False, native_ram_verified=False)
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        source_snapshot.unlink()
        return receipt
    except BaseException:
        shutil.rmtree(out)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--state-tool", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.renderer, args.state_tool, args.out), indent=2))
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
