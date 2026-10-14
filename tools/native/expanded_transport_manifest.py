#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind an offline expanded raw candidate to its app and preload receipts.

This emits review evidence only. It does not create FWSC, open a device, or
authorize a write. The ordered sector list is suitable for a later reviewed
transport adapter, not a command stream.
"""
import hashlib
import json
import os

import expanded_flash_profile as expanded
import raw_flash_profile as raw


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _digest_field(value, field):
    digest = value.get(field)
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in '0123456789abcdef' for char in digest)):
        raise ValueError('Missing or invalid ' + field)
    return digest


def build_manifest(baseline, target, reference, app, elf,
                   candidate_receipt, image_receipt, selection_receipt):
    """Verify exact offline artifacts and return a non-installable sector plan."""
    if any(not isinstance(item, bytes) for item in (baseline, target, app, elf)):
        raise ValueError('Baseline, target, app and ELF must be immutable bytes')
    if len(baseline) != raw.FLASH_BYTES or len(target) != raw.FLASH_BYTES:
        raise ValueError('Complete exact-size raw baseline and target required')
    if not isinstance(reference, (str, bytes, os.PathLike)):
        raise ValueError('Pinned raw-layout reference required')
    if not all(isinstance(item, dict) for item in
               (candidate_receipt, image_receipt, selection_receipt)):
        raise ValueError('Candidate, linked image and selection receipts required')

    # Reparse the geometry from actual bytes; receipts alone do not prove it.
    geometry = expanded.validate_geometry(baseline, target, reference, app)
    if (candidate_receipt.get('schema') != 1
            or candidate_receipt.get('status') != 'private-expanded-native-candidate-verified-offline'
            or candidate_receipt.get('profile') != 'expanded-d9000-recorded-092'
            or candidate_receipt.get('flash_layout') != 'expanded-d9000'
            or candidate_receipt.get('baseline_profile') not in
               ('recorded-original-loader', 'fixed-loader')
            or candidate_receipt.get('geometry_verified') is not True
            or candidate_receipt.get('provenance_verified') is not True
            or candidate_receipt.get('elf_verified') is not True
            or candidate_receipt.get('protected_raw_ranges_identical') is not True
            or candidate_receipt.get('configuration_contents_identical') is not True):
        raise ValueError('Verified recorded-092 expanded candidate receipt required')
    for field, actual in (
            ('baseline_sha256', _sha256(baseline)),
            ('target_sha256', _sha256(target)),
            ('app_sha256', _sha256(app)),
            ('elf_sha256', _sha256(elf))):
        if _digest_field(candidate_receipt, field) != actual:
            raise ValueError('Candidate receipt does not match exact ' + field.removesuffix('_sha256'))
    if (candidate_receipt.get('app_bytes') != len(app)
            or candidate_receipt.get('target_bytes') != len(target)
            or geometry.get('profile') != 'expanded-d9000-recorded-092'
            or candidate_receipt.get('installable') is not False
            or candidate_receipt.get('hardware_admitted') is not False
            or candidate_receipt.get('physical_writer_ready') is not False
            or candidate_receipt.get('settings_migration_verified') is not False
            or candidate_receipt.get('ota_package_verified') is not False):
        raise ValueError('Candidate sizes, profile or unadmitted state differ')

    if (image_receipt.get('version') != 1
            or image_receipt.get('status') != 'linked-private-diagnostic'
            or image_receipt.get('installable') is not False
            or image_receipt.get('hardware_admitted') is not False
            or image_receipt.get('hardware_tested') is not False
            or image_receipt.get('app_sha256') != _sha256(app)
            or image_receipt.get('elf_sha256') != _sha256(elf)
            or image_receipt.get('app_bytes') != len(app)
            or image_receipt.get('app_budget_bytes') != expanded.APP_BUDGET):
        raise ValueError('Exact expanded-d9000 linked private image receipt required')

    request_sha = _digest_field(selection_receipt, 'request_sha256')
    profile_sha = _digest_field(selection_receipt, 'prepared_profile_sha256')
    project_ids = selection_receipt.get('project_ids')
    startup_index = selection_receipt.get('startup_index')
    startup_id = selection_receipt.get('startup_project_id')
    if (selection_receipt.get('version') != 1
            or selection_receipt.get('status') != 'prepared-build-inputs'
            or selection_receipt.get('installable') is not False
            or type(startup_index) is not int
            or not isinstance(project_ids, list) or not project_ids
            or any(not isinstance(project_id, str) or not project_id for project_id in project_ids)
            or len(set(project_ids)) != len(project_ids)
            or not 0 <= startup_index < len(project_ids)
            or project_ids[startup_index] != startup_id):
        raise ValueError('Exact ordered, unadmitted preload selection required')
    if (image_receipt.get('request_sha256') != request_sha
            or image_receipt.get('prepared_profile_sha256') != profile_sha
            or image_receipt.get('project_ids') != project_ids
            or image_receipt.get('startup_index') != startup_index
            or image_receipt.get('startup_project_id') != startup_id):
        raise ValueError('Linked image and prepared selection receipts differ')

    allowed = candidate_receipt.get('allowed_sectors')
    directory = candidate_receipt.get('directory_sector')
    writable = candidate_receipt.get('writable_ranges')
    expected_changed = [offset for offset in range(raw.APP_BASE, expanded.AREA_END, 4096)
                        if baseline[offset:offset + 4096] != target[offset:offset + 4096]]
    if (not isinstance(allowed, list) or not allowed
            or any(type(offset) is not int for offset in allowed)
            or allowed != sorted(set(allowed))
            or directory != raw.APP_BASE
            or allowed != expected_changed
            or writable != [[offset, offset + 4096] for offset in allowed]
            or any(offset < raw.APP_BASE or offset + 4096 > expanded.AREA_END
                   or offset % 4096 for offset in allowed)):
        raise ValueError('Candidate sector map differs from actual changed sectors')
    ordered = [offset for offset in allowed if offset != directory] + [directory]

    return dict(
        schema=1,
        status='offline-expanded-transport-manifest',
        profile='expanded-d9000-recorded-092',
        target_sha256=_sha256(target), target_bytes=len(target),
        baseline_sha256=_sha256(baseline),
        app_sha256=_sha256(app), app_bytes=len(app),
        elf_sha256=_sha256(elf),
        candidate_receipt_sha256=_sha256(canonical(candidate_receipt)),
        image_receipt_sha256=_sha256(canonical(image_receipt)),
        selection_receipt_sha256=_sha256(canonical(selection_receipt)),
        request_sha256=request_sha, prepared_profile_sha256=profile_sha,
        project_ids=list(project_ids), startup_index=startup_index,
        startup_project_id=startup_id,
        changed_sectors=allowed, sector_order=ordered,
        directory_sector=directory,
        protected_ranges=[[0, raw.APP_BASE], [expanded.AREA_END, raw.FLASH_BYTES]],
        geometry_verified=True, receipt_correspondence_verified=True,
        hardware_admitted=False, physical_writer_ready=False,
        settings_migration_verified=False, recovery_verified=False,
        installable=False, device_io_performed=False,
        next_gate='Review a concrete native recovery transaction, migration and rollback')
