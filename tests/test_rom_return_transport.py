"""Offline actual-patched-C strict return-r01 protocol tests.

The local upstream source must be provided explicitly. No downloads, Pico
build, USB enumeration, device command or hardware inference occurs here.
"""

import os
from pathlib import Path
import re
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PIN = "a7fb5e8ac692c528f8ed29e325911a3f4b8111d6"
PATCHES = (
    "0001-pico2-reject-false-d-pullups.patch",
    "0002-exact-bot-completion.patch",
    "0003-fixed-return-r01-rom-mode.patch",
)
SOURCES = (
    "CMakeLists.txt", "pio/usb_key.pio", "src/recovery.c", "src/main.c",
    "src/pio_host.c", "src/pio_host.h", "src/recovery.h", "src/jieli_uboot.c",
    "src/jieli_uboot.h", "src/transporter_proto.h", "src/usb_device.c",
)


@pytest.fixture(scope="module")
def harness():
    source_value = os.environ.get("FM1_TRANSPORTER_SOURCE")
    if not source_value:
        pytest.skip("set FM1_TRANSPORTER_SOURCE to the pinned local upstream checkout")
    upstream = Path(source_value).resolve(strict=True)
    subprocess.run(["git", "-C", str(upstream), "cat-file", "-e", f"{PIN}^{{commit}}"], check=True)
    parent = ROOT / "scratch/rom-return-transport"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="actual-c-", dir=parent) as stage_name:
        stage = Path(stage_name)
        for relative in SOURCES:
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(subprocess.check_output(
                ["git", "-C", str(upstream), "show", f"{PIN}:{relative}"]
            ))
        subprocess.run(["git", "init", "--quiet", str(stage)], check=True)
        for patch in PATCHES:
            subprocess.run(["git", "apply", str(ROOT / "tools/fm1-transporter" / patch)],
                           cwd=stage, check=True)
        assert "R01_CALL_BOT" in (stage / "src/pio_host.c").read_text()
        assert "return_r01_proto.c" in (stage / "CMakeLists.txt").read_text()
        assert "return_r01_log_stub.c" in (stage / "CMakeLists.txt").read_text()

        fake = stage / "fake"
        (fake / "pico").mkdir(parents=True)
        (fake / "hardware").mkdir()
        (fake / "pico/stdlib.h").write_text(
            "#pragma once\n#include <stdint.h>\nuint64_t time_us_64(void);\n"
        )
        (fake / "hardware/sync.h").write_text(
            "#pragma once\n#define __dmb() __sync_synchronize()\n"
        )
        (fake / "pico/critical_section.h").write_text(
            "#pragma once\n#include <pthread.h>\n"
            "typedef struct { pthread_mutex_t mu; } critical_section_t;\n"
            "static inline void critical_section_init(critical_section_t *s) { "
            "pthread_mutex_init(&s->mu, 0); }\n"
            "static inline void critical_section_enter_blocking(critical_section_t *s) { "
            "pthread_mutex_lock(&s->mu); }\n"
            "static inline void critical_section_exit(critical_section_t *s) { "
            "pthread_mutex_unlock(&s->mu); }\n"
        )
        (fake / "tusb.h").write_text(
            "#pragma once\n#include <stdbool.h>\n#include <stdint.h>\n"
            "bool tud_cdc_n_connected(uint8_t);\n"
            "uint32_t tud_cdc_n_write_available(uint8_t);\n"
            "uint32_t tud_cdc_n_write(uint8_t,const void*,uint32_t);\n"
            "void tud_cdc_n_write_flush(uint8_t);\n"
        )
        binary = stage / "r01-harness"
        subprocess.run([
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread",
            "-DFM1T_RETURN_R01=1", "-I", str(fake), "-I", str(stage),
            str(ROOT / "tests/fixtures/fm1_return_r01_harness.c"), "-o", str(binary),
        ], check=True)
        yield binary


