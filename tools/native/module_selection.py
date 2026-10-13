# SPDX-License-Identifier: MIT
"""Resolve native module choices through the existing Make catalogue.

Only literal comma-separated IDs cross this boundary. Make list files and
variable expansion are deliberately unavailable to externally supplied choices.
This generates metadata, not firmware, and performs no device I/O.
"""
import hashlib
from pathlib import Path
import re
import subprocess


def wavetable_namespaces(selected):
    """Only the Macro engines and Shapes consume the compressed wave banks.

    Other Plaits-derived engines use scalar lookup tables retained in their
    resource object, not the large integrated wavetable bank.
    """
    selected = set(selected)
    return (['plaits'] if selected & {'macro', 'macro-heavy'} else []) + (
        ['braids'] if 'shapes' in selected else [])


def resolve_modules(root: Path, build: Path, specification: str):
    if specification != 'all':
        ids = specification.split(',')
        if (not ids or any(not re.fullmatch(r'[a-z][a-z0-9-]*', x) for x in ids)
                or len(ids) != len(set(ids))):
            raise ValueError('Modules must be unique literal comma-separated IDs')
    result = subprocess.run(
        ['make', '-s', '--no-print-directory', '-C', str(root / 'engines'),
         'BUILD=' + str(build), 'FM1_GPL_MODS=1',
         'FM1_MODULES=' + specification, 'print-modules'],
        capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Module catalogue rejected selection: ' + result.stderr.strip())
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and fields[0] != 'list':
            if len(fields) < 4 or fields[2] not in ('0', '1'):
                raise ValueError('Malformed module catalogue output')
            rows.append(dict(id=fields[0], kind=fields[1],
                             selected=fields[2] == '1', objects=fields[3:]))
    header = (build / 'gen/fm1_modules.h').read_bytes()
    selected = [r['id'] for r in rows if r['selected']]
    if not rows or not selected:
        raise ValueError('Empty module catalogue output')
    return header, dict(specification=specification, selected=selected, catalogue=rows,
                        header_sha256=hashlib.sha256(header).hexdigest())
