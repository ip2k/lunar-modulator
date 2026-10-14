#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare canonical modules and packed songs/sets; no link or device I/O.

Input: {"version": 1, "engines": [...], "effects": [...], "midi": [...],
        "modulation": [...], "content": ["relative/song.lunar", ...]}.
The trusted caller supplies the existing fm1-state executable. Prepared bundles
are build inputs, never admitted firmware or evidence of native RAM fit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from module_selection import resolve_modules

ROOT = Path(__file__).resolve().parents[2]
GROUPS = dict(engines='sound', effects='audio_fx', midi='midi_fx', modulation='mod')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded_read(path, limit):
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Input exceeds byte bound: ' + str(path))
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate profile key: ' + key)
        result[key] = value
    return result


def command(tool, *args):
    result = subprocess.run([str(tool), *map(str, args)], capture_output=True)
    if result.returncode:
        raise ValueError('State tool rejected content: ' + result.stderr.decode(errors='replace'))
    return result.stdout


def prepare(profile: Path, tool: Path, out: Path, *, recompress_content=False):
    if type(recompress_content) is not bool:
        raise ValueError('Recompression option must be boolean')
    raw_profile = bounded_read(profile, 65536)
    doc = json.loads(raw_profile, object_pairs_hook=unique_object)
    tool_hash = sha(tool.read_bytes())
    if (not isinstance(doc, dict) or type(doc.get('version')) is not int
            or doc['version'] != 1 or set(doc) - {'version', 'content', *GROUPS}):
        raise ValueError('Unsupported image profile')
    choices = []
    for group in GROUPS:
        values = doc.get(group, [])
        if (not isinstance(values, list) or len(values) > 128
                or any(not isinstance(x, str) for x in values)):
            raise ValueError('Invalid module group: ' + group)
        choices.extend(values)
    content = doc.get('content', [])
    if (not isinstance(content, list) or len(content) > 64
            or any(not isinstance(x, str) or not x for x in content)
            or len(set(content)) != len(content)):
        raise ValueError('Content must be at most 64 unique relative paths')
    # Require a new directory, so a refusal cannot leave an old accepted manifest.
    out.mkdir(parents=True, exist_ok=False)
    header, selection = resolve_modules(ROOT, out / 'modules', ','.join(choices))
    kinds = {r['id']: r['kind'] for r in selection['catalogue']}
    for group, kind in GROUPS.items():
        if any(kinds.get(x) != kind for x in doc.get(group, [])):
            raise ValueError('Module in wrong group: ' + group)
    selected = set(selection['selected'])
    if not doc.get('engines'):
        raise ValueError('Profile needs a sound engine')
    (out / 'fm1_modules.h').write_bytes(header)
    assets, seen_paths = [], set()
    base = profile.resolve().parent
    for index, relative in enumerate(content):
        path = (base / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(base) or path in seen_paths:
            raise ValueError('Content must be unique and remain within profile directory')
        seen_paths.add(path)
        data = bounded_read(path, 1048576)
        # Snapshot before invoking the tool; hashes describe the bytes packed.
        source = out / f'content-{index:02d}.source'
        source.write_bytes(data)
        packed = out / f'content-{index:02d}.bin'
        if data.startswith(b'\x89Lunar\r\n'):
            # Sets have no JSON form: retain binary inputs, then validate their
            # bounds and CRCs through the same records reader used below.
            packed.write_bytes(data)
        else:
            operation = 'from-movy1' if data.startswith(b'movy1\n') else 'pack'
            command(tool, operation, source, '-o', packed)
        record_bytes = command(tool, 'records', packed)
        compression = None
        if recompress_content:
            from recompress_project import recompress
            from tools.lunar_state import Refused
            from zlib import error as ZlibError
            try:
                payload, compression = recompress(packed.read_bytes())
            except (Refused, ZlibError) as error:
                raise ValueError('Content recompression refused: ' + str(error)) from error
            packed.write_bytes(payload)
            # The target reader, not the host encoder alone, decides whether
            # the new encoding preserves the complete native record stream.
            if command(tool, 'records', packed) != record_bytes:
                raise ValueError('Native records changed after recompression')
        records = [json.loads(line) for line in record_bytes.splitlines()]
        if not records or records[0].get('rec') != 'head':
            raise ValueError('Missing packed content header')
        if records[0].get('kind') not in ('project', 'set'):
            raise ValueError('Image content must be a project/song or set')
        dependencies = sorted({r.get('engine', '') if r.get('rec') == 'unit'
                               else r.get('kind', '') for r in records
                               if r.get('rec') in ('unit', 'module')} - {''})
        missing = set(dependencies) - selected
        if missing:
            raise ValueError('Content needs omitted modules: ' + ','.join(sorted(missing)))
        payload = packed.read_bytes()
        assets.append(dict(source=relative, source_sha256=sha(data),
                           packed=packed.name, packed_sha256=sha(payload),
                           bytes=len(payload), kind=records[0]['kind'], dependencies=dependencies,
                           sequence_semantics_verified=False,
                           dependency_scan_complete=records[0]['kind'] == 'project'))
        if compression is not None:
            assets[-1]['compression'] = dict(encoder='host-zlib-raw-4k', **compression)
    if sha(tool.read_bytes()) != tool_hash:
        raise ValueError('State tool changed during preparation')
    report = dict(version=1, profile_sha256=sha(raw_profile),
                  state_tool_sha256=tool_hash, module_selection=selection,
                  content=assets, packed_content_bytes=sum(a['bytes'] for a in assets),
                  installable=False, native_link_verified=False, native_ram_verified=False,
                  hardware_tested=False)
    # Written only after every input succeeds; consumers require this manifest.
    (out / 'profile.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state-tool', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--recompress-content', action='store_true',
                        help='Recompress chunks and verify exact native records before linking')
    args = parser.parse_args()
    try:
        report = prepare(args.profile.resolve(), args.state_tool.resolve(), args.out.resolve(),
                         recompress_content=args.recompress_content)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
