"""Persistent, transport-free FM-1 recovery failure model (MIT).

[verified: unit tests] This models the CDB layouts used by fm1_uboot_read and
fm1_uboot_restore_test, a 1 MiB NOR array, volatile loader RAM, and USB handle
generations. It never opens USB, SG_IO, MIDI, a serial port, or a device node.
Generic write CDBs here are simulation-only; the physical scratch-sector tool
retains its separate fixed range and fixed payload policy.

[inferred: model] A torn operation changes a deterministic byte prefix, not an
electrical timing model. Boot health is an explicit digest oracle for a supplied
application range, not pi32v2 execution, stock verifier emulation, or proof that
USB_KEY can recover a physical FM-1. Re-enumeration, loader responses and the
stable unit identity are modeled. Callers supply exact permitted/protected
ranges; the default permits no writes. Test loader hashes must be injected with
the conspicuous simulator_loader_sha256 argument; physical audit pins stay intact.

Persistence consists of flash.bin (fsynced after each mutation) and atomic
state.json metadata in a caller-owned directory. One device object owns a
directory at a time; concurrent processes and host filesystem power failure are
outside this model. Simulated reset/power loss preserves all committed NOR bytes.
"""

from __future__ import annotations

import binascii
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

try:
    from .fm1_uboot_read import CHUNK, FLASH_SIZE, LOADER_SHA, LOADER_SIZE, RAM, request
except ImportError:  # Direct scripts with tools/ on sys.path.
    from fm1_uboot_read import CHUNK, FLASH_SIZE, LOADER_SHA, LOADER_SIZE, RAM, request

SECTOR_BYTES = 4096
JEDEC = 0x856014
SOFT_KEY = bytes.fromhex('f0 22 24 35 7d f7')


class SimulatedDisconnect(OSError):
    """A stale/disconnected modeled handle; reconnect and inspect before retry."""


class SimulatedPowerLoss(SimulatedDisconnect):
    """A partial operation persisted and volatile loader state was lost."""


class SimulatedAckLoss(SimulatedDisconnect):
    """The operation committed, but the host did not receive its acknowledgement."""


@dataclass
class Failure:
    operation: str
    kind: str
    occurrence: int = 1
    after_bytes: int = 0


def _ranges(ranges):
    result = tuple((int(start), int(end)) for start, end in ranges)
    for start, end in result:
        if not 0 <= start < end <= FLASH_SIZE:
            raise ValueError('Ranges must be nonempty and within the 1 MiB flash')
    return result


def simulated_request(op, phase, *, address=0, payload=b''):
    """Mirror reviewed sector/page CDB layouts solely for the in-memory model."""
    if op == 0xFB01:
        if phase != 'loader' or payload or address % SECTOR_BYTES or not 0 <= address <= FLASH_SIZE-SECTOR_BYTES:
            raise ValueError('Simulated erase requires one aligned, bounded 4 KiB sector')
        return (op.to_bytes(2, 'big')+address.to_bytes(4, 'big')).ljust(16, b'\xff'), b'', 16
    if op == 0xFB04:
        if phase != 'loader' or len(payload) != CHUNK or address % CHUNK or not 0 <= address <= FLASH_SIZE-CHUNK:
            raise ValueError('Simulated program requires one aligned, bounded 256-byte page')
        cdb = (op.to_bytes(2, 'big')+address.to_bytes(4, 'big')+CHUNK.to_bytes(2, 'big')
               + b'\x00'+binascii.crc_hqx(payload, 0).to_bytes(2, 'little')).ljust(16, b'\xff')
        return cdb, payload, 0
    return request(op, phase, address=address, payload=payload)


