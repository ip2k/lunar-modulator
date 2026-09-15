"""Synthetic subset-ISA checks and optional private V15 byte execution."""

import os
from pathlib import Path
import random
import struct

import pytest

from tools.fm1_pi32 import (Memory, Pi32Error, Pi32Machine, _check_experiment_ranges,
                            run_operator_experiment, run_operator_kernel)


CODE = 0x1000
DATA = 0x2000


def machine(code, registers=None, budget=100):
    memory = Memory()
    raw = bytes.fromhex(code)
    memory.map(CODE, raw, 'rx', 'synthetic instructions')
    memory.map(DATA, bytes(64), 'rw', 'synthetic data')
    return Pi32Machine(memory, registers=registers, instruction_budget=budget), CODE + len(raw)


def test_memory_enforces_complete_ranges_and_permissions():
    memory = Memory()
    memory.map(DATA, b'abcd', 'r')
    memory.map(DATA + 4, b'efgh', 'w')
    assert memory.read(DATA, 4) == b'abcd'
    for action in (lambda: memory.write(DATA, b'x'), lambda: memory.read(DATA, 2, access='x'),
                   lambda: memory.read(DATA + 4, 1), lambda: memory.read(DATA + 3, 2),
                   lambda: memory.read(DATA, 1, access='w')):
        with pytest.raises(Pi32Error):
            action()
    memory.write(DATA + 4, b'changed'[:4])


@pytest.mark.parametrize('address,data,permissions', [
    (-1, b'a', 'r'), (0xFFFFFFFF, b'ab', 'r'), (0, b'', 'r'),
    (0, b'a', 'q'), (0, b'a', ''), (True, b'a', 'r')])
def test_mapping_domain(address, data, permissions):
    with pytest.raises(Pi32Error):
        Memory().map(address, data, permissions)


def test_overlapping_mappings_fail_without_replacing_bytes():
    memory = Memory()
    memory.map(DATA, b'keep', 'r')
    with pytest.raises(Pi32Error, match='overlapping'):
        memory.map(DATA + 3, b'changed', 'rw')
    assert memory.read(DATA, 4) == b'keep'


def test_arithmetic_wrap_then_signed_shift():
    # r0 += r3; r0 >>>= r5. The sum wraps before its sign is interpreted.
    vm, end = machine('3018 d81a', {'r0': 0x7FFFFFFF, 'r3': 1, 'r5': 1})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == 0xC0000000


@pytest.mark.parametrize('count', [32, 0xFFFFFFFF])
def test_unknown_shift_count_semantics_are_rejected(count):
    vm, end = machine('d81a', {'r0': 123, 'r5': count})
    with pytest.raises(Pi32Error, match='shift count'):
        vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == 123


def test_halfword_sign_and_unsigned_bit_extraction():
    # r7 = r7.l(s); r5=uextra(r7,p:10,l:5).
    vm, end = machine('ff17 b5e11475', {'r7': 0x0000FC00})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r7'] == 0xFFFFFC00
    assert vm.registers['r5'] == 31


def test_bit_extraction_crossing_word_boundary_is_rejected():
    vm, end = machine('b5e1887f', {'r7': 0xFFFFFFFF})  # position31, length2
    with pytest.raises(Pi32Error, match='bit extraction'):
        vm.run(CODE, stop_address=end)


def test_future_signed_load_is_not_silently_zero_extended(monkeypatch):
    import tools.fm1_pi32 as interpreter
    original = interpreter.decode_instruction

    def extended_decoder(*args):
        instruction = original(*args)
        instruction['mnemonic'] = 'signed_word_load_added_later'
        return instruction

    vm, end = machine('1065', {'r1': DATA})
    monkeypatch.setattr(interpreter, 'decode_instruction', extended_decoder)
    with pytest.raises(Pi32Error, match='memory instruction semantics'):
        vm.run(CODE, stop_address=end)


def test_conditional_branch_skips_exactly_one_short_instruction():
    # if(r4==0) goto+2; r1=1; r2=1.
    vm, end = machine('0441 4121 4221', {'r4': 0})
    result = vm.run(CODE, stop_address=end)
    assert vm.registers['r1'] == 0
    assert vm.registers['r2'] == 1
    assert result['instructions'] == 2


@pytest.mark.parametrize('value,expected', [(0, 9), (-1, 3)])
def test_predicate_signed_halfword_decision(value, expected):
    # ifs(r7>=0) {r0=r5}. Predicate state is local to one instruction.
    vm, end = machine('37ed0000 5016', {'r7': value, 'r0': 3, 'r5': 9})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == expected


