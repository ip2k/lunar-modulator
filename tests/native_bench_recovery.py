"""MIT. Private real-image recovery campaign, one of 16 container shards.

Run directly with --inputs and --shard; never opens a physical device.
The input directory carries receipt/, stockA.bin, stockB.bin, native.bin.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native.bench_transactions import prepare, V8_SHA, STOCK_SHA, NATIVE_SHA, APP_BASE
from fm1_flash_transaction import (digest, load_transaction, run_transaction,
                                   FLASH_SIZE, SECTOR_BYTES)


class InterruptedWrite(OSError):
    pass


class Nor:
    def __init__(self, flash, identity, fail_at=None, mode=None):
        self.flash = flash
        self.unit = identity
        self.fail_at = fail_at
        self.mode = mode
        self.operations = []
        self.dead = False

    def alive(self):
        if self.dead:
            raise AssertionError('Command reused disconnected session')

    def identity(self):
        self.alive()
        return self.unit

    def online(self):
        self.alive()
        return 3, 0x856014

    def read(self, address, size):
        self.alive()
        assert 0 <= address < address + size <= FLASH_SIZE
        return bytes(self.flash[address:address + size])

    def mutate(self, operation, address, data):
        self.alive()
        self.operations.append((operation, address))
        fault = len(self.operations) == self.fail_at
        count = len(data)
        if fault and self.mode == 'torn':
            count = max(1, count // 3)
        for offset in range(count):
            if operation == 'erase':
                self.flash[address + offset] = 255
            else:
                assert self.flash[address + offset] & data[offset] == data[offset]
                self.flash[address + offset] &= data[offset]
        if fault:
            self.dead = True
            raise InterruptedWrite('Torn mutation' if self.mode == 'torn'
                                   else 'Mutation completed; acknowledgement lost')

    def erase(self, address):
        assert address % SECTOR_BYTES == 0
        self.mutate('erase', address, b'\xff' * SECTOR_BYTES)

    def program(self, address, data):
        assert address % 256 == 0 and len(data) == 256
        self.mutate('program', address, data)


def directory_last(session):
    addresses = [address // SECTOR_BYTES * SECTOR_BYTES
                 for _, address in session.operations]
    if APP_BASE in addresses:
        assert all(address == APP_BASE for address in addresses[addresses.index(APP_BASE):])


def campaign(inputs, shard):
    if type(shard) is not int or not 0 <= shard < 16:
        raise ValueError('Shard must be 0..15')
    inputs = Path(inputs)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        report = prepare(root / 'plans', inputs / 'receipt', inputs / 'stockA.bin',
                         inputs / 'stockB.bin', inputs / 'native.bin', simulated=True)
        native = root / 'plans/native'
        stock = root / 'plans/stock'
        plan, _, baseline, target = load_transaction(native)
        # Count actual mutations, including erases and nonblank pages, to place
        # all 16 interruptions throughout this concrete candidate's write order.
        count = sum((baseline[a:a + SECTOR_BYTES] != b'\xff' * SECTOR_BYTES) +
                    sum(target[p:p + 256] != b'\xff' * 256
                        for p in range(a, a + SECTOR_BYTES, 256))
                    for a in plan['sector_order'])
        fail_at = 1 + (count - 1) * shard // 15
        flash = bytearray(baseline)
        failed = Nor(flash, plan['identity'], fail_at,
                     'torn' if shard % 2 == 0 else 'lost-ack')
        try:
            run_transaction(native, failed)
        except InterruptedWrite:
            pass
        else:
            raise AssertionError('Fault not reached')
        assert len(failed.operations) == fail_at and failed.dead
        assert load_transaction(native)[1]['state'] == 'recovery_required'
        directory_last(failed)
        # A prepared stock transaction must refuse torn/native bytes. It must
        # not adopt unrelated flash changes as its own interrupted operation.
        refused = Nor(flash, plan['identity'])
        try:
            run_transaction(stock, refused)
        except ValueError:
            pass
        else:
            raise AssertionError('Stock preflight adopted nonbaseline flash')
        assert not refused.operations
        assert load_transaction(stock)[1]['state'] == 'prepared'
        fresh = Nor(flash, plan['identity'])
        rollback = run_transaction(native, fresh, direction='restore')
        assert digest(bytes(flash)) == V8_SHA == rollback['verified_sha256']
        directory_last(fresh)
        if shard == 0:
            successful = Nor(flash, plan['identity'])
            installed = run_transaction(native, successful)
            assert digest(bytes(flash)) == NATIVE_SHA == installed['verified_sha256']
            directory_last(successful)
            returned = Nor(flash, plan['identity'])
            run_transaction(native, returned, direction='restore')
            assert digest(bytes(flash)) == V8_SHA
            directory_last(returned)
        rescue = Nor(flash, plan['identity'])
        restored = run_transaction(stock, rescue)
        assert digest(bytes(flash)) == STOCK_SHA == restored['verified_sha256']
        directory_last(rescue)
        # A forged complete journal cannot bypass protected-byte fresh readback.
        flash[0] ^= 1
        refused = Nor(flash, plan['identity'])
        try:
            run_transaction(stock, refused)
        except ValueError:
            pass
        else:
            raise AssertionError('Protected corruption ignored')
        assert not refused.operations
        return dict(shard=shard, simulated=True, hardware_operations=0,
                    fault=failed.mode, failed_operation=failed.operations[-1],
                    mutation_index=fail_at, mutation_count=count,
                    v8_rollback_sha256=rollback['verified_sha256'],
                    stock_restore_sha256=restored['verified_sha256'],
                    native_sectors=report['native_sectors'], directory_last=True,
                    complete_native_round_trip=shard == 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--shard', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(campaign(args.inputs, args.shard), sort_keys=True))
