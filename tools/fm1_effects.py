"""Source-bound FM-1 effects evidence and a limited offline waveshaper model.

See docs/18-effects-decoding.md and docs/19-effects-mathematics.md. Annotations
require the complete measured V15 application hash. Candidate effect names
are hypotheses; neither annotations nor the scalar model prove device audio
behavior. This module performs no device or filesystem I/O.
"""

import hashlib
import math
import struct

try:
    from .fm1_dsp import hyperbolic_tangent_table
except ImportError:
    from fm1_dsp import hyperbolic_tangent_table


V15_SHA256 = "306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203"
MAX_IMAGE_SIZE = 16 * 1024 * 1024
_XIP_BASE = 0x02000120
_STATE_BASE = 0x01C0E840
_DISPATCH_OFFSET = 0x457A4
_LABEL_OFFSET = 0x4E9B8
_NAMES = ("Filter", "Reverb", "Delay", "Distortion", "Chorus", "Phaser")
_ROLES = ("initialization", "parameter_update", "process")
_PROCESS_CALLS = (0x8746C, 0x87498, 0x874C4, 0x874F0, 0x8751C, 0x87548)


def analyze_effects(blob: bytes) -> dict:
    """Return V15 callback/state evidence, or withhold it for any other bytes.

    Callback offsets identify entries only. Their complete function extents
    are not inferred from entry fingerprints or proximity to another entry.
    """
    if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_IMAGE_SIZE:
        raise ValueError("application must contain 1 to 16 MiB of bytes")
    digest = hashlib.sha256(blob).hexdigest()
    matched = digest == V15_SHA256
    report = {
        "schema_version": 1, "kind": "fm1-effects-analysis",
        "size": len(blob), "sha256": digest,
        "profile": {"name": "FM-1_015" if matched else None, "matched": matched,
                    "basis": "complete application SHA-256"},
        "effects": [], "dispatch_table": None, "label_table": None,
        "dispatcher": None, "state_layout": None,
        "limitations": [
            "Effect names are inferred from label order and code observations; UI indexing is not fully traced.",
            "Callback addresses identify entries, not complete function boundaries.",
            "No complete effect implementation or hardware audio equivalence is established.",
        ],
        "device_io_performed": False,
    }
    if not matched:
        report["limitations"].insert(0, "Effects annotations are withheld because the application SHA-256 differs from the measured V15 image.")
        return report

    labels = []
    for effect_id, name in enumerate(_NAMES):
        entry_offset = _DISPATCH_OFFSET + effect_id * 12
        addresses = struct.unpack_from("<III", blob, entry_offset)
        callbacks = [
            {"role": role, "field_offset": field * 4,
             "runtime_address": address, "file_offset": address - _XIP_BASE,
             "role_confidence": "verified" if role == "process" else "inferred"}
            for field, (role, address) in enumerate(zip(_ROLES, addresses))
        ]
        label_address = struct.unpack_from("<I", blob, _LABEL_OFFSET + effect_id * 4)[0]
        labels.append({"text": name, "runtime_address": label_address,
                       "file_offset": label_address - _XIP_BASE})
        report["effects"].append({
            "id": effect_id, "candidate_name": name,
            "name_confidence": "inferred", "name_evidence": "Ordered UI label table; binding to dispatch ID remains inferred.",
            "record_file_offset": entry_offset, "record_size": 12,
            "callbacks": callbacks,
            "object_pointer_address": _STATE_BASE + 0x488 + effect_id * 4,
        })
    report["dispatch_table"] = {
        "file_offset": _DISPATCH_OFFSET, "runtime_address": _XIP_BASE + _DISPATCH_OFFSET,
        "record_count": 6, "record_size": 12, "size": 72,
        "sha256": hashlib.sha256(blob[_DISPATCH_OFFSET:_DISPATCH_OFFSET + 72]).hexdigest(),
        "confidence": "verified",
        "evidence": "Six little-endian pointer triples; the six-slot dispatcher loads the process pointer at record +8.",
    }
    report["label_table"] = {
        "file_offset": _LABEL_OFFSET, "runtime_address": _XIP_BASE + _LABEL_OFFSET,
        "labels": labels, "contents_confidence": "verified", "dispatch_binding_confidence": "inferred",
        "consumer_file_offsets": [0x25F76, 0x25F7A],
        "binding_limit": "The UI indexes names by IDs in three-byte records; its incoming data pointer has not been linked to the dispatcher's global state.",
    }
    report["dispatcher"] = {
        "file_offset": 0x872BE, "runtime_address": 0x01C0337E, "size": 656,
        "sha256": hashlib.sha256(blob[0x872BE:0x8754E]).hexdigest(),
        "confidence": "verified",
        "boundary_evidence": "Entry at 0x872be, terminating return at 0x8754c, next prologue at 0x8754e.",
        "process_call_file_offsets": list(_PROCESS_CALLS),
        "process_arguments": {"names": ["parameter_byte", "audio_buffer", "frame_count"],
                              "confidence": "inferred from register setup"},
        "parallel_note": "Callback loads paired with argument assignments can read the previous register value.",
    }
    report["state_layout"] = {
        "base_runtime_address": _STATE_BASE, "slot_count": 6, "confidence": "verified accesses",
        "base_load_file_offset": 0x872C2,
        "fields": [
            {"name": "object_pointer", "offset": 0x488, "stride": 4, "width": 4, "index": "effect_id"},
            {"name": "slot_effect_id", "offset": 0x18E7, "stride": 3, "width": 1, "index": "chain_slot"},
            {"name": "enabled", "offset": 0x18E8, "stride": 3, "width": 1, "index": "effect_id"},
            {"name": "process_parameter", "offset": 0x18E9, "stride": 3, "width": 1, "index": "effect_id"},
        ],
        "evidence": "Shared state base and indexed loads observed in the fingerprinted six-slot dispatcher; parameter meaning remains unresolved.",
    }
    report["effects"][3]["output_stage"] = {
        "model": "tanh_output_stage_f32", "confidence": "inferred from instruction dataflow",
        "file_offset": 0x1CF5E, "table_file_offset": 0x54398,
        "input_scale": 512, "maximum_interpolated_index": 511, "saturated_value": 1.0,
        "rounding": "The reference assumes nearest-even float32 after each operation; device rounding is unmeasured.",
        "scope": "Final lookup, sign and gain only; preceding filters and parameter mapping are excluded.",
    }
    return report


