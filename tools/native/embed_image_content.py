#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Emit constant native C data from integrity-checked builder inputs.

No compiler, linker or device access. Embedding does not admit firmware or
validate sequencer semantics. The controller must retain the expected digest.
"""
import argparse
import json
import re
from pathlib import Path

try:
    from .prepare_image_profile import sha
    from .verify_image_profile import load_prepared_profile
except ImportError:  # Script execution from tools/native.
    from prepare_image_profile import sha
    from verify_image_profile import load_prepared_profile

KINDS = {'project': 'FM1_STATE_PROJECT', 'set': 'FM1_STATE_SET'}

def display_title(asset, index):
    # Labels derive only from the admitted source basename, never a filesystem path.
    stem = Path(asset.get('source', '')).stem
    title = re.sub(r'[^A-Za-z0-9 _.-]', '', stem).strip(' ._-')[:20]
    return title or f'PROJECT {index + 1:02d}'
MAX_PACKED_FILE = 98304  # Existing FM1_STATE_BIN_MAX, not a larger file format.
MAX_PACKED_TOTAL = 1048576  # Entire physical FM1 flash; actual link cap is smaller.


def content_source(inputs, parent_indices=None, *, require_set_parents=False):
    if len(inputs.report['content']) != len(inputs.packed_content):
        raise ValueError('Content descriptors and payloads differ in count')
    if sum(map(len, inputs.packed_content)) > MAX_PACKED_TOTAL:
        raise ValueError('Packed content exceeds entire FM1 flash capacity')
    if parent_indices is None:
        parent_indices = [-1] * len(inputs.report['content'])
    if len(parent_indices) != len(inputs.report['content']):
        raise ValueError('Content parent bindings differ in count')
    lines = ['/* Generated builder input; firmware admission is still required. */',
             '#include "content_catalogue.h"', '#include "fm1_state.h"', '']
    entries = []
    for index, (asset, payload) in enumerate(zip(inputs.report['content'], inputs.packed_content)):
        if asset['kind'] not in KINDS:
            raise ValueError('Native content must be a project or set')
        if not 32 <= len(payload) <= MAX_PACKED_FILE:
            raise ValueError('Native packed file exceeds container bounds')
        symbol = f'lunar_content_{index:02d}'
        lines.append(f'static const uint8_t {symbol}[] = {{')
        for offset in range(0, len(payload), 16):
            lines.append('    ' + ','.join(f'0x{x:02x}' for x in payload[offset:offset + 16]) + ',')
        lines.extend(['};', ''])
        title = display_title(asset, index)
        parent = parent_indices[index]
        if type(parent) is not int or parent < -1 or parent >= len(inputs.report['content']):
            raise ValueError('Content parent binding is outside the catalogue')
        if asset['kind'] == 'set' and parent < 0 and require_set_parents:
            raise ValueError('Companion SET asset requires a trusted parent project binding')
        if asset['kind'] == 'project' and parent != -1:
            raise ValueError('PROJECT asset cannot have a parent binding')
        parent_value = 'UINT32_MAX' if parent < 0 else f'{parent}u'
        entries.append(f'    {{{symbol}, sizeof({symbol}), {KINDS[asset["kind"]]}, {json.dumps(title)}, {parent_value} }},')
    lines.append('const lunar_content_asset_t lunar_content_catalogue[] = {')
    lines.extend(entries or ['    {0, 0, 0, 0, UINT32_MAX},'])
    lines.extend(['};', f'const uint32_t lunar_content_count = {len(entries)}u;', ''])
    return '\n'.join(lines).encode('ascii')


def embed(directory, expected_sha256, out):
    inputs = load_prepared_profile(directory, expected_sha256)
    source = content_source(inputs)
    # Refusal precedes output creation. A fresh directory avoids stale acceptance.
    out.mkdir(parents=True, exist_ok=False)
    (out / 'content_catalogue.c').write_bytes(source)
    (out / 'fm1_modules.h').write_bytes(inputs.module_header)
    report = dict(version=1, prepared_sha256=expected_sha256,
                  source_sha256=sha(source), module_header_sha256=sha(inputs.module_header),
                  packed_content_bytes=sum(map(len, inputs.packed_content)),
                  asset_count=len(inputs.packed_content),
                  assets=[dict(packed=a['packed'], kind=a['kind'], bytes=len(p),
                               packed_sha256=sha(p))
                          for a, p in zip(inputs.report['content'], inputs.packed_content)],
                  installable=False, native_link_verified=False,
                  native_ram_verified=False, hardware_tested=False,
                  sequence_semantics_verified=False)
    (out / 'embedded.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = embed(args.directory, args.expected_sha256, args.out)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
