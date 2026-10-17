"""Synthetic 092 D7000 fixture and independent Python model oracle; no vendor bytes."""
import json
import pathlib
import struct
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'tools/jieli'), str(root / 'tests')]
from inspect_fwsc import crc16, header_decode, sfc_decode
from model_092_app_replacement import _flash_parse, EXPECTED_RESERVED

flash = bytearray(0xd7000)
def jlfs(name, address, size, flags, terminal, data=None):
    body = struct.pack('<HIIBBH16s', crc16(data) if data is not None else 65535,
                       address, size, flags, 0, terminal, name.encode())
    return struct.pack('<H', crc16(body)) + body

flash[:32] = struct.pack('<H', crc16(bytes(30))) + bytes(30)
blob = bytes([100] * 16) + bytes(100 ^ (0 if 0x980f & (1 << i) else 255) for i in range(16))
config = blob + struct.pack('<H', crc16(blob)) + bytes(665)
flash[0x38d0:0x38d0 + 699] = config
bank = bytes(14368)
bank_head = struct.pack('<HHIIH', 1, len(bank), 0x01c02000, 16, crc16(bank))
spl = bank_head + struct.pack('<H', crc16(bank_head)) + bank
flash[0xa0:0x38d0] = spl
flash[0x20:0xa0] = (jlfs('uboot.boot', 0xa0, len(spl), 0, 0, spl)
    + jlfs('isd_config.ini', 0x38d0, 699, 2, 0, config)
    + jlfs('app_dir_head', 0x4000, 0xffffffff, 0x81, 0)
    + jlfs('key_mac', 0xff000, 0x1000, 0x12, 0xffff))
app = b'SYNTHETIC APP'
tool = bytes(383)
area_size = 0x120 + len(app) + len(tool)
flash[0x4120:0x4120 + len(app)] = app
flash[0x4120 + len(app):0x4000 + area_size] = tool
children = [jlfs('app.bin', 0x120, len(app), 0x82, 0, app),
            jlfs('cfg_tool.bin', 0x120 + len(app), len(tool), 0x82, 0, tool)]
for i, (name, (address, size, flags)) in enumerate(EXPECTED_RESERVED.items()):
    children.append(jlfs(name, address, size, flags, int(i == 3)))
flash[0x4020:0x40e0] = b''.join(children)
flash[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, area_size, 0x83, 0, flash[0x4020:0x4000 + area_size])
cfg_offset = 0x4000 + area_size
cfg = jlfs('cfg', 32, 2937, 0x83, 1, bytes(2905)) + bytes(2905)
flash[cfg_offset:cfg_offset + len(cfg)] = cfg
# Mutations repair enclosing CRCs to reach nested checks.
mode = sys.argv[1] if len(sys.argv) > 1 else 'valid'
if mode == 'overlap':
    flash[0x4040:0x4060] = jlfs('cfg_tool.bin', 0x120, 383, 0x82, 0, tool)
elif mode == 'reserved':
    flash[0x4060:0x4080] = jlfs('VM', 0xd9001, 0x10000, 0x12, 0)
elif mode == 'length':
    flash[0x4020:0x4040] = jlfs('app.bin', 0x120, 0xffffffff, 0x82, 0, app)
elif mode == 'data':
    flash[0x4120] ^= 1
elif mode == 'header':
    flash[0x4020] ^= 1
if mode != 'valid':
    flash[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, area_size, 0x83, 0, flash[0x4020:0x4000 + area_size])
raw = bytearray(flash)
for offset in (0, 32, 64, 96, 128):
    raw[offset:offset + 32] = header_decode(flash[offset:offset + 32])
raw[0xa0:0xb0] = header_decode(flash[0xa0:0xb0])
raw[0xb0:0x38d0] = header_decode(flash[0xb0:0x38d0])
raw[0x4000:] = sfc_decode(flash[0x4000:], 0)
if mode == 'top-header':
    raw[32] ^= 1
elif mode == 'config-crc':
    raw[0x38d0 + 100] ^= 1
elif mode == 'spl-crc':
    raw[0xb0 + 100] ^= 1
elif mode == 'cfg-crc':
    raw[cfg_offset + 100] ^= 1
elif mode == 'truncated':
    raw = raw[:-32]
elif mode == 'oversized':
    raw.extend(bytes(32))
elif mode == 'decryption':
    raw[0x4000:] = sfc_decode(flash[0x4000:], 32)
# Verify valid bytes against independent Python parser with synthetic references.
if mode == 'valid':
    with tempfile.TemporaryDirectory() as directory:
        ref = pathlib.Path(directory)
        (ref / 'top').mkdir(); (ref / 'files').mkdir()
        for name, data in [('top/uboot.boot', flash[0xa0:0x38d0]), ('top/isd_config.ini', flash[0x38d0:0x38d0+699]),
                           ('files/app.bin', app), ('files/cfg_tool.bin', tool), ('files/cfg', cfg)]:
            (ref / name).write_bytes(data)
        parsed = _flash_parse(raw, ref)
        assert parsed['cfg_end'] == cfg_offset + len(cfg)
sys.stdout.buffer.write(raw)
