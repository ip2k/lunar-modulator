#!/usr/bin/env python3
"""Bounded mask-ROM RAM runner: upload one admitted image into SRAM and jump to it.

With a target already in mask-ROM UBOOT1.00 (USB 4c4a:8057), this tool does one
thing: INQUIRY, write the image into the SRAM window with WRITE_MEMORY (FB06),
read it back with READ_MEMORY (FD07) and compare, then call it once with JUMP
(FB08). Nothing else is implemented, and everything else is refused in code:

* an allow-list of exactly four commands (SCSI INQUIRY 0x12, FB06, FD07, FB08),
  enforced twice, when a request is built and again on the final CDB bytes;
* every flash or loader command (erase FB01, program FB04, flash read FD05,
  key FC09, online device FC0A, buffer size FC14, run app FC0C), the eFuse
  loader command FC12 and the raw A1 write, MIDI-shaped bytes (a CDB that
  begins F0, the SysEx start of the soft key), the head of a vendor syscmd
  frame (00 59, docs/02 section 6; syscmd 33-36 and 48 named) and online-tool
  frames (5A AA A5) are refused by name as well as by the allow-list;
* addresses only inside the window where the ROM already accepted and ran the
  vendor loader, 0x01C02000 + 24,064 bytes [verified: tools/fm1_uboot_read.py,
  notes/2026-10-22-devkit-uart-bringup.md], in whole 512-byte blocks, in order;
* one pass: inquiry, every block written, every block read back equal, one
  jump. A block is never resent and the jump is never retried, even after a
  timeout; a read-back mismatch or failure stops before the jump.

What the read-back proves: FD07 returns the ciphered form and is deciphered
here, as FM-1-transporter's jl_rom_mem_read does [reported]. A ROM that kept
the ciphered bytes unchanged would read back identically, so an equal
read-back proves the transfer, not that SRAM holds the plain image; the image
running (its own UART output) is what proves that [verified on the dev kit,
notes/2026-11-08-ram-runner-devkit.md].

Only `run` sends anything. The flash-reader methods inherited from
fm1_uboot_read.Reader (load, online, dump) are overridden to refuse.

Which device: the role is fixed to `devkit` (the AC79 dev kit) and every open
goes through tools/bench_target.py pinning (--usb-path, --devnum). There is no
FM-1 mode; running Lunar code on the FM-1 needs its own owner approval and a
transporter adapter (notes/2026-11-08-ram-runner-devkit.md). No MIDI, serial or
SysEx code is imported here.

Protocol facts: CDB layout, FB06/FD07/FB08 arguments and the per-transfer
cipher from kurogedelic's FM-1-transporter src/jieli_uboot.c (MIT) and
kagaimiq's jl-uboot-tool (MIT) [reported]; the CRC-16/XMODEM of the ciphered
payload in FB06 as in tools/fm1_uboot_read.py [verified on hardware for the
loader upload]. MIT licence, like this repository.
"""
import argparse
import binascii
import ctypes as C
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm1_uboot_read as base  # noqa: E402  (SGHeader, Reader: pin, then open)

WINDOW_BASE = base.RAM            # 0x01C02000
WINDOW_SIZE = base.LOADER_SIZE    # 24,064 bytes = 47 blocks
BLOCK = 512
INQUIRY, WRITE_MEMORY, READ_MEMORY, JUMP = 0x12, 0xFB06, 0xFD07, 0xFB08
JUMP_ARG = 0x0001                 # as the loader jump that the ROM honoured
ALLOWED_OPS = frozenset({WRITE_MEMORY, READ_MEMORY, JUMP})
# Named refusals: the allow-list already excludes them; naming them keeps the
# reason in the error and in the tests.
FORBIDDEN_OPS = {
    0xFB01: 'loader flash erase', 0xFB04: 'loader flash program',
    0xFD05: 'loader flash read', 0xFC09: 'loader key read',
    0xFC0A: 'loader online device', 0xFC14: 'loader buffer size',
    0xFC0C: 'loader run app / reset', 0xFC12: 'eFuse-burning loader command',
}
# Vendor syscmd frames are [00 59][cmd][len24][payload][~sum] (docs/02 section 6);
# 33-36 and 48 copy memory or touch flash (CLAUDE.md trap 7). Any 00 59 head is
# refused; these are named so the reason says which.
SYSCMD_HEAD = b'\x00\x59'
SYSCMD_FORBIDDEN = frozenset({33, 34, 35, 36, 48})
SG_TIMEOUT_MS = 3000
_MAGIC = '孟黎我爱你，玉林'.encode('gb2312')  # C3 CF C0 E8 ... C1 D6


