"""Opt-in audio-only actual app, scanner and target adapter; no hardware."""
import os
from pathlib import Path
import subprocess
from tools.native.prepare_selected_project import prepare
ROOT = Path(__file__).resolve().parents[1]


def test_actual_selected_audio_owner(tmp_path):
    build = tmp_path / "build"
    prepared = tmp_path / "prepared"
    sources = ["selected_project", "selected_diagnostic_app", "selected_interactive_owner",
               "selected_interactive_platform", "diagnostic_spi_model", "diagnostic_display",
               "diagnostic_transport"]
    fragment = tmp_path / "proof.mk"
    fragment.write_text(
        f"PROOF := {ROOT / 'firmware/native'}\n"
        f"BLOB := {prepared}\n"
        f"AUDIO_FIXTURE := {ROOT / 'tests/fixtures/selected_audio_owner'}\n"
        f"RETURN := {ROOT / 'firmware/third_party/selected-return'}\n"
        "$(BUILD)/proof/return-%.o: $(RETURN)/%.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(RETURN) -I$(PROOF) -Istate -c $< -o $@\n"
        "$(BUILD)/proof/%.o: $(PROOF)/%.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -Istate -I$(BLOB) -c $< -o $@\n"
        f"$(BUILD)/proof/check.o: {ROOT / 'tests/fixtures/selected_audio_owner/check.c'}\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -Istate -I$(BLOB) -I$(PROOF)/../third_party/dinghy/hal -I$(RETURN) -I$(AUDIO_FIXTURE) -Wno-unused-function -c $< -o $@\n"
        "$(BUILD)/proof/blob.o: $(BLOB)/selected_project_blob.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(BLOB) -c $< -o $@\n"
        "$(BUILD)/proof-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) "
        + " ".join(f"$(BUILD)/proof/{s}.o" for s in sources)
        + " $(BUILD)/proof/blob.o $(BUILD)/proof/check.o $(BUILD)/proof/return-selected_return.o $(BUILD)/proof/return-selected_return_pi32v2.o\n"
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm -pthread\n")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + (
        " -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1"
        " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1 -DLUNAR_SELECTED_INTERACTIVE_PROOF=1"
        " -DLUNAR_SELECTED_PROJECT_STAGE_PROOF=1 -DLUNAR_SELECTED_AUDIO_OWNER_PROOF=1"
        " -DLUNAR_SELECTED_RETURN_OFFLINE_PROOF=1 -DLUNAR_SELECTED_RETURN_PI32V2_BINDING=1"
        " -DLUNAR_SELECTED_RETURN_TARGET_INJECTED=1")
    cmd = ["make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
           str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
           f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_MODULES=trio",
           "FM1_GPL_MODS=1", "FM1_DX7_SINE=trunc12", "OPT=-O1", "-j4",
           f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
           f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}", f"EXTRA={extra}"]
    # Preparation and the actual app share the requested instrumentation.
    render, state = build / "fm1-render", build / "fm1-state"
    subprocess.run([*cmd, str(render), str(state)], check=True, timeout=300)
    receipt = prepare(render, state, prepared)
    assert receipt["packed_bytes"] == 597 and not receipt["hardware_admitted"]
    exe = build / "proof-check"
    subprocess.run([*cmd, str(exe)], check=True, timeout=300)
    modes = [(m,) for m in ("positive", "wrap", "unqualified", "empty", "overflow", "clock-back",
                            "clock-frozen-zero", "clock-frozen-subcadence")]
    modes += [("fault", str(n)) for n in range(1, 8)]
    modes += [("reenter", str(n)) for n in range(2, 8)]
    modes += [("early-irq", str(n)) for n in (2, 3)]
    for mode in modes:
        result = subprocess.run([str(exe), *mode], text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout, end="")


def test_audio_owner_is_separate_complete_plan(tmp_path):
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location("audio_builder", ROOT / "tools/native/build_diagnostic.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    aggregate = builder.diagnostic_plan(True, tmp_path, return_candidate=True, aggregate_layout=True)
    audio = builder.diagnostic_plan(True, tmp_path, return_candidate=True, aggregate_layout=True, audio_owner=True)
    package = ROOT / "firmware/third_party/selected-return"
    assert audio["extra"] == [package / "selected_audio_owner_platform.c"
                               if p == package / "selected_return_platform.c" else p
                               for p in aggregate["extra"]]
    for key in ("modules", "arena_bytes", "reader_bytes", "undefined_root", "linker"):
        assert audio[key] == aggregate[key]
    assert audio["reader_bytes"] == 65536
    assert audio["profile"] == "sdk-free-selected-trio-audio-owner-candidate-v1"
    for selected, returned, aggregated in ((False, False, False), (True, False, False), (True, True, False)):
        with pytest.raises(ValueError, match="complete selected aggregate"):
            builder.diagnostic_plan(selected, tmp_path, return_candidate=returned,
                                    aggregate_layout=aggregated, audio_owner=True)
    for name in ("dinghy", "selected-return"):
        builder.check_inventory(ROOT / "firmware/third_party" / name)
    manifest = builder.manifest(True, return_candidate=True, aggregate_layout=True, audio_owner=True)
    assert "tools/native/build_selected_trio_audio_owner.py" in manifest


def test_legacy_audio_initializer_statement_order():
    """Mechanical factoring proof; no claim about compiler or silicon timing."""
    import hashlib
    import re
    source = (ROOT / "firmware/third_party/dinghy/hal/fm1_audio.h").read_text()
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    def body(name):
        start = source.index("{", source.index("void " + name + "("))
        depth = 1
        end = start + 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        return source[start + 1:end - 1]
    legacy = body("fm1_audio_init")
    legacy = legacy.replace("fm1_audio_prepare(buf, half_words, isr, prio);", body("fm1_audio_prepare"))
    legacy = legacy.replace("fm1_audio_start_prepared();", body("fm1_audio_start_prepared"))
    legacy = legacy.replace("fm1_audio_finish_start();", body("fm1_audio_finish_start"))
    normalized = re.sub(r"\s+", "", legacy).encode()
    # Exact original6ece initializer body, comments/whitespace removed only.
    assert hashlib.sha256(normalized).hexdigest() == "a9474483a856bd54666ff24109238ac383ff641b652c8c84601d77d3cbc52640"
