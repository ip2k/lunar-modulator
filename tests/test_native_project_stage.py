"""Actual app PROJECT replay; products remain in caller-owned pytest basetemp.
FM1_PROJECT_ORACLE points to four exact frozen baseline translation units.
"""
import os
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]
ORACLE_FILES = {
    'fm1_app_state.c': ('sim/src/fm1_app_state.o', 'SIM_CFLAGS', '-Istate -Ihost'),
    'state_bin.c': ('state/state/state_bin.o', 'STATE_CFLAGS', ''),
    'state_json_write.c': ('state/state/state_json_write.o', 'STATE_CFLAGS', ''),
    'seq_persist.c': ('c/seq/seq_persist.o', 'SEQ_CFLAGS', '-Iseq'),
}
@pytest.mark.parametrize('sanitize', [False, True])
def test_project_stage(tmp_path, sanitize):
    oracle = os.environ.get('FM1_PROJECT_ORACLE')
    results = []
    for baseline in ([False, True] if oracle else [False]):
        name = 'baseline' if baseline else 'current'
        build = tmp_path / name
        fragment = tmp_path / f'{name}.mk'
        rules = ''
        if baseline:
            for source, (obj, flags, includes) in ORACLE_FILES.items():
                rules += (f'$(BUILD)/{obj}: {Path(oracle).resolve()/source}\n'
                          '\t@mkdir -p $(dir $@)\n'
                          f'\t$(CC) $({flags}) {includes} -c $< -o $@\n')
        fragment.write_text(
            '$(BUILD)/project-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(BUILD)/project-check.o\n'
            '\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n'
            '$(BUILD)/project-check.o: $(SIM)/../../tests/fixtures/native_state/project.c\n'
            '\t@mkdir -p $(dir $@)\n'
            '\t$(CC) $(SIM_CFLAGS) -Istate -Ihost -c $< -o $@\n' + rules)
        if not baseline:
            with fragment.open('a') as f:
                f.write('$(BUILD)/transaction-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(BUILD)/transaction-check.o\n'
                        '\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n'
                        '$(BUILD)/transaction-check.o: $(SIM)/../../tests/fixtures/native_state/transaction.c\n'
                        '\t@mkdir -p $(dir $@)\n'
                        '\t$(CC) $(SIM_CFLAGS) -Istate -Ihost -c $< -o $@\n')
        extra = f'-DFM1_APP_STATE_EXTERNAL_WORKSPACE=1 -DFM1_PROJECT_BASELINE={int(baseline)}'
        if sanitize:
            extra += ' -fsanitize=address,undefined -fno-omit-frame-pointer'
        target = build / 'project-check'
        subprocess.run(['make', '-C', str(ROOT/'engines'), '-f', 'Makefile', '-f',
            str(ROOT/'sim/web/mk/sim.mk'), '-f', str(fragment), f'SIM={ROOT}/sim/web',
            f'BUILD={build}', 'FM1_GPL_MODS=1',
            'FM1_MODULES=test-sine,test-gain,dx7,drums,arp,lfo,env,calc,register,chance', '-j4',
            f'CC={os.environ.get("FM1_SIM_CC", "cc")}', f'CXX={os.environ.get("FM1_SIM_CXX", "c++")}',
            f'EXTRA={extra}', str(target), *([] if baseline else [str(build/'transaction-check')])], check=True, stdout=subprocess.DEVNULL)
        corpus = build / 'corpus'
        subprocess.run([str(target), str(corpus)], check=True, timeout=180)
        results.append(corpus.read_bytes())
        if not baseline:
            subprocess.run([str(build/'transaction-check')], check=True, timeout=180)
    if oracle:
        assert results[0] == results[1], 'frozen app/JSON/sequence/binary oracle mismatch'
