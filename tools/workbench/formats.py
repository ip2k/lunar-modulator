#!/usr/bin/env python3
"""Offline DX7 SysEx <-> existing Lunar sound files. No device transport.

Uses Lunar's existing MIT state codec and saved build metadata. Vendor format
facts and deliberately unsupported conversions: notes/workbench/formats.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import dx7_bank, lunar_state  # noqa: E402

REPORT_SCHEMA = "lunar-workbench-loss/1"
MAX_INPUT = 466944
_NAMES = None


class ConversionError(ValueError):
    """A refused conversion; code is stable for callers."""

    def __init__(self, code, message, report=None):
        self.code = code
        self.report = report
        super().__init__(f"{code}: {message}")


def _check(condition, code, message):
    if not condition:
        raise ConversionError(code, message)


def _names():
    global _NAMES
    if _NAMES is None:
        _NAMES = lunar_state.Names.from_file(ROOT / "sim/web/www/meta.json")
    return _NAMES


def _voice(data):
    _check(len(data) == 155, "VOICE_SIZE", "a VCED voice is 155 bytes")
    limits = lunar_state.OP_MAX * 6 + lunar_state.GLOB_MAX
    for i, maximum in enumerate(limits):
        _check(data[i] <= maximum, "VOICE_RANGE", f"voice byte {i}: {data[i]} exceeds {maximum}")
    _check(all(32 <= b <= 126 for b in data[145:]), "VOICE_NAME",
           "Lunar requires ten printable ASCII voice-name bytes")
    return bytes(data)


def _unpack_vmem(data):
    """Expand format fields; reject unused bits rather than discard them."""
    out = bytearray()
    for at in range(0, 102, 17):
        b = data[at:at + 17]
        _check(b[11] < 16 and b[12] < 128 and b[13] < 32 and b[15] < 64,
               "RESERVED_BITS", "VMEM operator contains nonzero reserved bits")
        out.extend(b[:11])
        out.extend((b[11] & 3, b[11] >> 2, b[12] & 7, b[13] & 3,
                    b[13] >> 2, b[14], b[15] & 1, b[15] >> 1, b[16], b[12] >> 3))
    _check(data[110] < 32 and data[111] < 16, "RESERVED_BITS",
           "VMEM algorithm/sync contains nonzero reserved bits")
    out.extend(data[102:110])
    out.extend((data[110], data[111] & 7, data[111] >> 3))
    out.extend(data[112:116])
    out.extend((data[116] & 1, (data[116] >> 1) & 7, data[116] >> 4))
    out.extend(data[117:])
    return _voice(out)


def _pack_vmem(voice):
    """Inverse field layout, retaining all validated VCED parameter values."""
    v = _voice(voice)
    out = bytearray()
    for at in range(0, 126, 21):
        b = v[at:at + 21]
        out.extend(b[:11])
        out.extend((b[11] | b[12] << 2, b[13] | b[20] << 3,
                    b[14] | b[15] << 2, b[16], b[17] | b[18] << 1, b[19]))
    out.extend(v[126:134])
    out.extend((v[134], v[135] | v[136] << 3))
    out.extend(v[137:141])
    out.append(v[141] | v[142] << 1 | v[143] << 4)
    out.extend(v[144:])
    return bytes(out)


def read_syx(data):
    """Read exactly one Yamaha single-voice or 32-voice message."""
    _check(isinstance(data, bytes), "INPUT_TYPE", "input must be bytes")
    _check(len(data) in (163, 4104), "SYX_SIZE",
           "expected one 163-byte single voice or 4104-byte 32-voice bank")
    bank = len(data) == 4104
    _check(data[:2] == b"\xf0\x43" and data[-1] == 0xF7 and data[2] < 16
           and all(b < 128 for b in data[1:-1]), "SYX_FRAME",
           "expected a Yamaha DX7 bulk dump on channel 0..15 with seven-bit data")
    size = 4096 if bank else 155
    _check(data[3] == (9 if bank else 0) and (data[4] << 7 | data[5]) == size,
           "SYX_HEADER", "DX7 type and declared payload length must match")
    _check(sum(data[6:-1]) % 128 == 0, "CHECKSUM", "DX7 checksum mismatch")
    voices = ([_unpack_vmem(data[6 + k * 128:6 + (k + 1) * 128]) for k in range(32)]
              if bank else [_voice(data[6:-2])])
    return voices, data[2]


def _sound_doc(voices):
    return {"lunar": "1.0", "kind": "sound",
            "sound": {"engine": "dx7", "params": {"Patch": "User 1"}},
            "dx7": [{"slot": i + 1, "name": v[145:].decode("ascii").rstrip(" "),
                     "ops": [list(v[k * 21:(k + 1) * 21]) for k in range(6)],
                     "globals": list(v[126:145])} for i, v in enumerate(voices)]}


def _canonical(data):
    try:
        recs, report = lunar_state.read_any(data, _names())
        _check(not (report.skipped or report.repaired or report.unknown),
               "LUNAR_REPAIR", "refusing state requiring skipped, repaired or unavailable fields")
        text, report = lunar_state.write_json(recs, _names())
        _check(not report.skipped, "LUNAR_REPAIR", "refusing fields the codec would skip")
        return text.encode(), json.loads(text)
    except lunar_state.Refused as error:
        raise ConversionError("LUNAR_" + error.code, str(error)) from error


def _report(source, target, count):
    return {"schema": REPORT_SCHEMA, "source_format": source, "target_format": target,
            "voice_count": count, "preserved": ["all 155 VCED bytes per voice",
            "voice order and slots", "ten-byte voice names"],
            "losses": [], "defaults": [], "limitations": [
                "DX7 voice data only; no promise of identical rendered audio.",
                "No device reads, writes, MIDI output or network transport.",
                "SysEx channel is transport metadata; Lunar does not store it."]}


def import_syx(data):
    """Return a consumable canonical Lunar sound and a loss/default report."""
    voices, channel = read_syx(data)
    out, _ = _canonical(json.dumps(_sound_doc(voices)).encode())
    report = _report("syx", "lunar-sound", len(voices))
    report["source_channel"] = channel
    report["defaults"] = [
        {"field": "sound.params.Patch", "value": "User 1",
         "reason": "first imported voice selected; remaining voices occupy User 2..32"},
        {"field": "sound", "reason": "Lunar engine/macro, level and empty FX defaults; absent from SysEx"}]
    return out, report


def export_syx(data, channel=0, allow_loss=False):
    """Export 1 or 32 contiguous slots; refuse destructive state loss by default."""
    _check(type(channel) is int and 0 <= channel <= 15, "CHANNEL", "channel must be 0..15")
    _, doc = _canonical(data)
    _check(doc["kind"] == "sound" and doc["sound"]["engine"] == "dx7",
           "UNSUPPORTED_ENGINE", "export requires a Lunar sound using engine dx7")
    rows = doc.get("dx7", [])
    _check(len(rows) in (1, 32), "VOICE_COUNT",
           "export needs 1 or 32 voices; no invented voices or silent truncation")
    _check([row["slot"] for row in rows] == list(range(1, len(rows) + 1)),
           "VOICE_SLOTS", "export needs contiguous User slots beginning with User 1")
    voices = [_voice(bytes(sum(row["ops"], []) + row["globals"]) +
                      row["name"].ljust(10).encode("ascii")) for row in rows]
    _, baseline = _canonical(json.dumps(_sound_doc(voices)).encode())
    report = _report("lunar-sound", "syx", len(voices))
    report["target_channel"] = channel
    for key in sorted(set(doc) - {"lunar", "kind", "sound", "dx7"}):
        report["losses"].append({"field": key, "reason": "DX7 SysEx has no representation for this Lunar field"})
    for key, value in doc["sound"].items():
        if value != baseline["sound"].get(key):
            report["losses"].append({"field": "sound." + key,
                "reason": "Lunar macros, mix, selected patch, FX and MIDI FX are not DX7 voice parameters"})
    if report["losses"] and not allow_loss:
        raise ConversionError("LOSS_REQUIRES_OPT_IN",
            "conversion discards Lunar fields; --allow-loss is required after reviewing the proposed report", report)
    payload = b"".join(_pack_vmem(v) for v in voices) if len(voices) == 32 else voices[0]
    header = bytes((0xF0, 0x43, channel, 9, 32, 0)) if len(voices) == 32 else bytes((0xF0, 0x43, channel, 0, 1, 27))
    return header + payload + bytes((dx7_bank.checksum(list(payload)), 0xF7)), report


def _envelope(data, magic, versions, sizes):
    _check(len(data) in sizes and len(data) >= 16, "SIZE", "unsupported container size")
    tag, version, size, crc = struct.unpack_from("<4sIII", data)
    _check(tag == magic and version in versions, "VERSION", "unsupported magic/version or nonzero reserved bytes")
    payload = data[16:]
    _check(size == len(payload), "SIZE", "declared payload size differs from file")
    _check(zlib.crc32(payload) == crc, "CHECKSUM", "container CRC32 mismatch")
    return payload, version


def inspect_file(data):
    """Inspect offline file structure; vendor envelopes are not full DSP validation."""
    _check(isinstance(data, bytes) and len(data) <= MAX_INPUT, "SIZE", "input exceeds the pilot bound")
    if data.startswith(b"\xf0"):
        voices, channel = read_syx(data)
        return {"format": "syx", "version": "DX7 VCED" if len(voices) == 1 else "DX7 VMEM",
                "voice_count": len(voices), "channel": channel, "supported_conversion": True,
                "validation_scope": "frame, checksum, reserved bits, parameter and name ranges"}
    if data.startswith(b"FM1P"):
        p, version = _envelope(data, b"FM1P", (3, 4), (4064, 4080, 4280))
        _check(p[3852] == version == (3 if len(p) == 4048 else 4),
               "VERSION", "project payload version/length mismatch")
        if len(p) == 4264:
            t = p[4064:]
            _check(t[:4] == b"FM1T" and 128 not in t[4:196] and
                   zlib.crc32(t[:196]) == struct.unpack_from("<I", t, 196)[0],
                   "TUNING", "tuning block magic/data/CRC mismatch")
        return {"format": "fm1", "version": version, "payload_bytes": len(p),
                "tuning": len(p) == 4264, "supported_conversion": False,
                "validation_scope": "container and optional tuning envelope only",
                "reason": "vendor engines, 8-track sequence/chords/locks/lengths, FX, tuning and external sample references have no approved Lunar mapping"}
    if data.startswith(b"FM1T"):
        p, version = _envelope(data, b"FM1T", (1,), (239,))
        return {"format": "fm1t", "version": version, "payload_bytes": len(p),
                "engine_type": p[0], "supported_conversion": False,
                "validation_scope": "container envelope only; preset semantics not validated",
                "reason": "vendor engine/program, controls, sequence length and sample references need mapping; export an FM voice as DX7 .syx instead"}
    if data.startswith(b"FM1S"):
        _check(512 <= len(data) <= 466944, "SIZE", "sample bank size outside readable range")
        words = struct.unpack_from("<8I", data)
        _check(words[1] == 1 and words[2] == len(data) and words[4:] == (0, 32000, 0, 0),
               "VERSION", "unsupported sample bank header/version/rate")
        crc_data = data[:12] + b"\0" * 8 + data[20:]
        _check(zlib.crc32(crc_data) == words[3], "CHECKSUM", "sample bank CRC32 mismatch")
        _check(not any(data[480:512]), "RESERVED_BITS", "sample header reserved area must be zero")
        end, entries = 512, []
        max_frames = ((466944 - 512) // 228) * 320
        for slot in range(16):
            offset, frames, size = struct.unpack_from("<III", data, 32 + slot * 28)
            name = data[44 + slot * 28:60 + slot * 28]
            _check(offset == end and frames <= max_frames and size == ((frames + 319) // 320) * 228
                   and size <= len(data) - end and name[-1] == 0
                   and all(b == 0 or 32 <= b <= 126 for b in name),
                   "SAMPLE_ENTRY", f"invalid sample entry {slot + 1}")
            _check(all(data[p:p + 4] == b"\x01\x45\x14\x5a" for p in range(offset, offset + size, 228)),
                   "SAMPLE_CHUNK", f"invalid SEA5 chunk marker in slot {slot + 1}")
            _check(slot < 8 or (frames == 0 and not any(name)), "SAMPLE_ENTRY", "reserved sample slots must be empty")
            if slot < 8:
                entries.append({"slot": slot + 1, "frames": frames, "encoded_bytes": size})
            end += size
        _check(end == len(data), "SIZE", "trailing bytes after sample entries")
        return {"format": "fm1s", "version": 1, "sample_rate": 32000, "slots": entries,
                "supported_conversion": False, "within_new_transfer_capacity": len(data) <= 462848,
                "validation_scope": "bank header, checksum, table, padding and SEA5 chunk markers; no audio decoding",
                "reason": "shared 8-slot SEA5 sample bank is separate from projects; no Lunar sample-bank mapping"}
    raise ConversionError("UNSUPPORTED_FORMAT", "expected DX7 .syx, FM1P project, FM1T timbre or FM1S sample bank")


def _read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_INPUT + 1)
    _check(len(data) <= MAX_INPUT, "SIZE", "input exceeds the pilot bound")
    return data


def _save_pair(output, payload, report_path, report, input_path):
    paths = [Path(output), Path(report_path)]
    resolved = [p.resolve() for p in paths]
    _check(resolved[0] != resolved[1] and Path(input_path).resolve() not in resolved,
           "OUTPUT_ALIAS", "input, output and report must be different paths")
    _check(not any(p.exists() or p.is_symlink() for p in paths),
           "OUTPUT_EXISTS", "output/report already exists; choose new paths")
    # Exclusive creation defeats a collision after preflight. If the second
    # reservation fails, remove only the first new file created by this call.
    made = []
    handles = []
    try:
        for p in paths:
            handles.append(p.open("xb"))
            made.append(p)
        handles[0].write(payload)
        handles[1].write((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        for stream in handles:
            stream.close()
    except BaseException:
        for stream in handles:
            stream.close()
        for p in made:
            p.unlink()
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("import", "export", "inspect"))
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--report")
    ap.add_argument("--allow-loss", action="store_true")
    ap.add_argument("--channel", type=int, default=0, help="SysEx channel 0..15")
    args = ap.parse_args(argv)
    try:
        data = _read(args.input)
        if args.command == "inspect":
            print(json.dumps(inspect_file(data), indent=2, sort_keys=True))
            return 0
        _check(args.output and args.report, "OUTPUT_REQUIRED", "conversion requires -o OUTPUT and --report REPORT")
        if args.command == "import":
            info = inspect_file(data)
            _check(info["supported_conversion"], "UNSUPPORTED_CONVERSION", info.get("reason", "no approved mapping"))
            out, report = import_syx(data)
        else:
            out, report = export_syx(data, args.channel, args.allow_loss)
        _save_pair(args.output, out, args.report, report, args.input)
        print(f"Wrote {args.output}; loss/default report: {args.report}")
        return 0
    except (ConversionError, OSError, ValueError) as error:
        refusal = {"code": getattr(error, "code", "IO_OR_VALUE"), "message": str(error)}
        if getattr(error, "report", None) is not None:
            refusal["report"] = error.report
        print(json.dumps(refusal), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