class Refused(ValueError):
    """A command, address or order this tool will not send."""


def cipher(data):
    """jl_crc_cipher with key 0xFFFF, seeded afresh for each transfer.

    The ROM applies it to every WRITE_MEMORY/READ_MEMORY payload; it is its
    own inverse (an XOR keystream)."""
    crc = binascii.crc_hqx(b'\xff\xff', 0xFFFF)
    out = bytearray(data)
    for i in range(len(out)):
        crc = binascii.crc_hqx(_MAGIC[i % 16:i % 16 + 1], crc)
        out[i] ^= crc & 0xFF
    return bytes(out)


def admit(image, sha256):
    """The image the caller named, by hash, and small enough for the window."""
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise Refused('An expected SHA-256 (64 hex digits) is required')
    actual = hashlib.sha256(image).hexdigest()
    if actual != sha256.lower():
        raise Refused(f'Image SHA-256 {actual} is not the expected {sha256}')
    if not image:
        raise Refused('Empty image')
    if len(image) > WINDOW_SIZE:
        raise Refused(f'Image of {len(image)} bytes exceeds the {WINDOW_SIZE}-byte SRAM window')
    return image


def plan(image):
    """Blocks to write: [(address, plain 512 bytes, ciphered 512 bytes)].

    Zero padding to a whole block; everything starts at the window base, the
    image's link address. Pure: no device involved."""
    padded = image + bytes(-len(image) % BLOCK)
    blocks = []
    for offset in range(0, len(padded), BLOCK):
        plain = padded[offset:offset + BLOCK]
        blocks.append((WINDOW_BASE + offset, plain, cipher(plain)))
    if blocks[-1][0] + BLOCK > WINDOW_BASE + WINDOW_SIZE:
        raise Refused('Padded image leaves the SRAM window')
    return blocks


def describe(image, sha256):
    """What a run would write and call, for reviews and run plans."""
    blocks = plan(admit(image, sha256))
    end = blocks[-1][0] + BLOCK
    return {
        'image_sha256': sha256.lower(), 'image_bytes': len(image),
        'padded_bytes': end - WINDOW_BASE, 'blocks': len(blocks), 'block_bytes': BLOCK,
        'write_range': [hex(WINDOW_BASE), hex(end)],
        'window': [hex(WINDOW_BASE), hex(WINDOW_BASE + WINDOW_SIZE)],
        'jump': {'address': hex(WINDOW_BASE), 'arg': JUMP_ARG},
        'commands': (['INQUIRY'] + [f'FB06 {a:#010x} 512' for a, _p, _c in blocks]
                     + [f'FD07 {a:#010x} 512' for a, _p, _c in blocks]
                     + [f'FB08 {WINDOW_BASE:#010x} arg {JUMP_ARG}']),
        'flash_writes': 0,
    }


def check_cdb(cdb):
    """Final gate on the bytes that go to the ioctl. Independent of the state
    machine: an INQUIRY, or one of three ROM commands with an in-window
    address; nothing else, whatever produced it."""
    if not isinstance(cdb, (bytes, bytearray)):
        raise Refused('CDB must be bytes')
    cdb = bytes(cdb)
    if cdb == bytes.fromhex('120000002400'):
        return cdb
    if len(cdb) != 16:
        raise Refused(f'CDB of {len(cdb)} bytes')
    if cdb[0] == 0xF0:
        raise Refused('Refused: begins F0 (MIDI SysEx shape, such as the soft key)')
    if cdb[:3] == b'\x5a\xaa\xa5':
        raise Refused('Refused: online-tool 5A AA A5 frame')
    if cdb[:2] == SYSCMD_HEAD:
        named = ' (forbidden syscmd)' if cdb[2] in SYSCMD_FORBIDDEN else ''
        raise Refused(f'Refused: vendor syscmd frame, command {cdb[2]}{named}')
    if cdb[0] == 0xA1:
        raise Refused('Refused: raw A1 (eFuse write)')
    op = int.from_bytes(cdb[:2], 'big')
    if op in FORBIDDEN_OPS:
        raise Refused(f'Refused: {op:04X} ({FORBIDDEN_OPS[op]})')
    if op not in ALLOWED_OPS:
        raise Refused(f'Refused: {op:04X} is not on the allow-list')
    address = int.from_bytes(cdb[2:6], 'big')
    if op == JUMP:
        if address != WINDOW_BASE or cdb[6:8] != JUMP_ARG.to_bytes(2, 'big') or cdb[8:] != b'\xff' * 8:
            raise Refused('Refused: JUMP other than the window base with argument 1')
        return cdb
    length = int.from_bytes(cdb[6:8], 'big')
    if (length != BLOCK or address % BLOCK or
            not WINDOW_BASE <= address <= WINDOW_BASE + WINDOW_SIZE - BLOCK):
        raise Refused(f'Refused: {op:04X} at {address:#x} length {length} outside the SRAM window')
    tail = cdb[11:] if op == WRITE_MEMORY else cdb[8:]
    if tail != b'\xff' * len(tail) or (op == WRITE_MEMORY and cdb[8] != 0):
        raise Refused(f'Refused: {op:04X} with unexpected argument bytes')
    return cdb