class SimulatedDevice:
    """Own a persistent NOR image and open generation-scoped simulated sessions.

    New devices require exactly FLASH_SIZE initial bytes. Existing directories
    reopen with ``SimulatedDevice(path=path)``; their identity, permissions and
    boot oracle are restored without silently replacing the damaged flash.
    """

    def __init__(self, flash=None, *, path=None, unit_id='sim-fm1-001',
                 writable_ranges=(), protected_ranges=(), app_range=(0, FLASH_SIZE),
                 simulator_loader_sha256=None):
        self.path = Path(path) if path is not None else None
        self.failures = []
        self.events = []
        self._ram = bytearray(LOADER_SIZE)
        self._uploaded = set()
        if self.path is not None and (self.path/'state.json').exists():
            if flash is not None:
                raise ValueError('Reopen persistent state without an initial flash image')
            state = json.loads((self.path/'state.json').read_text())
            if state.get('schema') != 1 or state.get('simulated') is not True:
                raise ValueError('Not a supported simulated device directory')
            self._flash = bytearray((self.path/'flash.bin').read_bytes())
            self.unit_id = state['unit_id']
            self.writable_ranges = _ranges(state['writable_ranges'])
            self.protected_ranges = _ranges(state['protected_ranges'])
            self.app_range = _ranges([state['app_range']])[0]
            self.loader_sha256 = state['loader_sha256']
            self.expected_app_hashes = set(state['expected_app_hashes'])
            self.generation = int(state['generation'])+1
            # RAM cannot survive closing/reopening the modeled process/device.
            self.mode = 'app' if self._app_healthy() else 'app_unavailable'
            self.connected = True
        else:
            if flash is None or len(flash) != FLASH_SIZE:
                raise ValueError('New simulated devices require exactly 1 MiB initial flash')
            if not isinstance(unit_id, str) or not unit_id:
                raise ValueError('A stable nonempty simulated unit identity is required')
            self._flash = bytearray(flash)
            self.unit_id = unit_id
            self.writable_ranges = _ranges(writable_ranges)
            self.protected_ranges = _ranges(protected_ranges)
            self.app_range = _ranges([app_range])[0]
            self.loader_sha256 = simulator_loader_sha256 or LOADER_SHA
            self.expected_app_hashes = {self._app_hash(self._flash)}
            self.generation = 0
            self.mode, self.connected = 'app', True
            if self.path is not None:
                self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
                with (self.path/'flash.bin').open('xb') as fp:
                    os.chmod(fp.name, 0o600)
                    fp.write(self._flash)
                    fp.flush()
                    os.fsync(fp.fileno())
        if len(self._flash) != FLASH_SIZE:
            raise ValueError('Persistent NOR image is not exactly 1 MiB')
        if len(self.loader_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.loader_sha256):
            raise ValueError('Simulator loader pin must be a lowercase SHA-256')
        self._save_state()

    @property
    def flash(self):
        """Immutable inspection copy; mutations must pass the simulated protocol."""
        return bytes(self._flash)

    def _app_hash(self, image):
        start, end = self.app_range
        return hashlib.sha256(image[start:end]).hexdigest()

    def _app_healthy(self):
        return self._app_hash(self._flash) in self.expected_app_hashes

    def register_bootable_image(self, image):
        """Extend the synthetic boot oracle, without claiming hardware validity."""
        if len(image) != FLASH_SIZE:
            raise ValueError('Boot oracle registration requires a full 1 MiB image')
        self.expected_app_hashes.add(self._app_hash(image))
        self._save_state()

    def _save_state(self):
        if self.path is None:
            return
        state = {'schema': 1, 'simulated': True, 'unit_id': self.unit_id,
                 'writable_ranges': self.writable_ranges, 'protected_ranges': self.protected_ranges,
                 'app_range': self.app_range, 'loader_sha256': self.loader_sha256,
                 'expected_app_hashes': sorted(self.expected_app_hashes),
                 'generation': self.generation, 'mode': self.mode, 'connected': self.connected}
        temporary = self.path/'state.json.tmp'
        with temporary.open('w') as fp:
            os.chmod(temporary, 0o600)
            json.dump(state, fp, sort_keys=True)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temporary, self.path/'state.json')

    def _persist_flash(self, address, data):
        self._flash[address:address+len(data)] = data
        if self.path is not None:
            with (self.path/'flash.bin').open('r+b') as fp:
                fp.seek(address)
                fp.write(data)
                fp.flush()
                os.fsync(fp.fileno())

    def _reenumerate(self, mode, *, connected=True, retain_ram=False):
        self.generation += 1
        self.mode, self.connected = mode, connected
        if not retain_ram:
            self._ram[:] = bytes(LOADER_SIZE)
            self._uploaded.clear()
        self.events.append({'event': 'enumeration', 'generation': self.generation,
                            'mode': mode, 'connected': connected, 'simulated': True})
        self._save_state()

    def soft_key(self, message=SOFT_KEY):
        if message != SOFT_KEY or self.mode != 'app' or not self.connected:
            raise ValueError('Modeled soft key needs a healthy, connected application')
        self.events.append({'event': 'soft_key', 'simulated': True})
        self._reenumerate('rom')

    def usb_key(self):
        """Model external ROM entry even if the application cannot boot.

        This asserts an oracle route in the simulator, not physical verification
        of the RP2040 dongle, its timing, the FM-1 pins or full-image recovery.
        """
        self.events.append({'event': 'external_usb_key', 'simulated': True})
        self._reenumerate('rom')

    def reset(self):
        self._reenumerate('app' if self._app_healthy() else 'app_unavailable')

    def power_loss(self):
        self._reenumerate('off', connected=False)

    def reconnect(self):
        if self.mode == 'off':
            self.reset()
        else:
            self._reenumerate(self.mode, retain_ram=True)

    def open_session(self, log=None):
        if not self.connected or self.mode == 'off':
            raise SimulatedDisconnect('Modeled device is disconnected')
        return SimulatedSession(self, log)

    def recovery_session(self, loader, log=None):
        """Obtain fresh recovery state, explicitly modeling external ROM entry."""
        if not self.connected:
            self.reconnect()
        if self.mode != 'loader':
            if self.mode == 'app':
                self.soft_key()
            elif self.mode != 'rom':
                self.usb_key()
            session = self.open_session(log)
            session.load(loader)
            return session
        session = self.open_session(log)
        session.online()
        return session

    def inject_failure(self, operation, kind, *, occurrence=1, after_bytes=0):
        """Consume a deterministic one-shot failure at a matching operation.

        occurrence counts matching protocol commands after injection, so read
        occurrences are 256-byte FD05 chunks, not aggregate read() calls.
        """
        operations = {'inquiry', 'upload', 'jump', 'buffer', 'online', 'read', 'erase', 'program'}
        if operation not in operations or kind not in {'torn', 'ack_loss', 'disconnect_before', 'corrupt_read'}:
            raise ValueError('Unknown simulated fault operation/kind')
        if not isinstance(occurrence, int) or occurrence < 1 or not isinstance(after_bytes, int) or after_bytes < 0:
            raise ValueError('Fault occurrence must be positive and prefix nonnegative')
        if kind == 'torn' and (operation not in {'erase', 'program'} or after_bytes > (SECTOR_BYTES if operation == 'erase' else CHUNK)):
            raise ValueError('Torn failures need a bounded prefix of a NOR mutation')
        if kind == 'corrupt_read' and operation != 'read':
            raise ValueError('Read corruption only applies to FD05')
        self.failures.append(Failure(operation, kind, occurrence, after_bytes))

    def _failure(self, operation):
        for failure in self.failures:
            if failure.operation == operation:
                failure.occurrence -= 1
                if failure.occurrence == 0:
                    self.failures.remove(failure)
                    return failure
        return None

    def _writable(self, address, size):
        end = address+size
        if (not any(start <= address and end <= stop for start, stop in self.writable_ranges)
                or any(address < stop and start < end for start, stop in self.protected_ranges)):
            raise ValueError('Simulated mutation intersects a protected or unallowed range')


