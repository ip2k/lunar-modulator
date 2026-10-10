#!/usr/bin/env python3
"""MIT. Inspect stock V15 identity/trailer evidence offline; JSON only.

Matching observed fields is not proof of device acceptance. No version override,
firmware output, transport or device access is provided.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from inspect_fwsc import header_decode, inspect
from inspect_stock_flash import inspect_nested


STOCK_TAIL_SHA256 = '79d4bbc325be8b2f49492a9e8bf712e3cfe4e7c55e874dced1445ed65616843b'


def _fields(raw, outer, app):
    identity = outer['identity']
    # A substring or multiple literals does not establish one app identity.
    identities = list(re.finditer(rb'FM-1_[0-9]{3}\x00', app))
    if len(identities) != 1 or identities[0].group()[:-1].decode('ascii') != identity:
        raise ValueError('expected exactly one matching NUL-terminated app identity')
    image = b''.join(raw[i:i + 47] for i in range(0, 960, 48)) + raw[960:]
    if outer['unknown_header_fields'] != [4, 512]:
        raise ValueError('observed stock metadata profile differs')
    tail = next(item for item in outer['entries'] if item['name'] == 'tail.bin')
    payload = image[tail['offset']:tail['offset'] + tail['bytes']]
    if (tail['type'] != 255 or len(payload) != 64
            or hashlib.sha256(payload).hexdigest() != STOCK_TAIL_SHA256):
        raise ValueError('opaque stock trailer bytes differ')
    record = header_decode(image[64 + tail['index'] * 80:144 + tail['index'] * 80])
    if any(record[6:8]) or tail['allocated_bytes'] != 64 or any(record[20:64]):
        raise ValueError('observed stock trailer record differs')
    return dict(status='stock-version-trailer-evidence-inspected', packaging_ready=False,
                identity=identity, decimal_version=int(identity.rsplit('_', 1)[1]),
                app_identity_offset=identities[0].start(),
                app_identity_matches_markers=True,
                tail_sha256=STOCK_TAIL_SHA256, tail_bytes=64,
                tail_semantics='opaque; preserve exact bytes',
                trailer_record_profile_verified=True,
                metadata_profile_verified=True,
                device_acceptance='unverified', binary_emitted=False,
                pending=['same-version refusal is not proof that any new version is accepted',
                         'V13 reported cfg/OTA checks are not established for V15 or FM-1_092',
                         'inert diagnostic lacks an app identity/update service and observable startup',
                         'review exact candidate/write range and fresh backups before a device experiment'])


def inspect_contract(raw, stock):
    # Bind app and cfg/SPL/OTA before using extracted app identity as evidence.
    nested = inspect_nested(raw, stock)
    outer = inspect(raw, stock)
    result = _fields(raw, outer, (Path(stock) / 'files/app.bin').read_bytes())
    result['nested_stock_binding'] = nested['status']
    result['sha256'] = outer['sha256']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fwsc', type=Path)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--json', type=Path, required=True, help='new report; refuses overwrite')
    args = parser.parse_args()
    try:
        result = inspect_contract(args.fwsc.read_bytes(), args.stock)
        with args.json.open('x') as output:
            json.dump(result, output, indent=2)
            output.write('\n')
    except (OSError, ValueError, KeyError, StopIteration, UnicodeError) as exc:
        parser.exit(1, f'inspect_version_contract: {exc}\n')
    print(f"{result['identity']}: identity/trailer profile checked; device acceptance unverified")


if __name__ == '__main__':
    main()
