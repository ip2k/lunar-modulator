"""Bounded format/correspondence tests for the pinned private FM-1_500 composer."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "jieli"))
import compose_500_d7000_candidate as candidate  # noqa: E402


def retained_inputs():
    paths = (candidate.SOURCE, candidate.REFERENCE, candidate.APP, candidate.ELF,
             candidate.ARTIFACT_RECEIPT, candidate.BUILD_RECEIPT)
    if not all(path.exists() for path in paths):
        pytest.skip("pinned 092 source or FM-1_500 target build artifacts are unavailable")
    return (
        candidate.SOURCE.read_bytes(),
        candidate.REFERENCE,
        candidate.APP.read_bytes(),
        candidate.ELF.read_bytes(),
        candidate.ARTIFACT_RECEIPT.read_bytes(),
        candidate.BUILD_RECEIPT.read_bytes(),
    )


@pytest.fixture(scope="module")
def composed():
    source, reference, app, elf, artifact, receipt = retained_inputs()
    package, report = candidate.compose_bytes(source, reference, app, elf, artifact, receipt)
    return source, reference, app, elf, artifact, receipt, package, report


def test_private_candidate_reopens_all_layers_and_preserves_protected_payloads(composed):
    source, reference, app, elf, artifact, receipt, package, report = composed
    checked = candidate.verify_package(source, package, reference, app, elf, artifact, receipt)
    assert checked == report
    assert candidate._physical_identity(package) == "FM-1_500"
    assert report["package_identity"] == report["application_identity"] == "FM-1_500"
    assert report["package_bytes"] == len(package) == candidate.EXPECTED_CONTAINER_BYTES
    assert report["package_bytes"] <= candidate.MAX_CONTAINER_BYTES
    assert report["expanded_flash_bytes"] == 0xD7000
    assert report["app_bytes"] == 845272
    assert report["max_app_bytes_preserving_pinned_092_tail"] - report["app_bytes"] == 14408
    assert report["outer_integrity"] == {
        "header_crc_verified": True,
        "entry_list_crc_verified": True,
        "all_payload_crcs_verified": True,
    }
    assert set(report["protected_decoded_sha256"]) == {
        "uboot.boot", "isd_config.ini", "cfg_tool.bin", "cfg",
        "key_mac_descriptor",
    }
    assert report["installable"] is False
    assert report["hardware_admitted"] is False
    assert report["hardware_tested"] is False
    assert report["updater_acceptance_verified"] is False
    assert report["release_admitted"] is False


def test_identity_length_and_outer_crc_corruptions_are_rejected(composed):
    source, reference, app, elf, artifact, receipt, package, _ = composed
    wrong_identity = bytearray(package)
    wrong_identity[47] ^= 1
    with pytest.raises(ValueError):
        candidate.verify_package(source, bytes(wrong_identity), reference, app, elf, artifact, receipt)

    truncated = package[:-1]
    with pytest.raises(ValueError):
        candidate.verify_package(source, truncated, reference, app, elf, artifact, receipt)

    bad_crc = bytearray(package)
    bad_crc[20] ^= 1
    with pytest.raises(ValueError):
        candidate.verify_package(source, bytes(bad_crc), reference, app, elf, artifact, receipt)


def test_source_app_elf_and_both_receipts_are_exactly_pinned(composed):
    source, reference, app, elf, artifact, receipt, _, _ = composed
    with pytest.raises(ValueError, match="pinned public FM-1_092"):
        candidate.compose_bytes(source[:-1] + bytes([source[-1] ^ 1]), reference,
                                app, elf, artifact, receipt)
    with pytest.raises(ValueError, match="pinned target input"):
        candidate._verify_target(app[:-1] + bytes([app[-1] ^ 1]), elf, artifact, receipt)
    with pytest.raises(ValueError, match="pinned target input"):
        candidate._verify_target(app, elf[:-1] + bytes([elf[-1] ^ 1]), artifact, receipt)
    with pytest.raises(ValueError, match="artifact receipt SHA-256"):
        candidate._verify_target(app, elf, artifact[:-1] + bytes([artifact[-1] ^ 1]), receipt)
    with pytest.raises(ValueError, match="build receipt SHA-256"):
        candidate._verify_target(app, elf, artifact, receipt[:-1] + bytes([receipt[-1] ^ 1]))


def test_candidate_length_and_identity_marker_helpers_fail_closed():
    with pytest.raises(ValueError, match="fixed-length package identity"):
        candidate._set_physical_identity(b"\\xff" * 960, "FM-1_50")
    with pytest.raises(ValueError, match="shorter than"):
        candidate._physical_identity(b"short")
