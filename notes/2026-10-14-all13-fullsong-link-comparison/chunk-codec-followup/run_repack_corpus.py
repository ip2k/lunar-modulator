#!/usr/bin/env python3
"""Repack measured corpora and compare canonical Python/C reader records."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib

sys.path.insert(0, '/helper')
from recompress_project import recompress
from tools import lunar_state as ls

OUT = Path('/out')
RESULT = {
    'python': sys.version,
    'zlib_compile': zlib.ZLIB_VERSION,
    'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION,
    'inputs': {},
    'native_reader_equal': {},
}

for name, source in (('afterglow', '/song.lunarb'), ('dense', '/dense.lunarb')):
    data = Path(source).read_bytes()
    packed, receipt = recompress(data)
    output = OUT / (name + '.lunarb')
    output.write_bytes(packed)
    records, _ = ls.read_bin(packed)
    python_records = ls.records_text(records).encode()
    c_records = subprocess.run(
        ['/native/fm1-state', 'records', str(output)],
        check=True, capture_output=True).stdout
    equal = python_records == c_records
    RESULT['inputs'][name] = receipt
    RESULT['native_reader_equal'][name] = equal
    if not equal:
        raise SystemExit('canonical native reader mismatch: ' + name)
    RESULT['native_records_sha256_' + name] = hashlib.sha256(c_records).hexdigest()

(OUT / 'repack-receipt.json').write_text(json.dumps(RESULT, indent=2) + '\n')
print(json.dumps(RESULT, indent=2))
