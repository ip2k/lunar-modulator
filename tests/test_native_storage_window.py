# SPDX-License-Identifier: MIT
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/native'))
from storage_window import plan, verify
from storage_backup import digest, PROFILES
from test_native_storage_backup import image

CASES = ['roundtrip', 'second-window', 'mismatch', 'baseline-pin', 'candidate-pin',
         'short', 'unaligned', 'before-gap', 'after-gap', 'boolean', 'occupied',
         'prefix', 'bank', 'key', 'forged']


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('case', CASES)
def test_window_proof(profile, case):
    raw = bytearray(image(profile))
    raw[0xfc000:0xff000] = b'\xff'*0x3000
    a = b = candidate = bytes(raw)
    start = 0xfc000
    if case == 'second-window': start = 0xfd000
    if case == 'mismatch': b = a[:-1]+bytes([a[-1]^1])
    if case == 'short': candidate = candidate[:-1]
    if case == 'unaligned': start += 1
    if case == 'before-gap': start = 0xfb000
    if case == 'after-gap': start = 0xfe000
    if case == 'boolean': start = True
    if case == 'occupied':
        raw[start] = 0
        a = b = candidate = bytes(raw)
    if case in ['prefix','bank','key']:
        off = {'prefix':0x1000,'bank':PROFILES[profile][0]+0x100,'key':0xff800}[case]
        raw[off] ^= 1
        candidate = bytes(raw)
    bp = '0'*64 if case == 'baseline-pin' else digest(a)
    cp = '0'*64 if case == 'candidate-pin' else digest(candidate)
    if case not in ['roundtrip','second-window','forged']:
        with pytest.raises(ValueError): plan(a,b,candidate,profile,bp,cp,start)
        return
    receipt = plan(a,b,candidate,profile,bp,cp,start)
    if case == 'forged':
        receipt['ownership_verified'] = True
        with pytest.raises(ValueError): verify(receipt,a,b,candidate,profile,bp,cp,start)
        return
    assert verify(receipt,a,b,candidate,profile,bp,cp,start) == receipt
    assert receipt['geometry_verified'] and receipt['protected_storage_preserved']
    assert not receipt['hardware_admitted'] and not receipt['ownership_verified']
    assert receipt['hardware_operations'] == 0
