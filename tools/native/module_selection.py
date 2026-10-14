# SPDX-License-Identifier: MIT
"""Resolve native module choices through the existing Make catalogue.

Only literal comma-separated IDs cross this boundary. Make list files and
variable expansion are deliberately unavailable to externally supplied choices.
This generates metadata, not firmware, and performs no device I/O.
"""
import hashlib
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess


_MODULE_ID = re.compile(r'[a-z][a-z0-9-]*\Z')
_OBJECT_PATH = re.compile(r'[A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)*\.o\Z')
_MODULE_KINDS = {'sound', 'audio_fx', 'midi_fx', 'mod'}


def wavetable_namespaces(selected, flash_plaits=False):
    """Only the Macro engines and Shapes consume the compressed wave banks.

    With flash_plaits, retain the original immutable Plaits bank in XIP.
    Other Plaits-derived engines use scalar lookup tables retained in their
    resource object, not the large integrated wavetable bank.
    """
    selected = set(selected)
    return (['plaits'] if not flash_plaits and selected & {'macro', 'macro-heavy'} else []) + (
        ['braids'] if 'shapes' in selected else [])


def resolve_modules(root: Path, build: Path, specification: str):
    if specification != 'all':
        ids = specification.split(',')
        if (not ids or any(not _MODULE_ID.fullmatch(x) for x in ids)
                or len(ids) != len(set(ids))):
            raise ValueError('Modules must be unique literal comma-separated IDs')
    result = subprocess.run(
        ['make', '-s', '--no-print-directory', '-C', str(root / 'engines'),
         'BUILD=' + str(build), 'FM1_GPL_MODS=1',
         'FM1_MODULES=' + specification, 'print-modules'],
        capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Module catalogue rejected selection: ' + result.stderr.strip())
    lines = result.stdout.splitlines()
    trailer_name = 'all' if specification == 'all' else 'custom'
    if not lines or lines[-1].split() != ['list', trailer_name]:
        raise ValueError('Malformed module catalogue trailer')
    rows = []
    seen = set()
    for line in lines[:-1]:
        fields = line.split()
        if (len(fields) < 4 or not _MODULE_ID.fullmatch(fields[0])
                or fields[0] in seen or fields[1] not in _MODULE_KINDS
                or fields[2] not in ('0', '1')):
            raise ValueError('Malformed module catalogue output')
        objects = fields[3:]
        if any(not _OBJECT_PATH.fullmatch(obj)
               or '..' in PurePosixPath(obj).parts for obj in objects):
            raise ValueError('Malformed module catalogue object path')
        seen.add(fields[0])
        rows.append(dict(id=fields[0], kind=fields[1],
                         selected=fields[2] == '1', objects=objects))
    header = (build / 'gen/fm1_modules.h').read_bytes()
    selected = [r['id'] for r in rows if r['selected']]
    if not rows or not selected:
        raise ValueError('Empty module catalogue output')
    if specification != 'all' and set(selected) != set(specification.split(',')):
        raise ValueError('Module catalogue selection differs from requested IDs')
    return header, dict(specification=specification, selected=selected, catalogue=rows,
                        header_sha256=hashlib.sha256(header).hexdigest())
