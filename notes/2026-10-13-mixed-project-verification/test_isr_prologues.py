"""Negative checks for the ISR allocation-prefix admission condition."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'isr_prologues', Path(__file__).with_name('inspect-isr-prologues.py'))
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def row(pc, text):
    return pc, b'\0\0', text


def test_backward_branch_after_prologue_is_allowed():
    result = inspector.check_region(0, 8, [row(0, '[--sp] = rets'),
        row(2, 'nop'), row(4, 'if (r0 != 0) goto -4'), row(6, 'pc = [sp++]')])
    assert result['relative_branch_count'] == 1
    assert result['allocation_prefix_end'] == '0x2'


@pytest.mark.parametrize('rows,end,message', [
    ([row(0, '[--sp] = rets'), row(2, 'goto -4')], 4,
     'branch into allocation prefix'),
    ([row(0, 'if (r0 != 0) goto 2'), row(2, 'sp += -4'), row(4, 'rts')], 6,
     'allocation after control flow'),
    ([row(0, 'nop'), row(4, 'rts')], 6, 'instruction coverage gap'),
    ([row(0, 'goto -1'), row(2, 'rts')], 4, 'branch into instruction'),
    ([row(0, 'tbh [r0]')], 2, 'unsupported control flow'),
    ([row(0, 'goto r0')], 2, None),
    ([row(0, 'pc = r0')], 2, 'unsupported PC write'),
    ([row(0, 'goto 10')], 2, 'external branch'),
])
def test_unsafe_or_unmodeled_region_is_refused(rows, end, message):
    with pytest.raises(AssertionError, match=message):
        inspector.check_region(0, end, rows)
