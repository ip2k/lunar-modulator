"""Offline guard checks. Synthetic loader hash override exists only in tests."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_loader_reset as reset
from fm1_softkey_probe import KNOWN_092, SOFT_KEY
from fm1_uboot_read import Reader, request, RAM


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    loader = bytes(range(256)) * 94
    monkeypatch.setattr(reset, 'LOADER_SHA', hashlib.sha256(loader).hexdigest())
    # Reader.load checks its own module pin too; no production override exists.
    monkeypatch.setattr(sys.modules['fm1_uboot_read'], 'LOADER_SHA', reset.LOADER_SHA)
    usb = dict(reset.OWNER_USB)
    events = [
        {'event': 'artifact', 'time': 10},
        {'event': 'passive_capture_started', 'time': 10},
        {'event': 'before', 'time': 10, 'usb_path': '3-2',
         'usb': [{**usb, 'devnum': '19', 'pid': 'c755'}]},
        {'event': 'sending_identity', 'time': 10},
        {'event': 'identity', 'time': 10, 'reply': KNOWN_092.hex()},
        {'event': 'sending_soft_key', 'time': 10, 'hex': SOFT_KEY.hex()},
        {'event': 'uboot_enumerated', 'time': 11,
         'usb': [{**usb, 'devnum': '20'}]},
        {'event': 'experiment_finished', 'time': 20, 'retry': False, 'usb': [usb]},
    ]
    entry = '\n'.join(json.dumps(e) for e in events).encode()
    monkeypatch.setattr(reset, 'ENTRY_SHA', hashlib.sha256(entry).hexdigest())
    args = dict(entry_log=entry, observation=usb, observed_at=time.time(),
                receipt_path=tmp_path/'receipt.jsonl')
    return loader, args


class Mock:
    def __init__(self):
        self.session = 'handle1'
        self.usb = dict(reset.OWNER_USB)
        self.connected = True
        self.calls = []
        self.closed = 0
        self.failure = self.bad = self.change = None
        self.receipt = None

    def binding(self):
        return {'simulated': True, 'connected': self.connected, 'session_id': self.session,
                'usb': self.usb, 'observed_at': time.time()}

    def exchange(self, cdb, data, size):
        op = int.from_bytes(cdb[:2], 'big') if len(cdb) == 16 else 0x12
        if op == 0xFC0C:
            # Durable reset intent exists before even an uncertain submission.
            assert json.loads(self.receipt.read_text().splitlines()[-1])['event'] == 'reset_intent'
            assert cdb == reset.RESET_CDB and data == b'' and size == 16
        self.calls.append((cdb, data, size))
        if op == self.failure:
            raise OSError('lost reply after possible operation')
        result = bytearray(size)
        if size == 16:
            result[:2] = op.to_bytes(2, 'big')
        if op == 0x12:
            result[8:16], result[16:32] = b'WL82    ', b'UBOOT1.00       '
        elif op == 0xFC14:
            result[2:6] = (256).to_bytes(4, 'big')
        elif op == 0xFC0A:
            result[2] = 3
            result[4:8] = (0x856014).to_bytes(4, 'little')
        if op == self.change:
            self.session = 'replacement'
        if op == self.bad:
            return bytes(size-1) if size else b'x'
        return bytes(result)

    def close(self):
        self.closed += 1


def bind(prepared):
    loader, args = prepared
    mock = Mock()
    mock.receipt = args['receipt_path']
    guard = reset.prepare_reset(loader, **args).bind(mock)
    return guard, mock


def test_exact_sequence(prepared):
    guard, mock = bind(prepared)
    assert guard.run_reset() == {'attempted': True, 'retry': False, 'reset_observed': False,
                                 'hardware_ready': False, 'initializer_boundary_resolved': False, 'simulated': True}
    assert len(mock.calls) == 52
    assert mock.calls[0] == request(0x12, 'rom')
    loader = prepared[0]
    for i in range(47):
        assert mock.calls[i+1] == request(0xFB06, 'rom', address=RAM+512*i,
                                         payload=loader[512*i:512*(i+1)])
    assert [c[0][:2].hex() for c in mock.calls[-4:]] == ['fb08', 'fc14', 'fc0a', 'fc0c']
    assert mock.closed == 1
    assert prepared[1]['receipt_path'].stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        guard.run_reset()


@pytest.mark.parametrize('fault', ['loader', 'entry', 'observation', 'stale', 'future', 'nan'])
def test_prepare_refuses_before_transport(prepared, fault):
    loader, args = prepared
    args = copy.deepcopy(args)
    if fault == 'loader':
        loader = bytes(len(loader))
    elif fault == 'entry':
        args['entry_log'] += b'\n'
    elif fault == 'observation':
        args['observation']['devnum'] = '22'
    elif fault == 'stale':
        args['observed_at'] -= 11
    elif fault == 'future':
        args['observed_at'] += 100
    elif fault == 'nan':
        args['observed_at'] = float('nan')
    with pytest.raises(ValueError):
        reset.prepare_reset(loader, **args)
    assert not args['receipt_path'].exists()


def test_constructor_cannot_skip_evidence(prepared):
    with pytest.raises(ValueError):
        reset.LoaderResetGuard(prepared[0], prepared[1]['receipt_path'], time.time())


@pytest.mark.parametrize('op', [0xFB00, 0xFB01, 0xFB02, 0xFB04, 0xFD05, 0xFD07,
                               0xFC09, 0xFC12, 0xFC16, 0xA1, 0xFC0C, 0xFB08, 0xFC14, 0xFC0A])
def test_forbidden_early_operations(prepared, op):
    guard, mock = bind(prepared)
    with pytest.raises(ValueError):
        guard.cmd(op)
    assert not mock.calls and mock.closed == 1
    with pytest.raises(ValueError):
        guard.cmd(0x12)


@pytest.mark.parametrize('variant', ['wrong_block', 'wrong_address', 'short_block', 'extra_inquiry'])
def test_upload_only_exact_next_block(prepared, variant):
    guard, mock = bind(prepared)
    guard.cmd(0x12)
    data, address, op = prepared[0][:512], RAM, 0xFB06
    if variant == 'wrong_block':
        data = bytes(512)
    elif variant == 'wrong_address':
        address += 512
    elif variant == 'short_block':
        data = data[:-1]
    else:
        op, data, address = 0x12, b'', 0
    with pytest.raises(ValueError):
        guard.cmd(op, address=address, payload=data)
    assert len(mock.calls) == 1 and mock.closed == 1


@pytest.mark.parametrize('op', [0x12, 0xFB06, 0xFB08, 0xFC14, 0xFC0A, 0xFC0C])
@pytest.mark.parametrize('mode', ['lost', 'short', 'replacement'])
def test_ambiguity_latches(prepared, op, mode):
    guard, mock = bind(prepared)
    setattr(mock, {'lost': 'failure', 'short': 'bad', 'replacement': 'change'}[mode], op)
    if mode == 'replacement' and op == 0xFC0C:
        # After reset the connection may disappear/re-enumerate; still close.
        guard.run_reset()
    else:
        with pytest.raises((ValueError, OSError)):
            guard.run_reset()
    count = len(mock.calls)
    assert mock.closed == 1
    with pytest.raises(ValueError):
        guard.cmd(op)
    assert len(mock.calls) == count


@pytest.mark.parametrize('field,value', [('devnum', '22'), ('path', '3-3'),
                                        ('vid', '0000'), ('pid', 'c755'), ('busnum', '4')])
def test_precommand_replacement_no_submission(prepared, field, value):
    guard, mock = bind(prepared)
    mock.usb[field] = value
    with pytest.raises(ValueError):
        guard.cmd(0x12)
    assert not mock.calls and mock.closed == 1


def test_receipt_cannot_reopen(prepared):
    guard, mock = bind(prepared)
    guard.close()
    other = reset.prepare_reset(prepared[0], **prepared[1])
    unused = Mock()
    with pytest.raises(FileExistsError):
        other.bind(unused)
    assert not unused.calls


def test_freezes_mutable_loader(prepared):
    loader, args = prepared
    mutable = bytearray(loader)
    guard = reset.prepare_reset(mutable, **args)
    mutable[:] = bytes(len(loader))
    mock = Mock()
    mock.receipt = args['receipt_path']
    guard.bind(mock).run_reset()
    assert mock.calls[1][1] == loader[:512]


def test_direct_builder_consumes_without_replay(prepared):
    guard, mock = bind(prepared)
    guard.build_request(0x12, 0, b'')
    with pytest.raises(ValueError):
        guard.cmd(0x12)
    guard.close()
    assert not mock.calls


def test_fsync_failure_prevents_reset_submission(prepared, monkeypatch):
    guard, mock = bind(prepared)
    Reader.load(guard, prepared[0])
    monkeypatch.setattr(reset.os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError):
        guard.cmd(0xFC0C)
    assert len(mock.calls) == 51 and mock.closed == 1


@pytest.mark.parametrize('op', [0x12, 0xFB06, 0xFB08, 0xFC14, 0xFC0A, 0xFC0C])
def test_binding_checked_before_every_operation(prepared, op):
    guard, mock = bind(prepared)
    original = mock.binding
    def binding():
        upcoming = {0: 0x12, 1: 0xFB06, 48: 0xFB08, 49: 0xFC14,
                    50: 0xFC0A, 51: 0xFC0C}.get(len(mock.calls))
        value = original()
        if upcoming == op:
            value['connected'] = False
        return value
    mock.binding = binding
    with pytest.raises(ValueError):
        guard.run_reset()
    assert all(int.from_bytes(c[0][:2], 'big') != op for c in mock.calls)
    assert mock.closed == 1


@pytest.mark.parametrize('kind', ['chip', 'buffer_low', 'buffer_high', 'flash_type', 'jedec', 'echo'])
def test_bad_readiness_never_resets(prepared, kind):
    guard, mock = bind(prepared)
    original = mock.exchange
    def exchange(cdb, data, size):
        result = bytearray(original(cdb, data, size))
        op = int.from_bytes(cdb[:2], 'big') if len(cdb) == 16 else 0x12
        if kind == 'chip' and op == 0x12:
            result[8:16] = b'OTHER   '
        elif kind.startswith('buffer') and op == 0xFC14:
            result[2:6] = (255 if kind == 'buffer_low' else 65536).to_bytes(4, 'big')
        elif kind == 'flash_type' and op == 0xFC0A:
            result[2] = 4
        elif kind == 'jedec' and op == 0xFC0A:
            result[4:8] = bytes(4)
        elif kind == 'echo' and op == 0xFC14:
            result[:2] = b'\xfc\x0a'
        return bytes(result)
    mock.exchange = exchange
    with pytest.raises(ValueError):
        guard.run_reset()
    assert all(c[0] != reset.RESET_CDB for c in mock.calls)


@pytest.mark.parametrize('address,payload', [(1, b''), (0, b'\x01'), (0, b'_0')])
def test_reset_arguments_fixed(prepared, address, payload):
    guard, mock = bind(prepared)
    Reader.load(guard, prepared[0])
    with pytest.raises(ValueError):
        guard.cmd(0xFC0C, address=address, payload=payload)
    assert len(mock.calls) == 51 and mock.closed == 1


def test_original_reader_still_rejects_reset():
    with pytest.raises(ValueError):
        request(0xFC0C, 'loader')


def test_durable_intent_before_reset_even_keyboard_interrupt(prepared):
    guard, mock = bind(prepared)
    original = mock.exchange
    def exchange(cdb, data, size):
        if cdb == reset.RESET_CDB:
            original(cdb, data, size)
            raise KeyboardInterrupt()
        return original(cdb, data, size)
    mock.exchange = exchange
    with pytest.raises(KeyboardInterrupt):
        guard.run_reset()
    assert mock.closed == 1 and len(mock.calls) == 52
    with pytest.raises(ValueError):
        guard.cmd(0xFC0C)


@pytest.mark.parametrize('stage,phase,allowed', [('inquiry', 'rom', 0x12),
    ('upload', 'rom', 0xFB06), ('jump', 'rom', 0xFB08), ('buffer', 'loader', 0xFC14),
    ('online', 'loader', 0xFC0A), ('ready', 'loader', 0xFC0C)])
def test_lowest_builder_exhaustive_allowlist(prepared, stage, phase, allowed):
    guard, mock = bind(prepared)
    guard._stage, guard.phase = stage, phase
    for op in range(65536):
        if op != allowed:
            with pytest.raises(ValueError):
                guard.build_request(op, 0, b'')
    assert not mock.calls
    guard.close()


def test_stale_bind_observation_no_commands(prepared):
    guard = reset.prepare_reset(prepared[0], **prepared[1])
    guard._observed_at -= 11
    mock = Mock()
    with pytest.raises(ValueError):
        guard.bind(mock)
    assert not mock.calls and not prepared[1]['receipt_path'].exists()


def test_stale_percommand_observation_no_commands(prepared):
    guard, mock = bind(prepared)
    original = mock.binding
    def binding():
        value = original()
        value['observed_at'] -= 3
        return value
    mock.binding = binding
    with pytest.raises(ValueError):
        guard.run_reset()
    assert not mock.calls and mock.closed == 1


@pytest.mark.parametrize('simulated', [False, None, 1, 'true'])
def test_non_simulated_binding_rejected_before_exchange(prepared, simulated):
    guard = reset.prepare_reset(prepared[0], **prepared[1])
    mock = Mock()
    original = mock.binding
    def binding():
        value = original()
        value['simulated'] = simulated
        return value
    mock.binding = binding
    with pytest.raises(ValueError, match='Offline simulation only'):
        guard.bind(mock)
    assert not mock.calls and mock.closed == 1
    assert 'reset_intent' not in prepared[1]['receipt_path'].read_text()


def test_losing_simulation_assertion_latches_before_next_command(prepared):
    guard, mock = bind(prepared)
    original = mock.binding
    def binding():
        value = original()
        value.pop('simulated')
        return value
    mock.binding = binding
    with pytest.raises(ValueError, match='Offline simulation only'):
        guard.run_reset()
    assert not mock.calls and mock.closed == 1


def test_disconnect_during_durable_intent_prevents_submission(prepared):
    guard, mock = bind(prepared)
    Reader.load(guard, prepared[0])
    original = guard.log
    def log(event, **fields):
        original(event, **fields)
        if event == 'reset_intent':
            mock.connected = False
    guard.log = log
    with pytest.raises(ValueError):
        guard.cmd(0xFC0C)
    assert len(mock.calls) == 51 and mock.closed == 1
    events = [json.loads(line) for line in prepared[1]['receipt_path'].read_text().splitlines()]
    assert all(e['simulated'] is True and e['hardware_ready'] is False for e in events)
