#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage selected, hash-checked demo projects into a prepare-image profile.

The caller supplies project records from the trusted image catalogue and a
module-only profile. Repository source paths are accepted only when they match
the fixed preload registry; generated content paths are relative to the staged
profile. This stages build inputs only and performs no packing or device I/O.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil

from export_image_catalogue import PRELOAD_PROJECTS, PRELOAD_SETS
from prepare_image_profile import GROUPS


_PROJECT_ID = re.compile(r'[a-z][a-z0-9-]*\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_MAX_SOURCE_BYTES = 1048576


def _validate_module_profile(module_profile):
    if (not isinstance(module_profile, dict)
            or type(module_profile.get('version')) is not int
            or module_profile['version'] != 1
            or set(module_profile) != {'version', *GROUPS}):
        raise ValueError('Expected a version-1 module-only profile')
    profile = {'version': 1}
    for group in GROUPS:
        values = module_profile[group]
        if (not isinstance(values, list) or len(values) > 128
                or any(not isinstance(value, str) or not value for value in values)):
            raise ValueError('Invalid module group: ' + group)
        profile[group] = list(values)
    return profile


def _trusted_project_records(projects):
    if not isinstance(projects, list):
        raise ValueError('Catalogue projects must be a list')
    registered = {spec['id']: spec for spec in PRELOAD_PROJECTS}
    records = {}
    for record in projects:
        if not isinstance(record, dict):
            raise ValueError('Invalid project catalogue record')
        project_id = record.get('id')
        if (not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id)
                or project_id not in registered or project_id in records):
            raise ValueError('Unknown or duplicate catalogue project ID')
        spec = registered[project_id]
        # Do not let a request-provided catalogue redirect reads elsewhere in
        # the repository, even if the target would otherwise resolve in-root.
        if record.get('source_path') != spec['source_path']:
            raise ValueError('Catalogue source path differs from fixed preload registry')
        digest = record.get('source_sha256')
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError('Invalid catalogue source SHA-256')
        if record.get('title') != spec['title']:
            raise ValueError('Catalogue title differs from fixed preload registry')
        records[project_id] = record
    return records


def _trusted_set_records(sets):
    if not isinstance(sets, list):
        raise ValueError('Catalogue sets must be a list')
    registered = {spec['id']: spec for spec in PRELOAD_SETS}
    records = {}
    for record in sets:
        if not isinstance(record, dict):
            raise ValueError('Invalid set catalogue record')
        set_id = record.get('id')
        if (not isinstance(set_id, str) or not _PROJECT_ID.fullmatch(set_id)
                or set_id not in registered or set_id in records):
            raise ValueError('Unknown or duplicate catalogue set ID')
        if (record.get('parent_project_id') != registered[set_id]['parent_project_id']
                or record.get('dependency_scan_complete') is not False
                or record.get('source_dependency_scan_complete') is not False):
            raise ValueError('Set dependency metadata differs from fixed registry')
        records[set_id] = record
    return records


def _read_trusted_set(root, record, project_records, project_snapshots):
    parent_id = record['parent_project_id']
    parent_record = project_records.get(parent_id)
    if parent_record is None or parent_id not in project_snapshots:
        raise ValueError('Companion SET parent must be among selected projects')
    if (record.get('source_path') != parent_record.get('source_path')
            or record.get('source_sha256') != parent_record.get('source_sha256')):
        raise ValueError('Companion SET source identity differs from trusted parent project')
    raw = project_snapshots[parent_id]
    if hashlib.sha256(raw).hexdigest() != parent_record['source_sha256']:
        raise ValueError('Companion SET parent source digest changed')
    try:
        project = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid companion SET parent source') from error
    lines = project.get('set')
    if (not isinstance(lines, list) or not lines or lines[0] != 'movy1'
            or any(not isinstance(line, str) or '\n' in line or '\r' in line for line in lines)):
        raise ValueError('Companion SET is not a bounded movy1 line sequence')
    payload = ('\n'.join(lines) + '\n').encode('utf-8')
    if hashlib.sha256(payload).hexdigest() != record.get('content_sha256'):
        raise ValueError('Companion SET content digest differs from trusted catalogue')
    return payload


def _read_trusted_source(root, record):
    relative = PurePosixPath(record['source_path'])
    if relative.is_absolute() or not relative.parts or any(part in ('', '.', '..') for part in relative.parts):
        raise ValueError('Unsafe catalogue source path')
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError('Preload source path contains a symlink')
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError('Preload source escapes repository root')
    if not resolved.is_file():
        raise ValueError('Preload source is not a regular file')
    with resolved.open('rb') as stream:
        payload = stream.read(_MAX_SOURCE_BYTES + 1)
    if len(payload) > _MAX_SOURCE_BYTES:
        raise ValueError('Preload source exceeds byte bound')
    if hashlib.sha256(payload).hexdigest() != record['source_sha256']:
        raise ValueError('Preload source SHA-256 differs from catalogue')
    return payload


