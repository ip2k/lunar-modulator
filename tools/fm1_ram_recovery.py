"""Exact-image, ROM-only RAM recovery probe; no command-line entry point.

MIT. Protocol/encryption facts credited to kagaimiq's jl-uboot-tool adb3f188
(MIT, Andrey Grigoryev), and the pinned-loader audit. Independent implementation.
Existing flash-backup Reader allowlist is unchanged. No flash or loader commands.
Device use needs the concrete experiment plan in firmware/ram-recovery/README.md.
"""
import binascii
import hashlib
import time

from fm1_uboot_read import Reader, RAM, request
from fm1_softkey_probe import KNOWN_092, SOFT_KEY

PROBE_SIZE = 700
PROBE_SHA = '4498aabad49b5acf1c4f90d949463b590e76e56acf80d6e6d01b292ee9d32c42'
BLOCK_SIZE = 512
UPLOAD_SIZE = 1024


def scramble_block(block):
    """ROM CrcDecode XOR stream, with its seed restarted for each 512-byte block."""
    if len(block) != BLOCK_SIZE:
        raise ValueError('Exactly one ROM block required')
    phrase = '孟黎我爱你，玉林'.encode('gb2312')
    crc = binascii.crc_hqx(b'\xff\xff', 0xffff)
    out = bytearray(block)
    for i in range(BLOCK_SIZE):
        crc = binascii.crc_hqx(phrase[i % len(phrase):i % len(phrase)+1], crc)
        out[i] ^= crc & 255
    return bytes(out)


def prepare_probe(image):
    """Validate the plain artifact before any USB access; fixed zero padding."""
    if len(image) != PROBE_SIZE or hashlib.sha256(image).hexdigest() != PROBE_SHA:
        raise ValueError('Only the reviewed 700-byte recovery probe is permitted')
    padded = image + bytes(UPLOAD_SIZE - len(image))
    return tuple(scramble_block(padded[i:i+BLOCK_SIZE])
                 for i in range(0, UPLOAD_SIZE, BLOCK_SIZE))


def checked_entry(events, now=None):
    """Bind to the fresh exact owner reply and its same-port UBOOT enumeration."""
    now = time.time() if now is None else now
    if not events or any(not 0 <= now-e['time'] <= 120 for e in events):
        raise ValueError('Fresh entry events required (at most 120 seconds old)')
    if any(a['time'] > b['time'] for a, b in zip(events, events[1:])):
        raise ValueError('Entry events out of time order')
    required = ('before', 'identity', 'sending_soft_key', 'uboot_enumerated')
    selected = []
    for kind in required:
        matches = [(i, e) for i, e in enumerate(events) if e.get('event') == kind]
        if len(matches) != 1:
            raise ValueError('Exactly one successful entry attempt required')
        selected.append(matches[0])
    if [i for i, _ in selected] != sorted(i for i, _ in selected):
        raise ValueError('Entry events out of protocol order')
    before, identity, key, entered = [e for _, e in selected]
    if (bytes.fromhex(identity.get('reply', '')) != KNOWN_092 or
            bytes.fromhex(key.get('hex', '')) != SOFT_KEY):
        raise ValueError('Exact owner identity and vetted soft key required')
    port = before['usb_path']
    prior = [d for d in before['usb'] if d['path'] == port and
             (d['vid'].lower(), d['pid'].lower()) == ('4c4a', 'c755')]
    observed = [d for d in entered['usb'] if d['path'] == port and
                (d['vid'].lower(), d['pid'].lower()) == ('4c4a', '8057')]
    if len(prior) != 1 or len(observed) != 1 or prior[0]['devnum'] == observed[0]['devnum']:
        raise ValueError('Need distinct normal-to-UBOOT enumeration on the same port')
    return observed[0]


class RamRecoveryReader(Reader):
    def __init__(self, device, log, image, entry_events):
        # Validate BEFORE super opens the physical device.
        self._blocks = prepare_probe(image)
        entered = checked_entry(entry_events)
        self._stage = 'inquiry'
        self._next_block = 0
        super().__init__(device, log)
        try:
            if (self.usb.name != entered['path'] or
                    (self.usb / 'devnum').read_text().strip() != entered['devnum']):
                raise ValueError('SG device differs from fresh owner UBOOT entry')
        except Exception:
            self.close()
            raise

    def build_request(self, op, address, payload):
        if self.phase != 'rom':
            raise ValueError('Probe only runs through mask ROM, never a loader')
        if self._stage == 'inquiry' and op == 0x12:
            result = request(op, 'rom', address=address, payload=payload)
            self._stage = 'inquiry-pending'
            return result
        if self._stage == 'upload' and op == 0xFB06:
            i = self._next_block
            if (i >= len(self._blocks) or address != RAM + i*BLOCK_SIZE or
                    payload != self._blocks[i]):
                raise ValueError('Only the next exact encrypted probe block')
            result = request(op, 'rom', address=address, payload=payload)
            self._next_block += 1  # Consumed even on timeout; never retry.
            self._stage = 'upload-pending'
            return result
        if (self._stage == 'jump' and op == 0xFB08 and
                self._next_block == len(self._blocks)):
            result = request(op, 'rom', address=address, payload=payload)
            self._stage = 'finished'  # Never repeat, even if no response returns.
            return result
        raise ValueError('Operation out of order or outside exact-probe allowlist')

    def run_probe(self):
        if self._stage != 'inquiry':
            raise ValueError('Probe is attempted once per physical connection')
        try:
            inquiry = self.cmd(0x12)
            if (inquiry[8:16].decode('ascii').strip() != 'WL82' or
                    inquiry[16:32].decode('ascii').strip() != 'UBOOT1.00'):
                raise ValueError('Unexpected ROM inquiry; no upload')
            self.log('probe_upload', sha256=PROBE_SHA, bytes=PROBE_SIZE,
                     padded_bytes=UPLOAD_SIZE, base=RAM)
            for i, block in enumerate(self._blocks):
                self._stage = 'upload'
                self.cmd(0xFB06, address=RAM+i*BLOCK_SIZE, payload=block)
            self._stage = 'jump'
            self.log('probe_jump_attempt', entry=RAM)
            # A disconnect/timeout is ambiguous. Caller must observe a DISTINCT
            # USB re-enumeration, not interpret an exception/echo as reset proof.
            self.cmd(0xFB08, address=RAM)
            self.log('probe_jump_response', reset_observed=False)
        finally:
            self._stage = 'finished'