def _finite_float32(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float32 value")
    try:
        rounded = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError(f"{name} must fit finite float32") from exc
    if not math.isfinite(rounded):
        raise ValueError(f"{name} must be a finite float32 value")
    return rounded


def tanh_output_stage_f32(sample: float, gain: float = 1.0, *, rounding_assumption: str) -> float:
    """Model the inferred final stage of callback 3, not the whole effect.

    The caller must explicitly choose rounding_assumption="nearest-even".
    Inputs and each separate arithmetic result are rounded to IEEE float32;
    no fused multiply-add is used. The device's actual rounding mode has not
    been measured. Float-to-integer conversion is assumed to truncate.

    The model excludes preceding filters and the user parameter-to-gain map.
    Nonfinite values and lookup positions outside signed-int32 range are
    rejected because the hardware conversion behavior is unresolved.
    """
    if rounding_assumption != "nearest-even":
        raise ValueError("the reference only supports the explicit nearest-even rounding assumption")
    sample = _finite_float32(sample, "sample")
    gain = _finite_float32(gain, "gain")
    position = abs(_finite_float32(sample * 512.0, "lookup position"))
    if position >= 2**31:
        raise ValueError("lookup position exceeds the modeled signed-int32 conversion range")
    index = int(position)
    value = 1.0
    if index <= 511:
        table = hyperbolic_tangent_table()
        delta = _finite_float32(table[index + 1] - table[index], "table difference")
        fraction = _finite_float32(position - float(index), "fraction")
        interpolated = _finite_float32(delta * fraction, "interpolation product")
        value = _finite_float32(table[index] + interpolated, "interpolated value")
    signed = _finite_float32(value * math.copysign(1.0, sample), "signed value")
    return _finite_float32(signed * gain, "output")
