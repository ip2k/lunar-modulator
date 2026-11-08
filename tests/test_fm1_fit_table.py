"""The fit-table tool and the variant preparer's guards (docs/18 M2), on synthetic ELFs only."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from test_fm1_budget import image, synthetic_elf  # noqa: E402


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT/rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


T = load('fm1_fit_table', 'tools/jieli/fm1_fit_table.py')


def write(tmp_path, name, **kw):
    secs, syms = image(**kw)
    p = tmp_path/(name + '.elf')
    p.write_bytes(synthetic_elf(secs, syms))
    return p


def test_row_sums_load_images_and_margins(tmp_path):
    p = write(tmp_path, 'a', text=1000, data=2000, bss=3000, heap=60000, cache=1000)
    r = T.row('a', p)
    assert r['app_bytes'] == 1000 + 2000 + 1000
    assert r['slot_margin'] == 581564 - 4000
    assert r['heap'] == 60000
    assert r['cache_ram_used'] == 1000


def test_table_orders_rows_and_diffs_against_the_first(tmp_path, capsys):
    a = write(tmp_path, 'a', text=5000)
    b = write(tmp_path, 'b', text=1000)
    assert T.main([f'base={a}', f'small={b}', '--diff', '2']) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[1].startswith('base') and lines[2].startswith('small')
    assert '-4,000' in lines[2]
    assert 'small against base' in out


def test_bad_pair_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit):
        T.main(['no-equals-sign'])


def test_variant_preparer_refuses_an_unknown_entry(tmp_path):
    V = load('fit_variant', 'tools/jieli/prepare-fit-variant.py')
    with pytest.raises(SystemExit):
        V.main(['--sdk', str(tmp_path), '--source', str(tmp_path), '--out', str(tmp_path/'o'),
                '--pipeline-system-archive', str(tmp_path/'x'), '--off', 'not_an_entry'])
    # and every entry it may switch off exists in the preset it changes
    P = load('pipeline_prepare', 'tools/jieli/prepare-pipeline-devkit.py')
    assert 'drums_ready_convert' in P.PRESET


def test_the_module_set_is_a_make_variable_with_the_soak_default():
    text = (ROOT/'tools/jieli/devkit-renderer-sdk.mk').read_text()
    assert 'LUNAR_MODULES ?= dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance' in text
    assert text.count('FM1_MODULES=$(LUNAR_MODULES)') == 1