def stage_profile(repository_root: Path, module_profile: dict, projects: list,
                  project_ids: list, output_dir: Path, startup_index: int = 0,
                  sets: list | None = None, set_ids: list | None = None):
    """Stage a fresh prepare_image_profile input directory.

    ``projects`` must be the server-side ``projects`` array from the current
    exported catalogue, not request-supplied metadata. ``startup_index`` refers
    to the ordered ``project_ids`` list and is retained in ``selection.json``;
    the prepare-image schema intentionally receives only module groups/content.
    """
    root = Path(repository_root).resolve(strict=True)
    if not isinstance(project_ids, list) or not project_ids:
        raise ValueError('Select at least one preload project')
    if (any(not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id)
            for project_id in project_ids)
            or len(project_ids) != len(set(project_ids))):
        raise ValueError('Project selections must be unique literal IDs')
    if type(startup_index) is not int or not 0 <= startup_index < len(project_ids):
        raise ValueError('Startup index must identify a selected project')

    module = _validate_module_profile(module_profile)
    records = _trusted_project_records(projects)
    set_ids = [] if set_ids is None else set_ids
    if (not isinstance(set_ids, list) or len(set_ids) > 8
            or any(not isinstance(set_id, str) or not _PROJECT_ID.fullmatch(set_id) for set_id in set_ids)
            or len(set_ids) != len(set(set_ids))):
        raise ValueError('Set selections must be unique literal IDs')
    set_records = _trusted_set_records([] if sets is None else sets)
    if any(project_id not in records for project_id in project_ids):
        raise ValueError('Unknown selected preload project ID')

    # Read and verify all source snapshots before creating output, so catalogue
    # drift or a symlink cannot leave a partial accepted profile behind.
    snapshots = {}
    for project_id in project_ids:
        snapshots[project_id] = _read_trusted_source(root, records[project_id])
    if any(set_id not in set_records for set_id in set_ids):
        raise ValueError('Unknown selected companion SET ID')
    if set_ids and any(set_records[set_id]['parent_project_id'] != project_ids[startup_index]
                       for set_id in set_ids):
        raise ValueError('Companion SET parent must be the selected startup project')
    set_snapshots = {set_id: _read_trusted_set(root, set_records[set_id], records, snapshots)
                     for set_id in set_ids}

    requested = Path(output_dir)
    if requested.name in ('', '.', '..'):
        raise ValueError('Output must name a new directory')
    parent = requested.parent.resolve(strict=True)
    output = parent / requested.name
    if output.exists() or output.is_symlink():
        raise FileExistsError('Output directory already exists: ' + str(output))

    project_paths = [f'projects/{project_id}.lunar' for project_id in project_ids]
    set_paths = [f'sets/{set_id}.movy1' for set_id in set_ids]
    content_paths = project_paths + set_paths
    profile = dict(module, content=content_paths)
    selection = {
        'version': 1,
        'status': 'staged-not-prepared',
        'project_ids': list(project_ids),
        'set_ids': list(set_ids),
        'startup_index': startup_index,
        'startup_project_id': project_ids[startup_index],
        'sources': ([
            {'kind': 'project', 'id': project_id, 'source_path': records[project_id]['source_path'],
             'source_sha256': records[project_id]['source_sha256'],
             'staged_path': content_path}
            for project_id, content_path in zip(project_ids, project_paths)
        ] + [
            {'kind': 'set', 'id': set_id, 'parent_project_id': set_records[set_id]['parent_project_id'],
             'source_path': set_records[set_id]['source_path'],
             'source_sha256': set_records[set_id]['content_sha256'],
             'staged_path': content_path, 'dependency_scan_complete': False}
            for set_id, content_path in zip(set_ids, set_paths)
        ]),
    }

    output.mkdir(exist_ok=False)
    try:
        projects_dir = output / 'projects'
        projects_dir.mkdir()
        for project_id, content_path in zip(project_ids, project_paths):
            (output / content_path).write_bytes(snapshots[project_id])
        if set_ids:
            (output / 'sets').mkdir()
        for set_id, content_path in zip(set_ids, set_paths):
            (output / content_path).write_bytes(set_snapshots[set_id])
        (output / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
        # Consumers treat this file as the accepted profile input. Write it
        # last; on any failure, remove the whole directory before re-raising.
        (output / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {'profile_path': output / 'profile.json',
            'selection_path': output / 'selection.json',
            'project_ids': list(project_ids), 'startup_index': startup_index,
            'startup_project_id': project_ids[startup_index],
            'set_ids': list(set_ids), 'selected_content': selection['sources']}