class Sequence:
    """inquiry -> upload (each block once, in order) -> verify (each block
    once, in order) -> jump (once) -> done. Any refusal or transport failure
    ends it in `stopped`; it is never rewound."""

    def __init__(self, blocks):
        self.blocks, self.stage, self.next = blocks, 'inquiry', 0

    def request(self, op, address=0, payload=b''):
        if self.stage in ('done', 'stopped'):
            raise Refused(f'Sequence is {self.stage}; nothing more is sent')
        if self.stage == 'inquiry' and op == INQUIRY and not address and not payload:
            self.stage = 'upload'
            return bytes.fromhex('120000002400'), b'', 36
        if op == WRITE_MEMORY and self.stage == 'upload':
            addr, _plain, sealed = self.blocks[self.next]
            if address != addr or payload != sealed:
                raise Refused('Only the next block of the admitted image')
            self._advance('verify')
            crc = binascii.crc_hqx(sealed, 0).to_bytes(2, 'little')
            args = addr.to_bytes(4, 'big') + BLOCK.to_bytes(2, 'big') + b'\x00' + crc
            return (WRITE_MEMORY.to_bytes(2, 'big') + args).ljust(16, b'\xff'), sealed, 0
        if op == READ_MEMORY and self.stage == 'verify' and not payload:
            if address != self.blocks[self.next][0]:
                raise Refused('Only the next block of the admitted image')
            self._advance('jump')
            args = address.to_bytes(4, 'big') + BLOCK.to_bytes(2, 'big')
            return (READ_MEMORY.to_bytes(2, 'big') + args).ljust(16, b'\xff'), b'', BLOCK
        if op == JUMP and self.stage == 'jump' and address == WINDOW_BASE and not payload:
            self.stage = 'done'
            args = WINDOW_BASE.to_bytes(4, 'big') + JUMP_ARG.to_bytes(2, 'big')
            return (JUMP.to_bytes(2, 'big') + args).ljust(16, b'\xff'), b'', 16
        raise Refused(f'{op:04X} at {address:#x} is not allowed in stage {self.stage}')

    def _advance(self, after):
        self.next += 1
        if self.next == len(self.blocks):
            self.stage, self.next = after, 0

    def stop(self):
        self.stage = 'stopped'


