"""Offline selected Trio record refusal and current-app oracle.

The normal path links this checkout's bounded binary reader. During its
separate review only, LUNAR_SELECTED_PARSER_ROOT and _HEAD may point to an
exact frozen sibling source; that result is provisional, not accepted CI.
Build products live under pytest's caller-selected basetemp and are removable.
"""
import copy
import hashlib
import os
from pathlib import Path
import subprocess

from tools import lunar_state as state

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "engines/state/examples/init-starters/trio-init.lunar"
SOURCE_SHA256 = "46541967e4fa7321f4efe1105632de3613064a2fbcf7d71490cb647247a97c1b"
PACKED_SHA256 = "dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4"


def _makefile(tmp_path):
    sibling = os.environ.get("LUNAR_SELECTED_PARSER_ROOT")
    rules = []
    include = ""
    if sibling:
        parser = Path(sibling).resolve()
        expected = os.environ["LUNAR_SELECTED_PARSER_HEAD"]
        actual = subprocess.run(["git", "-C", str(parser), "rev-parse", "HEAD"],
                                check=True, text=True, capture_output=True).stdout.strip()
        assert actual == expected
        state_dir = parser / "engines/state"
        assert (state_dir / "state_bin.c").is_file()
        include = f"-I{state_dir} "
        rules += [
            f"PARSER := {state_dir}",
            "$(BUILD)/state/state/state_bin.o: $(PARSER)/state_bin.c",
            "\t@mkdir -p $(dir $@)",
            "\t$(CC) $(STATE_CFLAGS) -I$(PARSER) -c $< -o $@",
        ]
    rules += [
        f"PROOF := {ROOT}",
        "$(BUILD)/proof/selected_project.o: $(PROOF)/firmware/native/selected_project.c",
        "\t@mkdir -p $(dir $@)",
        f"\t$(CC) $(SIM_CFLAGS) {include}-I$(PROOF)/engines/state -I$(PROOF)/firmware/native -c $< -o $@",
        "$(BUILD)/proof/check.o: $(PROOF)/tests/fixtures/selected_project/check.c",
        "\t@mkdir -p $(dir $@)",
        f"\t$(CC) $(SIM_CFLAGS) {include}-I$(PROOF)/engines/state -I$(PROOF)/firmware/native -c $< -o $@",
        "$(BUILD)/proof-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) "
        "$(BUILD)/proof/selected_project.o $(BUILD)/proof/check.o",
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm -pthread",
    ]
    path = tmp_path / "proof.mk"
    path.write_text("\n".join(rules) + "\n")
    return path


def test_native_selected_trio_matches_current_app_and_refuses_extra_records(tmp_path):
    build = tmp_path / "build"
    fragment = _makefile(tmp_path)
    render, proof = build / "fm1-render", build / "proof-check"
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile",
        "-f", str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}",
        "FM1_MODULES=trio", "FM1_GPL_MODS=1", "FM1_DX7_SINE=trunc12",
        "OPT=-O1", "EXTRA=-DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1",
        "-j4", str(render), str(proof),
    ], check=True, timeout=300)

    source = SOURCE.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256
    names = state.Names.from_build(render)
    records, report = state.read_json(source, names)
    assert report.code == "OK"
    assert (report.skipped, report.repaired, report.unknown) == (0, 0, 0)
    assert len([r for r in records if r["rec"] == "param"]) == 14
    packed = state.write_bin(records, deflate_chunks=False)
    assert hashlib.sha256(packed).hexdigest() == PACKED_SHA256
    accepted = tmp_path / "trio.lunarbin"
    accepted.write_bytes(packed)

    mutations = {
        "missing-param": [r for r in records if not (r["rec"] == "param" and r["uid"] == 14)],
        "extra-info": records[:2] + [{"rec": "info", "key": "author", "text": "x"}] + records[2:],
        "wrong-engine": [{**r, "engine": "macro"} if r["rec"] == "unit" and r["engine"] == "trio"
                         else r for r in records],
        "out-of-range": [{**r, "f32": "4f000000"} if r["rec"] == "param" and r["uid"] == 6
                         else r for r in records],
        "missing-level": [r for r in records if r["rec"] != "level"],
    }
    refused = []
    for label, changed in mutations.items():
        data = state.write_bin(copy.deepcopy(changed), deflate_chunks=False)
        reread, bin_report = state.read_bin(data)
        assert bin_report.code == "OK" and reread
        path = tmp_path / f"{label}.lunarbin"
        path.write_bytes(data)
        refused.append(path)
    result = subprocess.run([str(proof), str(accepted), *(str(p) for p in refused)],
                            check=True, capture_output=True, text=True, timeout=90)
    assert "selected Trio proof passed: 14 params" in result.stdout
    print(result.stdout, end="")
