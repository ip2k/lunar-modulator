"""Native identity override stays bounded and leaves historical probes intact."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "native_firmware_identity", ROOT / "tools/native/firmware_identity.py")
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def test_default_preserves_pinned_probe_source():
    source = (ROOT / "firmware/third_party/dinghy/src/platform.c").read_text()
    assert identity.platform_with_identity(source) == source
    assert identity.identity_configuration()["application_identity"] == "FM-1_990"


@pytest.mark.parametrize("value", ["FM-1_500", "FM-1_599"])
def test_lunar_override_preserves_recovery_and_does_not_claim_acceptance(value):
    source = (ROOT / "firmware/third_party/dinghy/src/platform.c").read_text()
    result = identity.platform_with_identity(source, value)
    assert result == f'#define FELUCCA_ID "{value}"\n' + source
    assert '#define OTA_IDENTITY (recovery_active ? "FM-1_000" : FELUCCA_ID)' in result
    receipt = identity.identity_configuration(value)
    assert receipt["explicit"]
    for field in ("package_identity_verified", "updater_acceptance_verified",
                  "hardware_identity_verified"):
        assert receipt[field] is False


@pytest.mark.parametrize("value", ["FM-1_092", "FM-1_990", "FM-1_600", "FM-1_50",
                                  "FM-1_500\n", 'FM-1_500"\n#error injected',
                                  "FM-1_５００", 500, True, ""])
def test_rejects_stock_foreign_malformed_and_injected_identities(value):
    with pytest.raises(ValueError):
        identity.identity_configuration(value)


def test_changed_vendor_guard_is_refused():
    with pytest.raises(ValueError, match="guard changed"):
        identity.platform_with_identity('#define FELUCCA_ID "FM-1_991"', "FM-1_500")


def test_cli_refuses_invalid_identity_before_creating_build(tmp_path):
    out = tmp_path / "out"
    result = subprocess.run([
        sys.executable, str(ROOT / "tools/native/build_application_probe.py"),
        "--toolchain", str(tmp_path / "tc"), "--catalogue", str(tmp_path / "catalogue"),
        "--build", str(out), "--firmware-identity", "FM-1_092"],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert "native Lunar identity" in result.stderr
    assert not out.exists()
