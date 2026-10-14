#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose a private, pinned native controls OTA prototype offline.

No transport or hardware admission. This 20-second, NOR-write-disabled probe
is not a release; boot, recovery and browser installation remain unverified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
from inspect_fwsc import header_decode, inspect
from model_app_replacement import _build, verify_replacement
from inspect_version_contract import STOCK_TAIL_SHA256

STOCK_SHA = 'db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a'
APP_SHA = '7471be3e9e2df50ea934f56577e1a61469e99a755ded619a67fff9999796b527'
# Exact current probe's normal OTA_IDENTITY, traced through platform.c.
IDENTITY = 'FM-1_990'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inputs(raw, app):
    if digest(raw) != STOCK_SHA or digest(app) != APP_SHA:
        raise ValueError('Only the reviewed V15 container and native controls app are supported')
    if (IDENTITY.encode() + b'\0') not in app:
        raise ValueError('Reviewed normal-mode identity missing from app')


def verify_version_contract(raw, outer, app):
    """Bind one expected identity marker while retaining other app string data."""
    identities = list(re.finditer(rb'FM-1_[0-9]{3}\0', app))
    matches = [match for match in identities if match.group()[:-1].decode('ascii') == outer['identity']]
    if len(matches) != 1 or outer['unknown_header_fields'] != [4, 512]:
        raise ValueError('candidate identity or observed metadata profile differs')
    logical = b''.join(raw[offset:offset + 47] for offset in range(0, 960, 48)) + raw[960:]
    tail = next((item for item in outer['entries'] if item['name'] == 'tail.bin'), None)
    if (tail is None or tail['type'] != 255 or tail['bytes'] != 64
            or tail['sha256'] != STOCK_TAIL_SHA256):
        raise ValueError('opaque stock UFW trailer differs')
    record = header_decode(logical[64 + tail['index'] * 80:144 + tail['index'] * 80])
    if any(record[6:8]) or tail['allocated_bytes'] != 64 or any(record[20:64]):
        raise ValueError('observed UFW trailer record differs')
    return dict(identity=outer['identity'], app_identity_offset=matches[0].start(),
                app_identity_matches_markers=True, tail_sha256=tail['sha256'],
                trailer_record_profile_verified=True, metadata_profile_verified=True,
                device_version_acceptance=False)


def verify(raw, candidate, stock, app):
    """Recheck outer, nested-component, and version-marker correspondence."""
    inputs(raw, app)
    outer = inspect(candidate, stock)
    if outer['identity'] != IDENTITY or len(candidate) != len(raw):
        raise ValueError('Candidate identity/length differs')
    # Check the candidate's app identity against its FWSC markers and pin the
    # opaque version/trailer profile. This is evidence of byte correspondence,
    # not proof that the device accepts the identity.
    version = verify_version_contract(candidate, outer, app)
    normalized = bytearray(candidate)
    for index in range(20):
        normalized[index * 48 + 47] = raw[index * 48 + 47]
    proof = verify_replacement(raw, bytes(normalized), stock, app)
    nested = proof['modified_nested_check']
    expected_components = {
        'top/uboot.boot', 'top/isd_config.ini', 'files/cfg',
        'files/app.bin', 'files/cfg_tool.bin', 'files/eq_cfg_hw.bin',
    }
    component_hashes = nested['bound_component_sha256']
    if (not proof['stock_boot_config_resource_components_unchanged']
            or set(component_hashes) != expected_components
            or version['identity'] != IDENTITY
            or not version['app_identity_matches_markers']
            or not version['trailer_record_profile_verified']
            or not version['metadata_profile_verified']):
        raise ValueError('candidate FWSC, nested components, app, or version contract do not correspond')
    return dict(schema=1, kind='native-controls-private-ota-prototype',
                identity=IDENTITY, app_sha256=digest(app),
                candidate_sha256=digest(candidate), stock_sha256=digest(raw),
                replacement=proof,
                correspondence=dict(outer_header_crc=outer['header_crc_verified'],
                    outer_entry_crc=outer['entry_list_crc_verified'],
                    nested_full_container_noop=nested['full_container_noop_identical'],
                    app_identity=version['identity'],
                    app_identity_matches_markers=version['app_identity_matches_markers'],
                    geometry=dict(stock_xip=nested['stock_xip'],
                                  app_image_offset=nested['stock_xip']['app_image_offset'],
                                  entry=nested['stock_xip']['entry']),
                    preserved_component_sha256=component_hashes,
                    stock_ota_verified=outer['stock_ota_guard_verified'],
                    stock_spl_cfg_etc_verified=proof['stock_boot_config_resource_components_unchanged'],
                    opaque_tail_sha256=version['tail_sha256'],
                    device_version_acceptance=False),
                hardware_operations=0,
                physical_boot_verified=False, recovery_verified=False,
                web_install_verified=False, release_ready=False,
                probe_return_seconds=20, probe_nor_writes=False)


def compose(raw, stock, app):
    inputs(raw, app)
    candidate = bytearray(_build(raw, stock, app))
    name = IDENTITY.encode('ascii')
    for index in range(20):
        candidate[index * 48 + 47] = name[index] + index + 1 if index < len(name) else 125
    candidate = bytes(candidate)
    return candidate, verify(raw, candidate, stock, app)


def emit(directory, candidate, receipt):
    """Exclusive private output; partial output never grants installation authority."""
    directory.mkdir(mode=0o700)
    for name, data in [('lunar-native-controls.fwsc', candidate),
                       ('receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())]:
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-package', type=Path, required=True)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    candidate, receipt = compose(args.stock_package.read_bytes(), args.stock,
                                 args.app.read_bytes())
    emit(args.out, candidate, receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'replacement'}))


if __name__ == '__main__':
    main()