def test_packet_store_reads_value_before_companion_register_write():
    # r0=r7 # [r1+36]=r0. This is the V15 target-store hazard, with synthetic data.
    vm, end = machine('70d6 9069', {'r0': 1234, 'r7': 16383, 'r1': DATA})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == 16383
    assert struct.unpack('<I', vm.memory.read(DATA + 36, 4))[0] == 1234


def test_packet_store_reads_address_before_companion_register_write():
    # r2=16383 # [r2+4]=r3. The store must use the previous pointer.
    vm, end = machine('42f0ff3f a361', {'r2': DATA, 'r3': 9012})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r2'] == 16383
    assert struct.unpack('<I', vm.memory.read(DATA + 4, 4))[0] == 9012


def test_packet_fault_is_atomic():
    vm, end = machine('70d6 9069', {'r0': 1234, 'r7': 16383, 'r1': 0x80000000})
    before = dict(vm.registers)
    with pytest.raises(Pi32Error, match='unmapped'):
        vm.run(CODE, stop_address=end)
    assert vm.registers == before
    assert vm.instructions == 0


def test_ambiguous_double_write_packet_is_rejected_atomically():
    vm, end = machine('70d6 5016', {'r0': 1234, 'r7': 16383, 'r5': 99})
    with pytest.raises(Pi32Error, match='same register'):
        vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == 1234


@pytest.mark.parametrize('predicate_value', [-1, 0])
def test_predicate_of_parallel_packet_remains_unsupported(predicate_value):
    vm, end = machine('37ed0000 70d6 9069', {'r7': predicate_value, 'r0': 12})
    with pytest.raises(Pi32Error, match='predicated parallel'):
        vm.run(CODE, stop_address=end)
    assert vm.registers['r0'] == 12


def test_postincrement_store_uses_old_address_then_advances():
    vm, end = machine('d8ec05b0', {'r0': DATA, 'r11': 0x12345678})
    vm.run(CODE, stop_address=end)
    assert vm.memory.read(DATA, 4) == bytes.fromhex('78563412')
    assert vm.registers['r0'] == DATA + 4


def test_push_pop_restores_registers_stack_and_return_address():
    vm, end = machine('7f04 47e0aabb 5f04', {'sp': DATA + 60, 'r7': 1234, 'rets': CODE + 8})
    vm.run(CODE, stop_address=end)
    assert vm.registers['r7'] == 1234
    assert vm.registers['sp'] == DATA + 60


def test_instruction_budget_stops_valid_self_loop():
    vm, end = machine('f79f', budget=3)
    with pytest.raises(Pi32Error, match='budget'):
        vm.run(CODE, stop_address=end)
    assert vm.instructions == 3


@pytest.mark.parametrize('code,pattern', [('ffff00000000', 'unsupported'), ('c0ff', 'unmapped')])
def test_unsupported_and_truncated_instructions_fail(code, pattern):
    vm, end = machine(code)
    with pytest.raises(Pi32Error, match=pattern):
        vm.run(CODE, stop_address=end)


def test_code_execution_permission_is_required():
    memory = Memory()
    memory.map(CODE, bytes(2), 'r')
    with pytest.raises(Pi32Error, match='access denied'):
        Pi32Machine(memory).run(CODE, stop_address=CODE + 2)


def test_wrong_application_is_rejected_before_address_assumptions():
    with pytest.raises(Pi32Error, match='exact verified'):
        run_operator_kernel(bytes(581564), ((0, 0, 0, 0),) * 3)


@pytest.mark.parametrize('start,size', [(0, 1), (0x85284, 1), (0x85283, 2),
                                       (0x89F8D, 2), (0x8AF8D, 2)])
def test_experiment_requires_entire_patch_inside_one_allowed_region(start, size):
    with pytest.raises(Pi32Error, match='fit entirely'):
        _check_experiment_ranges([{'offset': start, 'expected_hex': '00' * size}])


@pytest.mark.parametrize('start,size', [(0x85064, 0x220), (0x89F8E, 0x1000)])
def test_experiment_allows_exact_region_boundaries(start, size):
    _check_experiment_ranges([{'offset': start, 'expected_hex': '00' * size}])


def test_experiment_requires_original_exact_stock_image():
    with pytest.raises(Pi32Error, match='exact verified'):
        run_operator_experiment(bytes(581564), [], ((0, 0, 0, 0),) * 3)


