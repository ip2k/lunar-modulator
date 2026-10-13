"""MIT. One of 16 private native-policy mock wire checks, no device opener."""
import argparse
import binascii
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native.controls_transactions import prepare, NATIVE_SHA, V8_SHA
from native.controls_policy import load_policy, LOADER_SHA
from fm1_flash_transaction import load_transaction, digest
from native_bench_recovery import Nor


class Wire:
    def __init__(self, policy, flash):
        self.claim = dict(json.loads(policy.binding_bytes), phase='loader',
                          loader_sha256=LOADER_SHA, session_id='simulation-only',
                          identity=json.loads(policy.plan_bytes)['identity'])
        self.nor = Nor(flash, self.claim['identity'])
        self.closed = False
        self.calls = 0

    def binding(self):
        assert not self.closed
        return copy.deepcopy(self.claim)

    def close(self):
        self.closed = True

    def exchange(self, cdb, payload, size):
        assert not self.closed and len(cdb) == 16
        self.calls += 1
        op = int.from_bytes(cdb[:2], 'big')
        address = int.from_bytes(cdb[2:6], 'big')
        if op == 0xFD05:
            assert size == 256 and not payload
            return self.nor.read(address, size)
        if op == 0xFB04:
            assert size == 0 and len(payload) == 256
            assert int.from_bytes(cdb[9:11], 'little') == binascii.crc_hqx(payload, 0)
            self.nor.program(address, payload)
            return b''
        response = bytearray(16)
        response[:2] = cdb[:2]
        if op == 0xFC0A:
            response[2] = 3
            response[4:8] = (0x856014).to_bytes(4, 'little')
        elif op == 0xFB01:
            self.nor.erase(address)
        else:
            raise AssertionError('Unexpected command reached wire')
        return bytes(response)


def refuses(call):
    try:
        call()
    except (ValueError, OSError):
        return
    raise AssertionError('Expected refusal')


def campaign(inputs, shard):
    if not 0 <= shard < 16:
        raise ValueError('Shard must be 0..15')
    inputs = Path(inputs)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        prepare(root / 'plans', inputs / 'receipt', inputs / 'stockA.bin',
                inputs / 'stockB.bin', inputs / 'native.bin')
        arguments = dict(directory=root / 'plans/native', direction='install',
                         receipt=inputs / 'receipt')
        policy = load_policy(**arguments)
        _, _, baseline, _ = load_transaction(policy.directory)
        wire = Wire(policy, bytearray(baseline))
        binding_keys = ['phase', 'loader_sha256', 'session_id', 'identity',
                        'usb_binding', 'backup_manifest_sha256',
                        'backup_commands_sha256', 'backup_campaign_sha256']
        if shard < 8:
            key = binding_keys[shard]
            wire.claim[key] = '' if key == 'session_id' else 'wrong'
            refuses(lambda: policy.bind(wire))
            assert wire.closed and wire.calls == 0
            fault = 'binding:' + key
        else:
            session = policy.bind(wire)
            if shard == 8:
                refuses(lambda: replace(policy).bind(wire))
                fault = 'copied policy'
            elif shard == 9:
                wire.claim['session_id'] = 'changed'
                refuses(session.online)
                assert wire.closed and wire.calls == 0
                fault = 'changed session'
            elif shard == 10:
                refuses(lambda: session.erase(0x5000))
                assert wire.calls == 0
                fault = 'missing durable mutation intent'
            elif shard == 11:
                session._running = True  # Even a trusted caller cannot skip journal intent.
                refuses(lambda: session.program(0x5000, policy.target[0x5000:0x5100]))
                assert wire.calls == 0
                fault = 'running flag without journal intent'
            elif shard == 12:
                refuses(lambda: session.program(0x5000, b'\x00' * 256))
                assert wire.calls == 0
                fault = 'wrong image page'
            elif shard == 13:
                refuses(lambda: session.erase(0))
                assert wire.calls == 0
                fault = 'protected erase'
            elif shard == 14:
                path = policy.directory / 'target.bin'
                data = path.read_bytes()
                path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
                refuses(lambda: policy.bind(wire))
                assert wire.calls == 0
                fault = 'changed target artifact'
            else:
                refuses(lambda: session.cmd(0xFC12))
                refuses(lambda: session.cmd(0xFB08))
                refuses(lambda: session.cmd(0xFC0C))
                assert wire.calls == 0
                fault = 'efuse/upload/reset forbidden'
            session.close()
        if shard == 0:
            policy = load_policy(**arguments)
            wire = Wire(policy, bytearray(baseline))
            result = policy.bind(wire).run()
            assert digest(bytes(wire.nor.flash)) == NATIVE_SHA
            assert result['protocol_mock_only'] and not result['hardware_validated']
            restored = load_policy(**dict(arguments, direction='restore'))
            wire = Wire(restored, wire.nor.flash)
            result = restored.bind(wire).run()
            assert digest(bytes(wire.nor.flash)) == V8_SHA
            assert result['protocol_mock_only'] and not result['hardware_validated']
        return dict(shard=shard, fault=fault, passed=True, hardware_operations=0,
                    simulated=True, native_round_trip=shard == 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--shard', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(campaign(args.inputs, args.shard), sort_keys=True))
