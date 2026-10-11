"""Exact compiled core-reset protocol guard; all exchanges are mocks."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_core_reset as core
from fm1_uboot_read import request, RAM
from tests.test_loader_reset import prepared, Mock

IMAGE = bytes.fromhex('600060e0800b00ef10002000f79f')
SOURCE = b'''/* SPDX-License-Identifier: MIT. Independent fixed core-reset experiment. */
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r0 = 0x10000;
    [r0] |= 0x10;
    csync
1:
    goto 1b;
.size _start, .-_start
'''


@pytest.fixture
def args(prepared, monkeypatch):
    values = copy.deepcopy(prepared[1])
    monkeypatch.setattr(core, 'ENTRY_SHA', hashlib.sha256(values['entry_log']).hexdigest())
    values['source'] = SOURCE
    return values


def bind(args):
    mock = Mock()
    mock.receipt = args['receipt_path']
    original_binding = mock.binding
    def binding():
        value = original_binding()
        value.pop('simulated')  # This distinct guard does not require simulation.
        return value
    mock.binding = binding
    return core.prepare_core_reset(IMAGE, **args).bind(mock), mock


def test_exact_compiled_pins_sequence(args):
    assert hashlib.sha256(IMAGE).hexdigest() == core.IMAGE_SHA
    assert hashlib.sha256(SOURCE).hexdigest() == core.SOURCE_SHA
    guard, mock = bind(args)
    assert guard.run_reset() == {'attempted': True, 'retry': False,
        'physical_identity_attested': False, 'reset_observed': False}
    assert len(mock.calls) == 3
    assert mock.calls[0] == request(0x12, 'rom')
    cdb, block, size = mock.calls[1]
    assert hashlib.sha256(block).hexdigest() == core.BLOCK_SHA
    assert cdb.hex() == 'fb0601c02000020000a794ffffffffff' and size == 0
    assert mock.calls[2] == (bytes.fromhex('fb0801c020000001ffffffffffffffff'), b'', 16)
    from fm1_ram_recovery import scramble_block
    assert scramble_block(block) == IMAGE + bytes(498)
    assert mock.closed == 1
    events = [json.loads(e) for e in args['receipt_path'].read_text().splitlines()]
    assert all(e['physical_identity_attested'] is False and e['reset_observed'] is False for e in events)
    assert args['receipt_path'].stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        guard.run_reset()


@pytest.mark.parametrize('fault', ['image', 'image_length', 'source', 'entry', 'stale', 'future', 'nan', 'usb'])
def test_factory_rejects_before_transport(args, fault):
    values = copy.deepcopy(args)
    image = IMAGE
    if fault == 'image':
        image = bytes(len(image))
    elif fault == 'image_length':
        image += b'\x00'
    elif fault in ('source', 'entry'):
        key = 'source' if fault == 'source' else 'entry_log'
        values[key] += b'\n'
    elif fault == 'stale':
        values['observed_at'] -= 11
    elif fault == 'future':
        values['observed_at'] += 10
    elif fault == 'nan':
        values['observed_at'] = float('nan')
    else:
        values['observation']['devnum'] = '22'
    with pytest.raises(ValueError):
        core.prepare_core_reset(image, **values)
    assert not values['receipt_path'].exists()


@pytest.mark.parametrize('stage,allowed', [('inquiry', 0x12), ('upload', 0xFB06), ('jump', 0xFB08)])
def test_every_opcode_lowest_stage_allowlist(args, stage, allowed):
    guard, mock = bind(args)
    guard._stage = stage
    for op in range(65536):
        if op != allowed:
            with pytest.raises(ValueError):
                guard.build_request(op, 0, b'')
    assert not mock.calls
    guard.close()


@pytest.mark.parametrize('fault', ['payload', 'short', 'address', 'inquiry', 'early_jump'])
def test_order_and_payload_exact(args, fault):
    guard, mock = bind(args)
    if fault == 'early_jump':
        with pytest.raises(ValueError):
            guard.cmd(0xFB08, address=RAM)
        assert not mock.calls
        return
    guard.cmd(0x12)
    op, address, data = 0xFB06, RAM, guard._block
    if fault == 'payload':
        data = bytes(512)
    elif fault == 'short':
        data = data[:-1]
    elif fault == 'address':
        address += 512
    else:
        op, address, data = 0x12, 0, b''
    with pytest.raises(ValueError):
        guard.cmd(op, address=address, payload=data)
    assert len(mock.calls) == 1 and mock.closed == 1


@pytest.mark.parametrize('op', [0x12, 0xFB06, 0xFB08])
@pytest.mark.parametrize('mode', ['lost', 'short', 'swap'])
def test_ambiguous_operation_latches_and_never_replays(args, op, mode):
    guard, mock = bind(args)
    setattr(mock, {'lost': 'failure', 'short': 'bad', 'swap': 'change'}[mode], op)
    with pytest.raises((ValueError, OSError)):
        guard.run_reset()
    count = len(mock.calls)
    assert mock.closed == 1
    with pytest.raises(ValueError):
        guard.run_reset()
    with pytest.raises(ValueError):
        guard.cmd(op)
    assert len(mock.calls) == count


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('fault', ['devnum', 'path', 'vid', 'pid', 'busnum', 'disconnect', 'stale', 'session'])
def test_binding_checked_before_every_command(args, index, fault):
    guard, mock = bind(args)
    original = mock.binding
    def binding():
        value = original()
        if len(mock.calls) == index:
            value = copy.deepcopy(value)
            if fault in ('devnum', 'path', 'vid', 'pid', 'busnum'):
                value['usb'][fault] = 'wrong'
            elif fault == 'disconnect':
                value['connected'] = False
            elif fault == 'stale':
                value['observed_at'] -= 3
            else:
                value['session_id'] = 'new-handle'
        return value
    mock.binding = binding
    with pytest.raises(ValueError):
        guard.run_reset()
    assert len(mock.calls) == index and mock.closed == 1


@pytest.mark.parametrize('fault', ['fsync', 'disconnect'])
def test_durable_intent_failure_zero_jump(args, monkeypatch, fault):
    guard, mock = bind(args)
    guard.cmd(0x12)
    guard.cmd(0xFB06, address=RAM, payload=guard._block)
    if fault == 'fsync':
        monkeypatch.setattr(core.os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('disk failure')))
    else:
        original = guard.log
        def log(event, **fields):
            original(event, **fields)
            if event == 'jump_intent':
                mock.connected = False
        guard.log = log
    with pytest.raises((OSError, ValueError)):
        guard.cmd(0xFB08, address=RAM)
    assert len(mock.calls) == 2 and mock.closed == 1


def test_durable_private_intent_before_lost_jump_ack(args):
    guard, mock = bind(args)
    original = mock.exchange
    def exchange(cdb, data, size):
        if cdb[:2] == b'\xfb\x08':
            intent = json.loads(args['receipt_path'].read_text().splitlines()[-1])
            assert intent['event'] == 'jump_intent' and intent['retry'] is False
            assert intent['reset_observed'] is False and intent['physical_identity_attested'] is False
            original(cdb, data, size)
            raise OSError('jump may have executed; acknowledgement lost')
        return original(cdb, data, size)
    mock.exchange = exchange
    with pytest.raises(OSError):
        guard.run_reset()
    assert len(mock.calls) == 3 and mock.closed == 1
    assert 'jump_reply' not in args['receipt_path'].read_text()


def test_constructor_requires_factory(args):
    with pytest.raises(ValueError):
        core.CoreResetGuard(bytes(512), args['receipt_path'], time.time())


def test_receipt_reuse_rejected_before_transport(args):
    guard, mock = bind(args)
    guard.close()
    unused = Mock()
    with pytest.raises(FileExistsError):
        core.prepare_core_reset(IMAGE, **args).bind(unused)
    assert not unused.calls


def test_frozen_image_source(args):
    image, source = bytearray(IMAGE), bytearray(SOURCE)
    values = {**args, 'source': source}
    guard = core.prepare_core_reset(image, **values)
    image[:] = bytes(14)
    source[:] = bytes(len(source))
    mock = Mock()
    guard.bind(mock).run_reset()
    assert hashlib.sha256(mock.calls[1][1]).hexdigest() == core.BLOCK_SHA


def test_lowest_builder_consumes_without_syscall(args):
    guard, mock = bind(args)
    guard.build_request(0x12, 0, b'')
    with pytest.raises(ValueError):
        guard.cmd(0x12)
    guard.close()
    assert not mock.calls


def test_bad_inquiry_prevents_upload(args):
    guard, mock = bind(args)
    mock.exchange = lambda cdb, data, size: bytes(size)
    with pytest.raises(ValueError):
        guard.run_reset()
    assert mock.closed == 1


def test_wrong_jump_echo_never_is_reset_witness(args):
    guard, mock = bind(args)
    original = mock.exchange
    def exchange(cdb, data, size):
        result = original(cdb, data, size)
        return bytes(16) if cdb[:2] == b'\xfb\x08' else result
    mock.exchange = exchange
    with pytest.raises(ValueError):
        guard.run_reset()
    assert mock.closed == 1


def test_keyboard_interrupt_closes_after_jump_intent(args):
    guard, mock = bind(args)
    original = mock.exchange
    def exchange(cdb, data, size):
        result = original(cdb, data, size)
        if cdb[:2] == b'\xfb\x08':
            raise KeyboardInterrupt()
        return result
    mock.exchange = exchange
    with pytest.raises(KeyboardInterrupt):
        guard.run_reset()
    assert len(mock.calls) == 3 and mock.closed == 1


@pytest.mark.parametrize('stage,op,address,payload', [
    ('inquiry', 0x12, 1, b''), ('inquiry', 0x12, 0, b'x'),
    ('upload', 0xFB06, RAM, b''), ('jump', 0xFB08, RAM+4, b''),
    ('jump', 0xFB08, RAM, b'x'), ('jump', 0xFB08, 0, b'')])
def test_malformed_arguments_in_each_stage(args, stage, op, address, payload):
    guard, mock = bind(args)
    if stage != 'inquiry':
        guard.cmd(0x12)
    if stage == 'jump':
        guard.cmd(0xFB06, address=RAM, payload=guard._block)
    count = len(mock.calls)
    with pytest.raises(ValueError):
        guard.cmd(op, address=address, payload=payload)
    assert len(mock.calls) == count and mock.closed == 1


@pytest.mark.parametrize('fault', ['disconnected', 'empty_session', 'missing_timestamp'])
def test_bind_rejects_bad_handle_before_exchange(args, fault):
    mock = Mock()
    original = mock.binding
    def binding():
        value = original()
        if fault == 'disconnected':
            value['connected'] = False
        elif fault == 'empty_session':
            value['session_id'] = ''
        else:
            value.pop('observed_at')
        return value
    mock.binding = binding
    with pytest.raises(ValueError):
        core.prepare_core_reset(IMAGE, **args).bind(mock)
    assert not mock.calls and mock.closed == 1
