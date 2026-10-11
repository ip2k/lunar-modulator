"""Exact 14-byte ROM core-reset experiment; no physical opener or CLI.

MIT. ROM framing/cipher facts credited to kagaimiq's jl-uboot-tool adb3f188
(MIT, Andrey Grigoryev). This executes a fixed independently built RAM stub,
never the NOR loader. A jump reply or disconnect is not proof of execution,
reset, stock boot, or flash preservation. Injected topology/handle assertions
are trusted caller evidence, not independent physical identity attestation.
"""
import hashlib
import json
import os
from pathlib import Path
import time

from fm1_uboot_read import request, RAM
from fm1_ram_recovery import checked_entry, scramble_block
from fm1_loader_reset import ENTRY_SHA, OWNER_USB, _usb, _fresh

IMAGE_SIZE = 14
IMAGE_SHA = 'b137c15cc0b82d0d056246f08ad2292f754216b9f70bd83a1caec4e35978cee5'
SOURCE_SHA = '8b6530913943baeec54a67cb82482c3f0870078761c6fe1eb661812f45360e92'
BLOCK_SHA = 'cffeb8df17fe3dbe0fa85c162ad2b29b71ef247e8074259aa13dcebf7d88582f'
_PREPARED = object()


def prepare_core_reset(image, *, source, entry_log, observation, observed_at,
                       receipt_path, now=None):
    """Validate and freeze the exact stub/source and owner evidence locally.

    source is the exact core-reset.S byte content from the build receipt.
    Historical probe evidence is pinned but deliberately not called fresh.
    observation must be the actual fresh passive same-port UBOOT snapshot.
    No transport is touched until bind; no runtime hash override is offered.
    """
    now = time.time() if now is None else now
    image, source, entry_log = bytes(image), bytes(source), bytes(entry_log)
    if len(image) != IMAGE_SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA:
        raise ValueError('Exact reviewed 14-byte stub required')
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Exact built assembly source required')
    if hashlib.sha256(entry_log).hexdigest() != ENTRY_SHA:
        raise ValueError('Exact reviewed owner entry receipt required')
    events = [json.loads(line) for line in entry_log.splitlines()]
    entered = checked_entry(events[:7], now=events[6]['time'])
    if entered.get('path') != '3-2' or entered.get('devnum') != '20':
        raise ValueError('Unexpected historical owner entry')
    ended = [e for e in events if e.get('event') == 'experiment_finished']
    if len(ended) != 1 or ended[0].get('retry') is not False:
        raise ValueError('Reviewed single probe completion required')
    prior = [u for u in ended[0]['usb'] if u.get('path') == '3-2']
    if len(prior) != 1:
        raise ValueError('Ambiguous prior owner topology')
    _usb(prior[0])
    _usb(observation)
    _fresh(observed_at, now, 10)
    block = scramble_block(image + bytes(512 - IMAGE_SIZE))
    if hashlib.sha256(block).hexdigest() != BLOCK_SHA:
        raise ValueError('Fixed encrypted upload mismatch')
    return CoreResetGuard(block, Path(receipt_path), observed_at, _prepared=_PREPARED)