@pytest.mark.skipif(not os.environ.get('FM1_V15_APPLICATION'), reason='optional private V15 application not configured')
def test_private_v15_byte_execution_against_separate_reference():
    from tools.fm1_operator import OperatorState, render_three_operator_block

    application = Path(os.environ['FM1_V15_APPLICATION']).read_bytes()
    generator = random.Random(0xF115)
    boundary = [(0, 16384, 0, 0), (33, 0, 0xFFFFFFFF, 0xFFFFFFFF),
                (16352, 16384, 0x80000000, 0x7FFFFFFF), (8000, 8063, 12345, 45678)]
    cases = []
    for start, target, increment, phase in boundary:
        cases.append(([(start, (16384 - target) << 14, increment, phase)] * 3,
                      (0x7FFFFFFF, 0x7FFFFFFF), 2))
    for shift in range(2, 17):
        rows = [(generator.randint(0, 16384), generator.randint(0, 16384 << 14),
                 generator.getrandbits(32), generator.getrandbits(32)) for _ in range(3)]
        cases.append((rows, (generator.getrandbits(32), generator.getrandbits(32)), shift))
    for rows, history, shift in cases:
        result = run_operator_kernel(application, rows, history, kernel_feedback_shift=shift)
        reference = render_three_operator_block(tuple(OperatorState(*row) for row in rows), history,
                                                kernel_feedback_shift=shift)
        assert result['samples'] == reference.samples
        assert result['feedback'] == reference.feedback
        assert tuple(row[1] for row in result['operator_words']) == reference.target_attenuations
        for before, after in zip(rows, result['operator_words']):
            assert (after[0], after[2], after[3]) == (before[0], before[2], before[3])
        assert result['instructions'] < 20000
        assert not result['device_io_performed']


@pytest.mark.skipif(not os.environ.get('FM1_V15_APPLICATION'), reason='optional private V15 application not configured')
def test_private_half_scale_experiment_and_exact_rollback():
    import hashlib
    import json
    from tools.fm1_rebuild import rebuild_application, rollback_application

    original = Path(os.environ['FM1_V15_APPLICATION']).read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    patches = [{'offset': 0x85256, 'expected_hex': 'c0f10df0', 'replacement_hex': 'c0f10cf0',
                'label': 'Offline final operator output shift 13 to 12'}]
    # Two quiet positive modulators, followed by a carrier in its first quarter.
    # Changed feedback stays positive and cannot activate either modulator.
    rows = ((16384, 0, 0, 0), (16384, 0, 0, 0), (1, (16384 - 1) << 14, 16 << 12, 0))
    stock = run_operator_kernel(original, rows)
    experiment = run_operator_experiment(original, patches, rows)
    assert all(value > 0 for value in stock['samples'])
    assert tuple(value * 2 for value in experiment['samples']) == stock['samples']
    assert tuple(value * 2 for value in experiment['feedback']) == stock['feedback']
    assert experiment['operator_words'] == stock['operator_words']
    assert experiment['source_sha256'] == source_hash
    assert experiment['status'] == 'experimental'
    assert experiment['experimental'] and not experiment['hardware_behavior_verified']
    assert not experiment['device_io_performed']
    modified, independent_manifest = rebuild_application(original, patches, expected_source_sha256=source_hash)
    executed_hash = hashlib.sha256(modified).hexdigest()
    assert experiment['executed_image_sha256'] == experiment['application_sha256'] == executed_hash
    assert executed_hash != source_hash
    assert experiment['manifest'] == independent_manifest
    assert hashlib.sha256(original).hexdigest() == source_hash
    assert json.loads(json.dumps(experiment))['manifest']['source_sha256'] == source_hash
    restored, reverse = rollback_application(modified, experiment['manifest'])
    assert restored == original
    assert reverse['result_sha256'] == source_hash
    with pytest.raises(Pi32Error, match='exact verified'):
        run_operator_kernel(modified, rows)


@pytest.mark.skipif(not os.environ.get('FM1_V15_APPLICATION'), reason='optional private V15 application not configured')
def test_private_experiment_rejects_bad_preimage_and_unsupported_code():
    original = Path(os.environ['FM1_V15_APPLICATION']).read_bytes()
    rows = ((16384, 0, 0, 0),) * 3
    with pytest.raises(Pi32Error, match='expected bytes'):
        run_operator_experiment(original, [{'offset': 0x85064, 'expected_hex': '00',
                                           'replacement_hex': '01'}], rows)
    with pytest.raises(Pi32Error, match='unsupported instruction'):
        run_operator_experiment(original, [{'offset': 0x85064, 'expected_hex': original[0x85064:0x8506A].hex(),
                                           'replacement_hex': 'ffff00000000'}], rows)
