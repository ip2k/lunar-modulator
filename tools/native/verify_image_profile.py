# SPDX-License-Identifier: MIT
"""Load prepared build inputs against a digest retained by the build controller.

No subprocesses or device access. Return the checked bytes for the caller to
consume, avoiding a verify-then-reopen gap. This is not firmware admission.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re

from prepare_image_profile import bounded_read, sha, unique_object


@dataclass(frozen=True)
class PreparedInputs:
    report: dict
    module_header: bytes
    packed_content: tuple


def load_prepared_profile(directory: Path, expected_sha256: str):
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected manifest digest must be lowercase SHA256')
    directory = directory.resolve()

    def read(name, limit):
        path = directory / name
        # Every admitted input is an ordinary file in this snapshot directory.
        if path.is_symlink() or not path.is_file():
            raise ValueError('Prepared input must be a regular non-symlink file: ' + name)
        return bounded_read(path, limit)

    manifest = read('profile.json', 1048576)
    if sha(manifest) != expected_sha256:
        raise ValueError('Prepared manifest digest mismatch')
    report = json.loads(manifest, object_pairs_hook=unique_object)
    if (not isinstance(report, dict) or type(report.get('version')) is not int
            or report['version'] != 1):
        raise ValueError('Unsupported prepared profile')
    for key in ('installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'):
        if report.get(key) is not False:
            raise ValueError('Build input must not claim firmware admission: ' + key)
    header = read('fm1_modules.h', 65536)
    if sha(header) != report['module_selection']['header_sha256']:
        raise ValueError('Prepared module header digest mismatch')
    assets = report['content']
    if not isinstance(assets, list) or len(assets) > 64:
        raise ValueError('Prepared content exceeds asset bound')
    payloads = []
    for index, asset in enumerate(assets):
        name = f'content-{index:02d}.bin'
        if asset['packed'] != name:
            raise ValueError('Noncanonical prepared asset name')
        source = read(f'content-{index:02d}.source', 1048576)
        payload = read(name, 2097152)
        if sha(source) != asset['source_sha256']:
            raise ValueError('Prepared content source digest mismatch')
        if sha(payload) != asset['packed_sha256'] or len(payload) != asset['bytes']:
            raise ValueError('Prepared packed content digest or length mismatch')
        if asset['sequence_semantics_verified'] is not False:
            raise ValueError('Prepared content must not claim sequence acceptance')
        if set(asset['dependencies']) - set(report['module_selection']['selected']):
            raise ValueError('Prepared content needs omitted modules')
        payloads.append(payload)
    if sum(map(len, payloads)) != report['packed_content_bytes']:
        raise ValueError('Prepared content total mismatch')
    return PreparedInputs(report, header, tuple(payloads))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    try:
        inputs = load_prepared_profile(args.directory, args.expected_sha256)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(dict(build_inputs_verified=True, installable=False,
                          packed_content_bytes=sum(map(len, inputs.packed_content)))))


if __name__ == '__main__':
    main()