class RamRunner(base.Reader):
    """One RAM run on a pinned dev kit. Construction pins, then opens."""
    ROLE = 'devkit'  # never the FM-1: that needs its own approval and adapter

    def __init__(self, device, log, image, sha256, **pin):
        # Validate the image before anything touches USB.
        self.image = admit(image, sha256)
        self.sha256 = sha256.lower()
        self.blocks = plan(self.image)
        self.seq = Sequence(self.blocks)
        super().__init__(device, log, **pin)

    def build_request(self, op, address, payload):
        return self.seq.request(op, address, payload)

    # The base Reader's flash-backup path: never on a RAM run.
    def load(self, *_a, **_k):
        raise Refused('RamRunner never uploads or runs the flash loader')

    def online(self, *_a, **_k):
        raise Refused('RamRunner never talks to the flash loader')

    def dump(self, *_a, **_k):
        raise Refused('RamRunner never reads flash')

    def transport(self, cdb, data_out, in_size, timeout_ms=SG_TIMEOUT_MS):
        """SG_IO, as tools/fm1_uboot_read.py's Reader.cmd."""
        command = C.create_string_buffer(cdb)
        sense = C.create_string_buffer(32)
        data = C.create_string_buffer(data_out) if data_out else C.create_string_buffer(in_size)
        h = base.SGHeader(interface_id=ord('S'), direction=-2 if data_out else -3,
                          cmd_len=len(cdb), sense_max=32, data_len=len(data_out) or in_size,
                          data=C.addressof(data), cmd=C.addressof(command),
                          sense=C.addressof(sense), timeout=timeout_ms)
        fcntl.ioctl(self.fd, 0x2285, h)
        if h.status or h.host or h.driver or (h.info & 1) or h.resid:
            raise OSError(f'SG_IO status={h.status} host={h.host} driver={h.driver} '
                          f'resid={h.resid} sense={sense.raw[:h.sense_len].hex()}')
        return data.raw[:in_size]

    def cmd(self, op, *, address=0, payload=b''):
        stage = self.seq.stage
        try:
            cdb, data_out, in_size = self.build_request(op, address, payload)
            check_cdb(cdb)
        except Refused:
            self.seq.stop()
            raise
        self.log('command', stage=stage, cdb=cdb.hex(), out_len=len(data_out), in_len=in_size)
        try:
            result = self.transport(cdb, data_out, in_size)
        except Exception:
            if op != JUMP:
                self.seq.stop()
            raise
        if in_size == 16 and int.from_bytes(result[:2], 'big') != op:
            raise ValueError(f'Response did not echo {op:04X}: {result.hex()}')
        return result

    def run(self):
        """Returns a receipt. Raises (with the sequence stopped) before the
        jump on any inquiry, write or read-back problem."""
        receipt = {'image_sha256': self.sha256, 'image_bytes': len(self.image),
                   'blocks': len(self.blocks), 'base': hex(WINDOW_BASE)}
        inquiry = self.cmd(INQUIRY)
        vendor, product = inquiry[8:16].decode('ascii', 'replace').strip(), inquiry[16:32].decode('ascii', 'replace').strip()
        self.log('inquiry', vendor=vendor, product=product)
        if (vendor, product) != ('WL82', 'UBOOT1.00'):
            self.seq.stop()
            raise Refused(f'Not WL82 UBOOT1.00 ({vendor!r} {product!r}); nothing uploaded')
        receipt['inquiry'] = f'{vendor} {product}'
        for address, _plain, sealed in self.blocks:
            self.cmd(WRITE_MEMORY, address=address, payload=sealed)
        self.log('uploaded', blocks=len(self.blocks))
        for address, plain, _sealed in self.blocks:
            raw = self.cmd(READ_MEMORY, address=address)
            if cipher(raw) != plain:
                self.seq.stop()
                raise ValueError(f'Read-back of {address:#x} differs from the image; not jumping')
        self.log('verified', blocks=len(self.blocks))
        receipt['readback'] = 'equal'
        t0 = time.monotonic()
        try:
            echo = self.cmd(JUMP, address=WINDOW_BASE)
            receipt['jump'] = {'answered': True, 'echo': echo.hex(),
                               'ms': round((time.monotonic() - t0) * 1000)}
        except (OSError, ValueError) as exc:
            # Expected for an image that never returns or resets the chip.
            # Ambiguous by itself: only fresh UART output says what ran.
            receipt['jump'] = {'answered': False, 'error': str(exc),
                               'ms': round((time.monotonic() - t0) * 1000)}
        self.log('jumped', **receipt['jump'])
        return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='action', required=True)
    p = sub.add_parser('plan', help='print what a run would write and call; no device')
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    r = sub.add_parser('run', help='upload, verify and jump on the pinned dev kit')
    r.add_argument('--device', required=True, help='/dev/sgN of the dev kit in ROM mode')
    r.add_argument('--usb-path', required=True,
                   help='sysfs bus-port of the dev kit in ROM mode (tools/bench_targets.json)')
    r.add_argument('--devnum', help='USB devnum observed at enumeration')
    r.add_argument('--image', type=Path, required=True)
    r.add_argument('--sha256', required=True)
    r.add_argument('--out', type=Path, required=True, help='new directory for the log and receipt')
    args = ap.parse_args(argv)
    image = args.image.read_bytes()
    if args.action == 'plan':
        print(json.dumps(describe(image, args.sha256), indent=2))
        return 0
    admit(image, args.sha256)  # before creating anything or opening a device
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / 'commands.jsonl').open('x') as fp:
        def log(event, **fields):
            fp.write(json.dumps({'time': time.time(), 'event': event, **fields}) + '\n')
            fp.flush()
        runner = None
        try:
            runner = RamRunner(str(args.device), log, image, args.sha256,
                               usb_path=args.usb_path, devnum=args.devnum)
            receipt = runner.run()
            receipt.update(usb_path=args.usb_path, devnum=args.devnum, finished=time.time())
            (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            print(json.dumps(receipt), flush=True)
            return 0
        except Exception as exc:
            log('stopped', error=str(exc))
            print(f'Stopped: {exc}', flush=True)
            return 1
        finally:
            if runner is not None:
                runner.close()


if __name__ == '__main__':
    raise SystemExit(main())
