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
    assert result == f'#define LUNAR_ID "{value}"\n' + source
    assert '#define OTA_IDENTITY (recovery_active ? "FM-1_000" : LUNAR_ID)' in result
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
        identity.platform_with_identity('#define LUNAR_ID "FM-1_991"', "FM-1_500")


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


@pytest.mark.parametrize("loader, product", [(False, "Lunar Modulator"),
                                            (True, "Lunar Modulator Update")])
def test_usb_string_descriptor_wire_identity(tmp_path, loader, product):
    # Compile the real declarations so descriptor byte counts are checked
    # independently of C spelling and for both application/loader branches.
    source = (ROOT / "firmware/third_party/dinghy/src/usb.c").read_text()
    start = source.index("static const uint8_t STR0")
    end = source.index("static int get_desc", start)
    fixture = tmp_path / "strings.c"
    fixture.write_text("#include <stdint.h>\n#include <stdio.h>\n" +
                       ("#define LUNAR_LOADER 1\n" if loader else "") +
                       source[start:end] +
                       "int main(void) { fwrite(STR1, 1, sizeof STR1, stdout); "
                       "fwrite(STR2, 1, sizeof STR2, stdout); return 0; }\n")
    executable = tmp_path / "strings"
    subprocess.run(["cc", str(fixture), "-o", str(executable)], check=True)
    data = subprocess.check_output([str(executable)])
    decoded = []
    while data:
        size, descriptor_type = data[:2]
        assert descriptor_type == 3 and size >= 2 and size % 2 == 0
        assert size <= len(data)
        decoded.append(data[2:size].decode("utf-16le"))
        data = data[size:]
    assert decoded == ["Lunar Modulator", product]


def test_lunar_platform_usb_configuration_emits_expected_audio_descriptor(tmp_path):
    """Compile the platform's selected LUNAR_* settings through usb.c descriptors."""
    import re

    platform = (ROOT / "firmware/third_party/dinghy/src/platform.c").read_text()
    usb = (ROOT / "firmware/third_party/dinghy/src/usb.c").read_text()
    names = ("LUNAR_OTA", "LUNAR_CDC", "LUNAR_UAC", "LUNAR_UART")
    definitions = []
    for name in names:
        match = re.search(rf"^#define {name} ([^\n]+)$", platform, re.M)
        assert match, name
        definitions.append(match.group(0))
    assert [line.split()[-1] for line in definitions] == ["1", "0", "1", "0"]
    assert "#define LUNAR_UAC_48K 1" in usb
    descriptor_start = usb.index("#define CDC_IF")
    descriptor_end = usb.index("typedef char cfg_len_ok", descriptor_start)
    descriptor_source = usb[descriptor_start:descriptor_end]
    fixture = tmp_path / "config.c"
    fixture.write_text(
        "#include <stdint.h>\n" + "\n".join(definitions) +
        "\n#define LUNAR_UAC_48K 1\n#define LUNAR_USB_PID 1\n"
        "#define UAC_MAXP 196u\n" + descriptor_source +
        "\n#include <stdio.h>\n"
        "int main(void) { if (DEV_DESC[8] != 0x09 || DEV_DESC[9] != 0x12 "
        "|| DEV_DESC[10] != 1 || DEV_DESC[11] != 0) return 1; "
        "printf(\"%u %u %u %u\\n\", "
        "(unsigned)sizeof DEV_DESC, (unsigned)sizeof CFG_DESC, "
        "CFG_DESC[4], (unsigned)(CFG_DESC[2] | (CFG_DESC[3] << 8))); "
        "for (unsigned i=0;i<sizeof CFG_DESC;i++) printf(\"%02x\", CFG_DESC[i]); "
        "return 0; }\n"
    )
    executable = tmp_path / "config"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    str(fixture), "-o", str(executable)], check=True,
                   capture_output=True, text=True)
    output = subprocess.check_output([str(executable)], text=True).splitlines()
    assert output[0] == "18 178 3 178"
    cfg = bytes.fromhex(output[1])
    assert cfg[:9] == bytes([9, 2, 178, 0, 3, 1, 0, 0x80, 50])
    assert bytes([0x44, 0xAC, 0x00, 0x80, 0xBB, 0x00]) in cfg
    assert b"FELUCCA" not in (platform + usb).encode()
    assert b"FELUCCA-LOADER-1" in (ROOT / "firmware/third_party/dinghy/src/ota.c").read_bytes()