class SimulatedSession:
    """Reader-shaped API bound to one modeled USB enumeration generation."""

    def __init__(self, device, log=None):
        self.device = device
        self.generation = device.generation
        self.closed = False
        self.log = log or (lambda event, **fields: None)

    @property
    def phase(self):
        return self.device.mode

    def _check(self):
        if self.closed or not self.device.connected or self.generation != self.device.generation:
            raise SimulatedDisconnect('Closed, disconnected or stale modeled USB handle')

    def close(self):
        self.closed = True

    def identity(self):
        self._check()
        return {'unit_id': self.device.unit_id, 'flash_size': FLASH_SIZE,
                'sector_size': SECTOR_BYTES, 'page_size': CHUNK,
                'jedec': JEDEC, 'simulated': True}

    def build_request(self, op, address, payload):
        return simulated_request(op, self.phase, address=address, payload=payload)

    def cmd(self, op, *, address=0, payload=b''):
        self._check()
        cdb, data, size = self.build_request(op, address, payload)
        return self.execute(cdb, data, size)

    def execute(self, cdb, data_out=b'', in_size=0):
        """Decode and strictly validate wire layout, including CRC and FF padding."""
        self._check()
        if not cdb:
            raise ValueError('Empty simulated CDB')
        op = 0x12 if cdb == bytes.fromhex('12 00 00 00 24 00') else int.from_bytes(cdb[:2], 'big')
        address = int.from_bytes(cdb[2:6], 'big') if op in {0xFB06, 0xFB08, 0xFD05, 0xFB01, 0xFB04} else 0
        expected = self.build_request(op, address, data_out)
        if (cdb, data_out, in_size) != expected:
            raise ValueError('Malformed simulated CDB, length, CRC or padding')
        operation = {0x12: 'inquiry', 0xFB06: 'upload', 0xFB08: 'jump',
                     0xFC14: 'buffer', 0xFC0A: 'online', 0xFD05: 'read',
                     0xFB01: 'erase', 0xFB04: 'program'}[op]
        if operation in {'erase', 'program'}:
            self.device._writable(address, SECTOR_BYTES if operation == 'erase' else CHUNK)
        if operation == 'jump' and (len(self.device._uploaded) != LOADER_SIZE//512
                                   or hashlib.sha256(self.device._ram).hexdigest() != self.device.loader_sha256):
            raise ValueError('Jump requires every loader block and the approved simulator hash')
        failure = self.device._failure(operation)
        self.log('command', phase=self.phase, cdb=cdb.hex(), out_len=len(data_out), in_len=in_size, simulated=True)
        self.device.events.append({'event': 'command', 'operation': operation, 'address': address,
                                   'generation': self.generation, 'simulated': True})
        if failure:
            self.device.events.append({'event': 'fault', 'operation': operation,
                                       'kind': failure.kind, 'address': address,
                                       'after_bytes': failure.after_bytes, 'simulated': True})
        if failure and failure.kind == 'disconnect_before':
            self.device._reenumerate(self.phase, connected=False, retain_ram=True)
            raise SimulatedDisconnect('Injected disconnect before modeled operation')
        result = op.to_bytes(2, 'big')+bytes(14) if in_size == 16 else b''
        if operation == 'inquiry':
            result = bytes(8)+b'WL82    '+b'UBOOT1.00       '+b'1.00'
        elif operation == 'upload':
            offset = address-RAM
            self.device._ram[offset:offset+512] = data_out
            self.device._uploaded.add(offset)
        elif operation == 'jump':
            # The audited Reader continues on the same handle after loader jump.
            self.device.mode = 'loader'
            self.device._save_state()
        elif operation == 'buffer':
            result = op.to_bytes(2, 'big')+CHUNK.to_bytes(4, 'big')+bytes(10)
        elif operation == 'online':
            result = op.to_bytes(2, 'big')+b'\x03\x00'+JEDEC.to_bytes(4, 'little')+bytes(8)
        elif operation == 'read':
            result = bytes(self.device._flash[address:address+CHUNK])
            if failure and failure.kind == 'corrupt_read':
                result = bytes([result[0] ^ 1])+result[1:]
        elif operation in {'erase', 'program'}:
            data = b'\xff'*SECTOR_BYTES if operation == 'erase' else bytes(old & new for old, new in zip(self.device._flash[address:address+CHUNK], data_out))
            count = failure.after_bytes if failure and failure.kind == 'torn' else len(data)
            self.device._persist_flash(address, data[:count])
            if failure and failure.kind == 'torn':
                self.device.power_loss()
                raise SimulatedPowerLoss('Injected torn modeled NOR operation; partial bytes persisted')
        if failure and failure.kind == 'ack_loss':
            self.device._reenumerate(self.phase, connected=False, retain_ram=True)
            raise SimulatedAckLoss('Injected acknowledgement loss after modeled commit')
        return result

    def load(self, loader):
        self._check()
        if len(loader) != LOADER_SIZE or hashlib.sha256(loader).hexdigest() != self.device.loader_sha256:
            raise ValueError('Loader must match the 24064-byte simulator audit pin')
        inquiry = self.cmd(0x12)
        if inquiry[8:16].strip() != b'WL82' or inquiry[16:32].strip() != b'UBOOT1.00':
            raise ValueError('Unexpected simulated ROM identity')
        for offset in range(0, LOADER_SIZE, 512):
            self.cmd(0xFB06, address=RAM+offset, payload=loader[offset:offset+512])
        self.cmd(0xFB08, address=RAM)
        result = self.cmd(0xFC14)
        if int.from_bytes(result[2:6], 'big') != CHUNK:
            raise ValueError('Unexpected simulated loader buffer')
        self.online()

    def online(self):
        result = self.cmd(0xFC0A)
        kind, jedec = result[2], int.from_bytes(result[4:8], 'little')
        if kind != 3 or jedec != JEDEC:
            raise ValueError('Unexpected modeled flash geometry/JEDEC')
        return kind, jedec

    def read(self, address, size):
        self._check()
        if address % CHUNK or size % CHUNK or size <= 0 or not 0 <= address < address+size <= FLASH_SIZE:
            raise ValueError('Modeled reads require bounded aligned 256-byte chunks')
        return b''.join(self.cmd(0xFD05, address=offset) for offset in range(address, address+size, CHUNK))

    def erase(self, address):
        return self.cmd(0xFB01, address=address)

    def program(self, address, payload):
        return self.cmd(0xFB04, address=address, payload=payload)

    def sector(self, address=0xD8000):
        if address % SECTOR_BYTES:
            raise ValueError('Sector inspection requires 4 KiB alignment')
        return self.read(address, SECTOR_BYTES)

    def dump(self, file):
        file = Path(file)
        data = self.read(0, FLASH_SIZE)
        with file.open('xb') as fp:
            os.chmod(file, 0o600)
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        return {'file': file.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
