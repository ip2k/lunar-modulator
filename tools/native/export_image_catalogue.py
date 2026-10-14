#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export native builder choices and the production default; no device I/O.

The Make catalogue owns module IDs and kinds. Test modules remain available to
developer builds, but are not choices in the production image builder. This
document describes requests, not approved or installable firmware artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from module_selection import resolve_modules
from prepare_image_profile import GROUPS

ROOT = Path(__file__).resolve().parents[2]


def export_catalogue(root: Path, build: Path):
    catalogue_path = root / 'engines/modules/catalogue.mk'
    before = catalogue_path.read_bytes()
    _, all_modules = resolve_modules(root, build / 'all', 'all')
    groups = {group: [] for group in GROUPS}
    by_kind = {kind: group for group, kind in GROUPS.items()}
    seen = set()
    for row in all_modules['catalogue']:
        module = row['id']
        if module in seen or row['kind'] not in by_kind:
            raise ValueError('Duplicate module or unsupported catalogue kind')
        seen.add(module)
        if not module.startswith('test-'):
            groups[by_kind[row['kind']]].append(module)
    if any(not ids for ids in groups.values()):
        raise ValueError('Production catalogue has an empty module group')
    profile = dict(version=1, **groups, content=[])
    selected = [module for ids in groups.values() for module in ids]
    _, default = resolve_modules(root, build / 'default', ','.join(selected))
    if set(default['selected']) != set(selected):
        raise ValueError('Production default does not match requested catalogue')
    if catalogue_path.read_bytes() != before:
        raise ValueError('Module catalogue changed during export')
    return dict(version=1, groups=groups, default_profile=profile,
                catalogue_sha256=hashlib.sha256(before).hexdigest(),
                default_header_sha256=default['header_sha256'],
                installable=False, native_link_verified=False,
                native_ram_verified=False, hardware_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='lunar-image-catalogue-') as scratch:
            report = export_catalogue(ROOT, Path(scratch))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
