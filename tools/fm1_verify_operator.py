#!/usr/bin/env python3
"""Compare V15 operator instruction execution with the separate integer model.

Reads a privately supplied application or FWSC package. Produces a compact
reproducible JSON report; performs no device I/O and writes no firmware.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random
import struct

try:
    from .fm1_operator import OperatorState, render_three_operator_block
    from .fm1_package import MAX_INPUT_SIZE, inspect_and_extract
    from .fm1_pi32 import V15_SHA256, run_operator_kernel
except ImportError:
    from fm1_operator import OperatorState, render_three_operator_block
    from fm1_package import MAX_INPUT_SIZE, inspect_and_extract
    from fm1_pi32 import V15_SHA256, run_operator_kernel


VECTOR_SET = "v15-three-operator-1"


def verification_vectors() -> list[dict]:
    """Stable boundary cases plus one deterministic case per supported shift."""
    vectors = []
    for start, target, increment, phase in (
        (0, 16384, 0, 0), (33, 0, 0xFFFFFFFF, 0xFFFFFFFF),
        (16352, 16384, 0x80000000, 0x7FFFFFFF), (8000, 8063, 12345, 45678),
    ):
        vectors.append({"id": f"boundary-{len(vectors) + 1}",
                        "operators": [[start, (16384 - target) << 14, increment, phase] for _ in range(3)],
                        "feedback": [0x7FFFFFFF, 0x7FFFFFFF], "kernel_feedback_shift": 2})
    generator = random.Random(0xF115)
    for shift in range(2, 17):
        vectors.append({"id": f"feedback-shift-{shift}",
                        "operators": [[generator.randint(0, 16384), generator.randint(0, 16384 << 14),
                                       generator.getrandbits(32), generator.getrandbits(32)] for _ in range(3)],
                        "feedback": [generator.getrandbits(32), generator.getrandbits(32)],
                        "kernel_feedback_shift": shift})
    return vectors


def _sample_hash(samples) -> str:
    return hashlib.sha256(struct.pack(f"<{len(samples)}i", *samples)).hexdigest()


def verify_operator(application: bytes) -> dict:
    """Verify this finite vector set, not all states or physical CPU behavior."""
    if (not isinstance(application, bytes) or len(application) != 581564
            or hashlib.sha256(application).hexdigest() != V15_SHA256):
        raise ValueError("verification requires the exact decoded FM-1_015 application")
    rows = []
    for vector in verification_vectors():
        states = tuple(OperatorState(*words) for words in vector["operators"])
        expected = render_three_operator_block(states, vector["feedback"],
                                               kernel_feedback_shift=vector["kernel_feedback_shift"])
        actual = run_operator_kernel(application, vector["operators"], vector["feedback"],
                                     kernel_feedback_shift=vector["kernel_feedback_shift"])
        mismatches = [i for i, (left, right) in enumerate(zip(expected.samples, actual["samples"])) if left != right]
        sample_match = len(actual["samples"]) == len(expected.samples) and not mismatches
        expected_words = tuple((before[0], target, before[2], before[3])
                               for before, target in zip(vector["operators"], expected.target_attenuations))
        state_match = actual["operator_words"] == expected_words
        history_match = actual["feedback"] == expected.feedback
        rows.append({**vector, "passed": sample_match and state_match and history_match,
                     "sample_count": len(actual["samples"]), "sample_match": sample_match,
                     "state_match": state_match, "feedback_match": history_match,
                     "first_sample_mismatch": mismatches[0] if mismatches else None,
                     "interpreter_output_sha256": _sample_hash(actual["samples"]),
                     "reference_output_sha256": _sample_hash(expected.samples),
                     "executed_instructions": actual["instructions"]})
    return {"schema_version": 1, "kind": "fm1-operator-verification", "vector_set": VECTOR_SET,
            "application_sha256": V15_SHA256, "passed": all(row["passed"] for row in rows),
            "case_count": len(rows), "sample_count": sum(row["sample_count"] for row in rows),
            "cases": rows, "device_io_performed": False, "hardware_behavior_verified": False,
            "scope": "V15 three-operator kernel; samples, feedback and state writes on the listed inputs.",
            "limitations": ["This comparison evaluates the interpreter and mathematical model under reconstructed ISA semantics.",
                           "Parallel-packet read-before-write timing is inferred from static evidence.",
                           "This finite vector set does not cover every state, other algorithms, complete voices, or effects.",
                           "No physical CPU execution, waveform capture, flashing or recovery is performed."]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path)
    parser.add_argument("--kind", choices=("app", "fwsc"), default="app")
    parser.add_argument("--output", type=Path, help="new JSON report; defaults to stdout")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("report output already exists; choose a new filename")
        with args.firmware.open("rb") as stream:
            raw = stream.read(MAX_INPUT_SIZE + 1)
        if not raw or len(raw) > MAX_INPUT_SIZE:
            raise ValueError("firmware input must contain 1 to 16 MiB")
        application = inspect_and_extract(raw)[1] if args.kind == "fwsc" else raw
        report = verify_operator(application)
        report["source"] = {"kind": args.kind, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        else:
            print(encoded, end="")
        return 0 if report["passed"] else 1
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