@pytest.mark.parametrize("case,counts,required,forbidden", [
    ("success", "1 1 1", ("OK rr01-ready", "OK rr01-upload mount=1", "OK rr01-call mount=1"), ("ERR",)),
    ("bad-payload", "0 0 1", ("ERR rr01-upload",), ("OK rr01-upload", "OK rr01-call")),
    ("extra-payload", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-upload",)),
    ("upload-fail", "1 0 1", ("ERR rr01-upload",), ("OK rr01-call",)),
    ("upload-detach", "1 0 1", ("ERR rr01-upload",), ("OK rr01-call",)),
    ("upload-extra-inflight", "1 0 1", ("ERR rr01-upload",), ("OK rr01-upload", "OK rr01-call", "ERR rr01-terminal")),
    ("concurrent-upload-extra", "1 0 1", ("ERR rr01-upload",), ("OK rr01-upload", "OK rr01-call", "ERR rr01-terminal")),
    ("call-fail", "1 1 1", ("ERR rr01-call",), ("OK rr01-call",)),
    ("call-detach", "1 1 1", ("ERR rr01-call",), ("OK rr01-call",)),
    ("call-extra-inflight", "1 1 1", ("ERR rr01-call",), ("OK rr01-call", "ERR rr01-terminal")),
    ("concurrent-call-extra", "1 1 1", ("ERR rr01-call",), ("OK rr01-call", "ERR rr01-terminal")),
    ("no-mount", "0 0 1", ("ERR rr01-ready",), ("OK rr01-ready",)),
    ("generic", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-ready",)),
    ("pipelined-ready", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-ready",)),
    ("premature-next-before-ready-reply", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-ready",)),
    ("split-next-before-ready-reply", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-ready", "OK rr01-upload")),
    ("pipelined-call", "1 0 1", ("ERR rr01-terminal",), ("OK rr01-call",)),
    ("premature-call-before-upload-reply", "1 0 1", ("ERR rr01-terminal",), ("OK rr01-upload", "OK rr01-call")),
    ("split-call-before-upload-reply", "1 0 1", ("ERR rr01-terminal",), ("OK rr01-upload", "OK rr01-call")),
    ("partial-timeout", "0 0 1", ("OK rr01-ready",), ("OK rr01-upload",)),
    ("cdc-disconnect", "0 0 1", ("OK rr01-ready",), ("OK rr01-upload",)),
    ("rx-during-cdc-write", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-upload", "OK rr01-call")),
    ("cr", "0 0 1", ("ERR rr01-terminal",), ("OK rr01-ready",)),
])
def test_actual_strict_protocol(harness, case, counts, required, forbidden):
    result = subprocess.check_output([str(harness), case], text=True)
    assert result.startswith(counts + " "), result
    for part in required:
        assert part in result
    for part in forbidden:
        assert part not in result


def test_default_recipe_and_generic_paths_are_untouched():
    assert "0003-fixed-return-r01" not in (ROOT / "tools/fm1-transporter/build.sh").read_text()
    manifest = ROOT / "tools/fm1-transporter/return-r01-build-manifest.json"
    assert '"uf2_sha256": null' in manifest.read_text()


def test_strict_usb_identity_and_reset_exclusion(harness):
    source = (Path(harness).parent / "src/usb_device.c").read_text()
    assert '"Lunar fixed ROM return-r01"' in source
    assert '"Return-r01 fixed data"' in source
    assert "#define USBD_ITF_MAX 4" in source
    reset_section = source.split("#if !FM1T_RETURN_R01", 2)[-1]
    assert "rom_reset_usb_boot_extra" in reset_section
    assert "*driver_count = 0;" in reset_section


def test_strict_core_ownership_and_retained_build_evidence(harness):
    stage = Path(harness).parent
    proto = (stage / "src/return_r01_proto.c").read_text()
    pio = (stage / "src/pio_host.c").read_text()
    assert "tud_cdc_n_connected" not in _function(proto, "fm1_proto_poll")
    assert "critical_section_enter_blocking" in _function(proto, "fm1_proto_rx")
    assert "critical_section_enter_blocking" in _function(proto, "publish_success")
    assert "static tuh_xfer_t x;" in _function(pio, "edpt_sync")
    host_task = _function(pio, "fm1_pio_host_task")
    assert host_task.index("fm1_proto_poll();") < host_task.index("tuh_task();")
    probe = _function(pio, "probe_descriptors")
    assert probe.count("r01_probe_live(daddr)") >= 7
    optional_log = probe.index("#if !FM1T_RETURN_R01")
    assert optional_log < probe.index("log_string(daddr") < probe.index("#endif", optional_log)
    main = (stage / "src/main.c").read_text()
    assert main.index("fm1_proto_init();") < main.index("tud_init(0);")
    assert "void log_drain(void) {}" in (stage / "src/return_r01_log_stub.c").read_text()
    script = (ROOT / "tools/fm1-transporter/build-rom-return.sh").read_text()
    for name in ("return-r01.elf", "return-r01.map", "return-r01.disasm",
                 "return-r01.nm", "compile_commands.json", "artifact-sha256.txt"):
        assert name in script


def test_cold_entry_requires_continuously_low_dp(harness):
    stage = Path(harness).parent
    source = (stage / "src/recovery.c").read_text()
    assert "recovery_target_detached_stable(50)" in (stage / "src/main.c").read_text()
    code = (
        "#include <stdbool.h>\n#include <stdint.h>\n"
        "static uint64_t now; static int samples; static int high_at;\n"
        "static uint64_t time_us_64(void) { return now; }\n"
        "static bool dp(void) { return samples++ == high_at; }\n"
        "static void sleep_us(unsigned n) { now += n; }\n"
        + _function(source, "recovery_target_detached_stable") + "\n"
        "int main(void) { high_at = 10; if (recovery_target_detached_stable(50)) return 1; "
        "now = 0; samples = 0; high_at = -1; "
        "return recovery_target_detached_stable(50) && samples == 500 ? 0 : 2; }\n"
    )
    path = stage / "actual_cold_entry.c"
    path.write_text(code)
    binary = stage / "actual_cold_entry"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_recipe_refuses_unpinned_inputs_before_output():
    script = ROOT / "tools/fm1-transporter/build-rom-return.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    out = ROOT / "scratch/rom-return-transport/invalid-build"
    assert not out.exists()
    result = subprocess.run(["bash", str(script), str(out)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 64, result.stderr
    assert not out.exists()


def test_fixed_write_cdb_crc_matches_actual_rom_cipher(harness):
    stage = Path(harness).parent
    source = (stage / "src/jieli_uboot.c").read_text()
    code = "#include <stdint.h>\n" + _function(source, "jl_crc16") + "\n"
    code += _function(source, "jl_crc_cipher") + "\n"
    code += (
        "int main(void) { unsigned char p[512] = {0x80, 0}; "
        "jl_crc_cipher(p, sizeof p); "
        "return jl_crc16(p, sizeof p, 0) == 0xC360 ? 0 : 1; }\n"
    )
    path = stage / "actual_cipher_crc.c"
    path.write_text(code)
    binary = stage / "actual_cipher_crc"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def _function(source: str, name: str) -> str:
    for match in re.finditer(rf"(?m)^(?:static )?[^\n]*\b{re.escape(name)}\(", source):
        brace = source.find("{", match.start())
        semicolon = source.find(";", match.start())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        end = source.find("\n}", brace)
        if end >= 0:
            return source[match.start():end + 2]
    raise AssertionError(f"actual function {name} absent")


@pytest.fixture(scope="module")
def pio_harness(harness):
    stage = Path(harness).parent
    source = (stage / "src/pio_host.c").read_text()
    start = source.index("typedef enum {")
    end = source.index("} r01_host_phase_t;", start) + len("} r01_host_phase_t;")
    names = (
        "fm1_host_return_arm_cold", "fm1_host_return_ready_generation",
        "fm1_host_return_claim_upload", "fm1_host_return_upload_complete",
        "fm1_host_return_claim_call", "fm1_host_return_terminal",
        "fm1_host_return_call_complete",
        "r01_allowed_cdb", "fm1_host_bot", "probe_inquiry",
    )
    (stage / "actual_pio_functions.inc").write_text(
        source[start:end] + "\nstatic r01_host_phase_t r01_phase;\n"
        "static uint32_t r01_mount_generation;\n" +
        "\n\n".join(_function(source, name) for name in names) + "\n"
    )
    binary = stage / "r01-pio-harness"
    subprocess.run([
        "cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-DFM1T_RETURN_R01=1",
        "-I", str(stage),
        str(ROOT / "tests/fixtures/fm1_return_r01_pio_harness.c"), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("case,expected", [
    ("upload-call", "2 1 0"),
    ("bad-upload-cdb", "0 1 0"),
    ("bad-upload-crc", "0 1 0"),
    ("bad-call-cdb", "1 1 0"),
    ("upload-detach", "1 1 0"),
    ("call-detach", "2 1 0"),
    ("wrong-generation", "0 0 1"),
    ("inquiry-ok", "1 0 1"),
    ("inquiry-bad", "1 0 1"),
    ("inquiry-short", "1 0 1"),
    ("inquiry-detach", "1 0 1"),
])
def test_actual_strict_pio_allowlist_and_identity(pio_harness, case, expected):
    assert subprocess.check_output([str(pio_harness), case], text=True).strip() == expected


@pytest.fixture(scope="module")
def boundary_harness(harness):
    stage = Path(harness).parent
    source = (stage / "src/pio_host.c").read_text()
    start = source.index("typedef enum {")
    end = source.index("} r01_host_phase_t;", start) + len("} r01_host_phase_t;")
    names = (
        "r01_probe_live", "fm1_host_return_terminal", "xfer_done",
        "edpt_sync", "probe_descriptors", "fm1_pio_host_task",
    )
    (stage / "actual_boundary_functions.inc").write_text(
        source[start:end] + "\nstatic r01_host_phase_t r01_phase;\n"
        + "\n\n".join(_function(source, name) for name in names) + "\n"
    )
    binary = stage / "r01-boundaries"
    subprocess.run([
        "cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-DFM1T_RETURN_R01=1",
        "-I", str(stage),
        str(ROOT / "tests/fixtures/fm1_return_r01_boundaries.c"), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("case,expected", [
    ("valid", "1 2 2 0"),
    ("device-terminal", "1 0 0 1"),
    ("header-terminal", "1 1 0 1"),
    ("config-terminal", "1 2 0 1"),
    ("out-open-terminal", "1 2 1 1"),
    ("malformed-tail", "1 2 0 0"),
    ("malformed-crossing", "1 2 0 0"),
    ("malformed-small-total", "1 1 0 0"),
    ("malformed-large-total", "1 1 0 0"),
    ("malformed-header-len", "1 1 0 0"),
    ("malformed-header-kind", "1 1 0 0"),
    ("malformed-second-header", "1 2 0 0"),
    ("malformed-short-interface", "1 2 0 0"),
    ("malformed-short-endpoint", "1 2 0 0"),
    ("endpoint-preterminal", "endpoint-preterminal"),
    ("endpoint-submit-terminal", "endpoint-submit-terminal"),
    ("endpoint-task-terminal", "endpoint-task-terminal"),
    ("endpoint-valid", "endpoint-valid"),
    ("task-preterminal", "task-preterminal"),
    ("task-dispatch-terminal", "task-dispatch-terminal"),
])
def test_actual_strict_descriptor_endpoint_and_task_boundaries(boundary_harness, case, expected):
    assert subprocess.check_output([str(boundary_harness), case], text=True).strip() == expected
