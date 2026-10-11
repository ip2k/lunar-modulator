"""Offline fixed patch of the audited WL82 loader's configuration selector.

MIT. Protocol/cipher facts: kagaimiq jl-uboot-tool adb3f188 (MIT, Andrey
Grigoryev). No device opener, transport, flash command or generic memory write.
Vendor loader bytes remain private. This does not certify external initializer
effects or hardware readiness; the patched vendor listing needs separate review.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm1_ram_recovery import scramble_block
from fm1_uboot_read import LOADER_SHA, LOADER_SIZE, RAM, request

DECODED_SHA = 'db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e'
ZERO_BASE = 0x01C07C40
ZERO_SIZE = 64
# Offsets are relative to RAM=0x01C02000, not ELF or flash coordinates.
# Replace the selector prologue with a leaf return to uploaded zero padding (unchanged on the traced path).
# Disable both subsequent in-place configuration-decode calls; the parser's
# first record length at returned_pointer+34 stays zero and takes its exit.
PATCHES = (
    (0x84, bytes.fromhex('7804e297c8ff0097'), bytes.fromhex('c0ff407cc0018000')),
    (0x666, bytes.fromhex('bfeaddfc'), bytes(4)),
    (0x676, bytes.fromhex('bfead5fc'), bytes(4)),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def crypt_blocks(data):
    if len(data) != LOADER_SIZE:
        raise ValueError('Exact 47-block loader size required')
    return b''.join(scramble_block(data[i:i+512])
                    for i in range(0, LOADER_SIZE, 512))


@dataclass(frozen=True)
class PreparedLoader:
    encrypted: bytes
    decoded: bytes
    report_json: bytes

    def upload_requests(self):
        """Fixed ROM upload inventory; returned bytes do not execute anything."""
        return tuple(request(0xFB06, 'rom', address=RAM+i,
                             payload=self.encrypted[i:i+512])
                     for i in range(0, LOADER_SIZE, 512))


def prepare_loader(encrypted):
    """Accept only the pinned original; emit exactly the reviewed patch proposal."""
    encrypted = bytes(encrypted)
    if len(encrypted) != LOADER_SIZE or digest(encrypted) != LOADER_SHA:
        raise ValueError('Only the exact audited encrypted loader is supported')
    original = crypt_blocks(encrypted)
    if digest(original) != DECODED_SHA:
        raise ValueError('Independent decoded-loader pin mismatch')
    zero_offset = ZERO_BASE-RAM
    if original[zero_offset:zero_offset+ZERO_SIZE] != bytes(ZERO_SIZE):
        raise ValueError('Image-owned zero padding changed')
    patched = bytearray(original)
    allowed = set()
    for offset, before, after in PATCHES:
        if len(before) != len(after) or original[offset:offset+len(before)] != before:
            raise ValueError('Exact instruction premise changed')
        allowed.update(range(offset, offset+len(before)))
        patched[offset:offset+len(after)] = after
    decoded = bytes(patched)
    if any(a != b and i not in allowed
           for i, (a, b) in enumerate(zip(original, decoded))):
        raise ValueError('Unexpected byte change outside the three fixed patches')
    if decoded[zero_offset:zero_offset+ZERO_SIZE] != bytes(ZERO_SIZE):
        raise ValueError('Configuration zero data changed')
    output = crypt_blocks(decoded)
    if crypt_blocks(output) != decoded:
        raise ValueError('Per-block cipher roundtrip failed')
    upload_inventory = []
    for offset in range(0, LOADER_SIZE, 512):
        cdb, payload, read_size = request(
            0xFB06, 'rom', address=RAM+offset, payload=output[offset:offset+512])
        upload_inventory.append({
            'index': offset//512, 'address': RAM+offset, 'bytes': len(payload),
            'cdb_sha256': digest(cdb), 'payload_sha256': digest(payload),
            'read_size': read_size,
        })
    report = {
        'schema': 1, 'scope': 'offline fixed WL82 loader configuration proposal',
        'original_encrypted_sha256': digest(encrypted),
        'original_decoded_sha256': digest(original),
        'patched_encrypted_sha256': digest(output),
        'patched_decoded_sha256': digest(decoded),
        'bytes': LOADER_SIZE, 'base': RAM, 'block_size': 512, 'blocks': 47,
        'zero_data_range': [ZERO_BASE, ZERO_BASE+ZERO_SIZE],
        'upload_inventory': upload_inventory,
        'patches': [{'address': RAM+o, 'before_hex': b.hex(), 'after_hex': a.hex()}
                    for o, b, a in PATCHES],
        'direct_traced_selector_reads_retained_windows': False,
        'extra_rom_uploads': 0,
        'intended_spi_mode': 2,
        'branch_premises': [
            'selector is a leaf returning image-owned zero padding',
            'both selected-window decode calls are NOP instructions',
            'field parser reads zero length at pointer+34 and returns absence',
            'absence selects original default dual-mode branch',
        ],
        'hardware_ready': False,
        'patched_vendor_listing_independently_reviewed': False,
        'external_initializer_effects_verified': False,
        'rom_cipher_runtime_verified_by_this_tool': False,
        'physical_execution_verified': False,
    }
    return PreparedLoader(output, decoded,
                          (json.dumps(report, sort_keys=True, indent=2)+'\n').encode())


def emit_private(loader_path, output_directory):
    """New private offline artifact directory; no vendor bytes printed or committed."""
    prepared = prepare_loader(Path(loader_path).read_bytes())
    directory = Path(output_directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, data in (('loader.patched.encrypted.bin', prepared.encrypted),
                       ('loader.patched.decoded.bin', prepared.decoded),
                       ('profile.json', prepared.report_json)):
        fd = os.open(directory/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    fd = os.open(directory.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return json.loads(prepared.report_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    report = emit_private(args.loader, args.output_directory)
    print(json.dumps({key: report[key] for key in
                      ('patched_encrypted_sha256', 'patched_decoded_sha256',
                       'hardware_ready')}, sort_keys=True))


if __name__ == '__main__':
    main()
