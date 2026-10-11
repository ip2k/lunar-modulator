"""One exact pinned-loader reset attempt; injected transport, no opener or CLI.

Protocol facts credited to kagaimiq's jl-uboot-tool adb3f188 (MIT, Andrey
Grigoryev). FC0C argument 1 is a RUN_APP request, not proof of a cold reset
or successful stock boot. The pinned loader parses retained RAM config at
0x01c07e00..0x01c081ff and 0x01c08e00..0x01c091ff, and can alter NOR status
if it selects quad mode. This offline guard is NOT hardware ready: that
initializer boundary is unresolved, and there is no no-flash-effects claim.
Python objects and supplied USB observations are trusted caller assertions,
not an adversarial sandbox or independent physical identity attestation.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time

from fm1_uboot_read import Reader, request, LOADER_SHA, LOADER_SIZE, RAM
from fm1_ram_recovery import checked_entry

ENTRY_SHA = '58f1b2def18eddaadc3a23e1a4fa79bd2b256101b4fefe2c3e56345fb1d1b40b'
OWNER_USB = {'path': '3-2', 'busnum': '3', 'devnum': '21',
             'vid': '4c4a', 'pid': '8057'}
_PREPARED = object()
RESET_CDB = bytes.fromhex('fc0c00000001ffffffffffffffffffff')


def _usb(value):
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in OWNER_USB.items()):
        raise ValueError('Exact current owner UBOOT topology required')
    return dict(OWNER_USB)


def _fresh(stamp, now, age):
    if (type(stamp) not in (float, int) or not math.isfinite(stamp) or
            not 0 <= now - stamp <= age):
        raise ValueError('Fresh passive USB observation required')


def prepare_reset(loader, *, entry_log, observation, observed_at, receipt_path, now=None):
    """Freeze validated local inputs before any transport is accepted.

    entry_log is the exact reviewed private probe receipt. observation is a
    fresh passive sysfs snapshot of the same owner port at device number 21.
    A new exclusive receipt file prevents ordinary reuse across instances.
    """
    now = time.time() if now is None else now
    loader, entry_log = bytes(loader), bytes(entry_log)
    if len(loader) != LOADER_SIZE or hashlib.sha256(loader).hexdigest() != LOADER_SHA:
        raise ValueError('Exact audited loader required')
    if hashlib.sha256(entry_log).hexdigest() != ENTRY_SHA:
        raise ValueError('Exact reviewed owner entry receipt required')
    events = [json.loads(line) for line in entry_log.splitlines()]
    # Historical entry is deliberately not claimed fresh. Verify its ordered
    # exact owner reply/soft-key and same-port normal19 -> ROM20 transition.
    entered = checked_entry(events[:7], now=events[6]['time'])
    if entered['path'] != '3-2' or entered['devnum'] != '20':
        raise ValueError('Unexpected prior entry')
    ended = [e for e in events if e.get('event') == 'experiment_finished']
    if len(ended) != 1 or ended[0].get('retry') is not False:
        raise ValueError('Reviewed single probe completion required')
    usb = [d for d in ended[0]['usb'] if d.get('path') == '3-2']
    if len(usb) != 1:
        raise ValueError('Ambiguous prior USB observation')
    _usb(usb[0])
    _usb(observation)
    _fresh(observed_at, now, 10)
    return LoaderResetGuard(loader, Path(receipt_path), observed_at, _prepared=_PREPARED)


class LoaderResetGuard(Reader):
    """Reader.load's unchanged sequence, plus one fixed reset CDB.

    transport.binding() must return simulated=True, connected=True, a stable nonempty
    session_id, observed_at (<=2 seconds old), and usb=the exact topology.
    transport.exchange(cdb, payload, in_size) submits one syscall without
    retry and returns bytes; transport.close() closes that bound handle.
    Factory preparation is required; constructing a new object is not a
    campaign retry authorization. No device path is opened by this module.
    """
    def __init__(self, loader, receipt_path, observed_at, *, _prepared=None):
        if _prepared is not _PREPARED:
            raise ValueError('Use prepare_reset to validate prior evidence')
        # Factory evidence and the exact loader are required before binding.
        self._loader = bytes(loader)
        if len(self._loader) != LOADER_SIZE or hashlib.sha256(self._loader).hexdigest() != LOADER_SHA:
            raise ValueError('Exact audited loader required')
        self._receipt_path = receipt_path
        self._observed_at = observed_at
        self._stage, self._next = 'unbound', 0
        self.phase = 'rom'
        self._transport = self._fp = None
        self._session = None

    def bind(self, transport):
        if self._stage != 'unbound':
            raise ValueError('Guard already consumed')
        _fresh(self._observed_at, time.time(), 10)
        # No transport is accepted until exclusive receipt creation succeeds.
        self._fp = self._receipt_path.open('x', encoding='utf8')
        try:
            os.chmod(self._receipt_path, 0o600)
            self._transport = transport
            self._stage = 'inquiry'
            self._check_binding(first=True)
            self.log('prepared', loader_sha256=LOADER_SHA, entry_sha256=ENTRY_SHA,
                     usb=OWNER_USB, session_id=self._session,
                     hardware_ready=False, initializer_boundary_resolved=False,
                     simulated=True,
                     physical_identity_attested=False)
            return self
        except BaseException:
            self.close()
            raise

    def log(self, event, **fields):
        self._fp.write(json.dumps({'time': time.time(), 'event': event, **fields,
                                  'simulated': True, 'hardware_ready': False,
                                  'initializer_boundary_resolved': False}, sort_keys=True) + '\n')
        self._fp.flush()
        os.fsync(self._fp.fileno())
        fd = os.open(self._receipt_path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _check_binding(self, first=False):
        binding = self._transport.binding()
        if not isinstance(binding, dict) or binding.get('simulated') is not True:
            raise ValueError('Offline simulation only: loader initializer unresolved')
        if binding.get('connected') is not True:
            raise ValueError('Disconnected session')
        _usb(binding.get('usb'))
        _fresh(binding.get('observed_at'), time.time(), 2)
        session = binding.get('session_id')
        if not isinstance(session, str) or not session:
            raise ValueError('Bound handle identity required')
        if first:
            self._session = session
        elif session != self._session:
            raise ValueError('Replaced handle')

    def build_request(self, op, address, payload):
        """Lowest builder consumes each exact operation before submission."""
        if self._stage == 'inquiry' and op == 0x12 and self.phase == 'rom':
            result = request(op, 'rom', address=address, payload=payload)
        elif self._stage == 'upload' and op == 0xFB06 and self.phase == 'rom':
            start = self._next * 512
            if address != RAM + start or payload != self._loader[start:start+512]:
                raise ValueError('Only next exact pinned loader block')
            result = request(op, 'rom', address=address, payload=payload)
        elif self._stage == 'jump' and op == 0xFB08 and self.phase == 'rom':
            result = request(op, 'rom', address=address, payload=payload)
        elif self._stage == 'buffer' and op == 0xFC14 and self.phase == 'loader':
            result = request(op, 'loader', address=address, payload=payload)
        elif self._stage == 'online' and op == 0xFC0A and self.phase == 'loader':
            result = request(op, 'loader', address=address, payload=payload)
        elif (self._stage == 'ready' and op == 0xFC0C and self.phase == 'loader'
              and address == 0 and payload == b''):
            result = RESET_CDB, b'', 16
        else:
            raise ValueError('Outside exact ordered loader/reset policy')
        self._stage = 'pending'
        return result

    def cmd(self, op, *, address=0, payload=b''):
        if self._transport is None or self._stage in ('finished', 'unbound', 'pending'):
            raise ValueError('Consumed or unbound guard')
        try:
            self._check_binding()
            cdb, data, size = self.build_request(op, address, payload)
            if op == 0xFC0C:
                self.log('reset_intent', cdb=cdb.hex(), in_size=16, retry=False,
                         reset_observed=False, usb=OWNER_USB,
                         hardware_ready=False, initializer_boundary_resolved=False,
                         simulated=True,
                         session_id=self._session, loader_sha256=LOADER_SHA)
            else:
                self.log('command_intent', cdb=cdb.hex(), out_len=len(data), in_size=size)
            # Disk durability may take time; recheck immediately before the
            # one submission, without restoring the already consumed state.
            self._check_binding()
            result = self._transport.exchange(cdb, data, size)
            if not isinstance(result, bytes) or len(result) != size:
                raise ValueError('Incomplete or malformed response')
            if size == 16 and int.from_bytes(result[:2], 'big') != op:
                raise ValueError('Wrong command echo')
            if op == 0xFC0C:
                self.log('reset_reply', reset_observed=False)
                return result
            self._check_binding()
            if op == 0x12:
                if (result[8:16].decode('ascii').strip() != 'WL82' or
                        result[16:32].decode('ascii').strip() != 'UBOOT1.00'):
                    raise ValueError('Unexpected ROM inquiry')
                self._stage = 'upload'
            elif op == 0xFB06:
                self._next += 1
                self._stage = 'jump' if self._next == LOADER_SIZE // 512 else 'upload'
            elif op == 0xFB08:
                self.phase, self._stage = 'loader', 'buffer'
            elif op == 0xFC14:
                if not 256 <= int.from_bytes(result[2:6], 'big') <= 65535:
                    raise ValueError('Unexpected loader buffer')
                self._stage = 'online'
            elif op == 0xFC0A:
                if result[2] != 3 or int.from_bytes(result[4:8], 'little') != 0x856014:
                    raise ValueError('Unexpected NOR identity')
                self._stage = 'ready'
            return result
        except BaseException:
            self.close()
            raise
        finally:
            if op == 0xFC0C:
                self.close()  # A lost response must never permit replay.

    def run_reset(self):
        try:
            if self._stage != 'inquiry':
                raise ValueError('One fresh loader/reset attempt required')
            Reader.load(self, self._loader)
            self.cmd(0xFC0C)
            return {'attempted': True, 'retry': False, 'reset_observed': False,
                    'hardware_ready': False, 'initializer_boundary_resolved': False,
                    'simulated': True}
        finally:
            self.close()

    def close(self):
        self._stage = 'finished'
        transport, fp = self._transport, self._fp
        self._transport = self._fp = None
        try:
            if transport is not None:
                transport.close()
        finally:
            if fp is not None:
                fp.close()
