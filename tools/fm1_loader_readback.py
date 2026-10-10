"""Prepared, unexecuted fixed RAM readback of the audited WL82 loader.

No CLI/device-opening entry point is provided. Device use requires review of
the proposal in notes/2026-10-10-fm1-live-bringup.md. This does not allow ROM,
MMIO, eFuse, flash, arbitrary RAM, custom payloads or additional jumps.
The existing backup reader's allowlist remains unchanged. MIT licence.
"""
import hashlib

from fm1_uboot_read import Reader, RAM

READBACK_ADDRESS = RAM + 0x23DE
READBACK_BYTES = 64
READBACK_SHA = '55a58166f612936e6ab55f33a373c07718bcc2069826806f9626521c68bf94c3'


def readback_request(op, phase, *, address, payload=b''):
    """One exact FD07 code slice, below the pinned loader's 256-byte buffer."""
    if (op != 0xFD07 or phase != 'loader' or
            address != READBACK_ADDRESS or payload):
        raise ValueError('Only the fixed audited-loader RAM readback is permitted')
    cdb = (b'\xfd\x07' + READBACK_ADDRESS.to_bytes(4, 'big') +
           READBACK_BYTES.to_bytes(2, 'big')).ljust(16, b'\xff')
    return cdb, b'', READBACK_BYTES


class LoaderReadbackReader(Reader):
    def __init__(self, device, log):
        super().__init__(device, log)
        self._readback_ready = False
        self._readback_used = False

    def load(self, loader):
        self._readback_ready = False
        super().load(loader)  # Hash, identity, upload, buffer and flash identity checks.
        self._readback_ready = True

    def build_request(self, op, address, payload):
        if op != 0xFD07:
            return super().build_request(op, address, payload)
        if not self._readback_ready or self._readback_used:
            raise ValueError('Readback requires a verified loader and is attempted once')
        result = readback_request(op, self.phase, address=address, payload=payload)
        self._readback_used = True  # A transport failure must not trigger an automatic retry.
        return result

    def readback(self):
        data = self.cmd(0xFD07, address=READBACK_ADDRESS)
        if len(data) != READBACK_BYTES or hashlib.sha256(data).hexdigest() != READBACK_SHA:
            raise ValueError('Loader RAM readback does not match the pinned plain code')
        self.log('loader_ram_readback_verified', address=READBACK_ADDRESS,
                 bytes=READBACK_BYTES, sha256=READBACK_SHA)
        return data
