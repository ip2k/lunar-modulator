"""Reproducible, source-bound verification reports and CLI output behavior."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools.fm1_verify_operator import verification_vectors, verify_operator
from tools import fm1_verify_operator


def test_vector_set_covers_each_feedback_shift_and_is_independent_per_call():
    vectors = verification_vectors()
    assert len(vectors) == 19
    assert {v["kernel_feedback_shift"] for v in vectors} == set(range(2, 17))
    assert vectors == verification_vectors()
    vectors[0]["operators"][0][0] = 77
    assert verification_vectors()[0]["operators"][0][0] == 0


@pytest.mark.parametrize("blob", [b"FM-1_015\0", bytes(581564)], ids=["identity-only", "wrong-content"])
def test_wrong_image_never_gets_a_passing_report(blob):
    with pytest.raises(ValueError, match="exact decoded"):
        verify_operator(blob)


@pytest.mark.skipif(not os.environ.get("FM1_V15_APPLICATION"), reason="optional private V15 application not configured")
@pytest.mark.parametrize("state_count", [0, 2, 4])
def test_incomplete_or_extra_interpreter_state_fails_verification(monkeypatch, state_count):
    original_runner = fm1_verify_operator.run_operator_kernel
    one_vector = verification_vectors()[:1]

    def corrupted_runner(*args, **kwargs):
        result = original_runner(*args, **kwargs)
        words = result["operator_words"]
        result["operator_words"] = (words + words[:1])[:state_count]
        return result

    monkeypatch.setattr(fm1_verify_operator, "run_operator_kernel", corrupted_runner)
    monkeypatch.setattr(fm1_verify_operator, "verification_vectors", lambda: one_vector)
    report = verify_operator(Path(os.environ["FM1_V15_APPLICATION"]).read_bytes())
    assert not report["passed"]
    assert not report["cases"][0]["state_match"]
    assert report["cases"][0]["sample_match"] and report["cases"][0]["feedback_match"]
    assert not any("agree" in statement for statement in report["limitations"])


@pytest.mark.skipif(not os.environ.get("FM1_V15_APPLICATION"), reason="optional private V15 application not configured")
def test_private_verification_cli_report_and_existing_file_preservation(tmp_path):
    application = os.environ["FM1_V15_APPLICATION"]
    output = tmp_path / "report.json"
    command = [sys.executable, "-m", "tools.fm1_verify_operator", application, "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] and report["case_count"] == 19 and report["sample_count"] == 1216
    assert not report["hardware_behavior_verified"] and not report["device_io_performed"]
    assert str(Path(application)) not in output.read_text(encoding="utf-8")
    assert all(row["interpreter_output_sha256"] == row["reference_output_sha256"] for row in report["cases"])
    original = output.read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode == 2
    assert output.read_bytes() == original
