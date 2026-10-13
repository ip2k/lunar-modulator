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
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
from inspect_fwsc import inspect
from model_app_replacement import _build, verify_replacement

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


def verify(raw, candidate, stock, app):
    """Independently inspect output, then enforce the incumbent replacement contract."""
    inputs(raw, app)
    outer = inspect(candidate, stock)
    if outer['identity'] != IDENTITY or len(candidate) != len(raw):
        raise ValueError('Candidate identity/length differs')
    normalized = bytearray(candidate)
    for index in range(20):
        normalized[index * 48 + 47] = raw[index * 48 + 47]
    proof = verify_replacement(raw, bytes(normalized), stock, app)
    return dict(schema=1, kind='native-controls-private-ota-prototype',
                identity=IDENTITY, app_sha256=digest(app),
                candidate_sha256=digest(candidate), stock_sha256=digest(raw),
                replacement=proof, hardware_operations=0,
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