class CoreResetGuard:
    """One inquiry, one exact encrypted FB06 block, one exact FB08 jump.

    transport.binding() supplies connected=True, usb=exact OWNER_USB,
    nonempty stable session_id and observed_at <=2 seconds old. Caller must
    bind these assertions to the actual open handle/sysfs connection and
    maintain exclusive device access. exchange(cdb,payload,in_size) must
    perform one attempt without transport retries. close() releases handle.
    All uncertainty latches closed. A new receipt/instance is not retry
    authorization. Private Python fields are not a hostile-code sandbox.
    """
    def __init__(self, block, receipt_path, observed_at, *, _prepared=None):
        if _prepared is not _PREPARED:
            raise ValueError('Use prepare_core_reset for local preflight')
        self._block = bytes(block)
        if len(self._block) != 512 or hashlib.sha256(self._block).hexdigest() != BLOCK_SHA:
            raise ValueError('Exact encrypted block required')
        self._receipt_path, self._observed_at = receipt_path, observed_at
        self._stage = 'unbound'
        self._transport = self._fp = self._session = None

    def bind(self, transport):
        if self._stage != 'unbound':
            raise ValueError('Guard already consumed')
        _fresh(self._observed_at, time.time(), 10)
        self._fp = self._receipt_path.open('x', encoding='utf8')
        try:
            os.chmod(self._receipt_path, 0o600)
            self._transport = transport
            self._stage = 'inquiry'
            self._check_binding(first=True)
            self.log('prepared', image_sha256=IMAGE_SHA, source_sha256=SOURCE_SHA,
                     block_sha256=BLOCK_SHA, entry_sha256=ENTRY_SHA)
            return self
        except BaseException:
            self.close()
            raise

    def log(self, event, **fields):
        record = {'time': time.time(), 'event': event, **fields,
                  'usb': OWNER_USB, 'session_id': self._session,
                  'physical_identity_attested': False, 'reset_observed': False}
        self._fp.write(json.dumps(record, sort_keys=True) + '\n')
        self._fp.flush()
        os.fsync(self._fp.fileno())
        fd = os.open(self._receipt_path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _check_binding(self, first=False):
        value = self._transport.binding()
        if not isinstance(value, dict) or value.get('connected') is not True:
            raise ValueError('Disconnected bound handle')
        _usb(value.get('usb'))
        _fresh(value.get('observed_at'), time.time(), 2)
        session = value.get('session_id')
        if not isinstance(session, str) or not session:
            raise ValueError('Explicit bound handle identity required')
        if first:
            self._session = session
        elif session != self._session:
            raise ValueError('Replaced bound handle')

    def build_request(self, op, address, payload):
        """Lowest builder allows only the next exact ROM operation."""
        if self._stage == 'inquiry' and op == 0x12:
            result = request(op, 'rom', address=address, payload=payload)
        elif self._stage == 'upload' and op == 0xFB06:
            if address != RAM or payload != self._block:
                raise ValueError('Only the one exact encrypted stub block')
            result = request(op, 'rom', address=address, payload=payload)
        elif self._stage == 'jump' and op == 0xFB08:
            result = request(op, 'rom', address=address, payload=payload)
        else:
            raise ValueError('Outside ordered exact core-reset policy')
        self._stage = 'pending'  # Consumed before syscall or durable logging.
        return result

    def cmd(self, op, *, address=0, payload=b''):
        if self._transport is None or self._stage in ('unbound', 'finished', 'pending'):
            raise ValueError('Unbound or consumed guard')
        try:
            self._check_binding()
            cdb, data, size = self.build_request(op, address, payload)
            self.log('jump_intent' if op == 0xFB08 else 'command_intent',
                     cdb=cdb.hex(), out_len=len(data), in_size=size, retry=False)
            self._check_binding()  # Immediately after fsync, before submission.
            result = self._transport.exchange(cdb, data, size)
            if not isinstance(result, bytes) or len(result) != size:
                raise ValueError('Incomplete or malformed response')
            if size == 16 and int.from_bytes(result[:2], 'big') != op:
                raise ValueError('Wrong command echo')
            # Expected disconnect after jump remains ambiguous and latches.
            self._check_binding()
            if op == 0x12:
                if (result[8:16].decode('ascii').strip() != 'WL82' or
                        result[16:32].decode('ascii').strip() != 'UBOOT1.00'):
                    raise ValueError('Unexpected ROM inquiry; no upload')
                self._stage = 'upload'
            elif op == 0xFB06:
                self._stage = 'jump'
            else:
                self.log('jump_reply', retry=False)
            return result
        except BaseException:
            self.close()
            raise
        finally:
            if op == 0xFB08:
                self.close()

    def run_reset(self):
        try:
            if self._stage != 'inquiry':
                raise ValueError('One fresh exact core-reset attempt required')
            self.cmd(0x12)
            self.cmd(0xFB06, address=RAM, payload=self._block)
            self.cmd(0xFB08, address=RAM)
            return {'attempted': True, 'retry': False,
                    'physical_identity_attested': False, 'reset_observed': False}
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
