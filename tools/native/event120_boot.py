# SPDX-License-Identifier: MIT
"""One Event120 boot request after exact offline installation replay.

No flash, upload, retry or boot-success inference. The pending proof source pin
deliberately prevents use until the reviewed campaign verifier is integrated.
"""
import argparse
import ctypes
from dataclasses import dataclass
import fcntl
import importlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from weakref import WeakSet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fm1_fixed_target_reset import canonical, digest, read_file
from native.event120_install_proof import unique_object
from native.event120_reset import CompletionFirstReset

PROOF_SHA = 'pending-independent-campaign-proof'
RESET_SHA = 'f7b75e3448fe30babaed23b70340bab76db1e2c8815d13d22c6bdb00116a770c'
USB = dict(path='1-1', busnum='1', devnum='38', vid='4c4a', pid='8057')
_AUTHORIZED = WeakSet()


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    expected_mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact factory-created Event120 boot required')
        for path, sha in self.evidence:
            if digest(read_file(path, 32 * 1048576)) != sha:
                raise ValueError('Frozen boot evidence changed')
        c = json.loads(self.campaign, object_pairs_hook=unique_object)
        if not 0 <= time.time() - c['observed_at'] <= 120:
            raise ValueError('Boot observation expired')


def prepare(path):
    path = Path(path).absolute()
    raw = read_file(path, 65536)
    c = json.loads(raw, object_pairs_hook=unique_object)
    fields = {'schema', 'kind', 'adapter_sha256', 'observed_at', 'evidence_root',
        'sg_binding', 'usb_binding', 'receipt_path', 'active_session_state',
        'install_campaign_sha256'}
    if (set(c) != fields or type(c['schema']) is not int or c['schema'] != 1
            or c['kind'] != 'fm1-event120-device38-single-boot'
            or c['active_session_state'] != 'same-fixed-loader-event120-installed-no-later-commands'
            or c['usb_binding'] != USB or type(c['observed_at']) not in (int, float)
            or not math.isfinite(c['observed_at']) or not 0 <= time.time() - c['observed_at'] <= 120):
        raise ValueError('Exact fresh Event120 boot campaign required')
    adapter, proof_path = Path(__file__).resolve(), ROOT / 'native/event120_campaign_proof.py'
    if (digest(read_file(adapter)) != c['adapter_sha256']
            or digest(read_file(ROOT / 'native/event120_reset.py')) != RESET_SHA
            or digest(read_file(proof_path)) != PROOF_SHA):
        raise ValueError('Reviewed boot/proof/reset source differs')
    root, out = Path(c['evidence_root']), Path(c['receipt_path'])
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or stat.S_IMODE(root.stat().st_mode) != 0o700 or path.parent != root
            or not out.is_absolute() or out.parent != root or os.path.lexists(out)
            or os.path.lexists(root / '.event12038-boot.consumed')):
        raise ValueError('Private new one-use boot receipt required')
    proof = importlib.import_module('native.event120_campaign_proof')
    if Path(proof.__file__).resolve() != proof_path:
        raise ValueError('Ambient proof module forbidden')
    verified = proof.verify(root, c['install_campaign_sha256'])
    from native.event120_bench_live import sources
    bridge, reader, _ = sources()
    if (canonical(bridge.discover_sg(USB)) != canonical(c['sg_binding'])
            or ctypes.sizeof(reader.SGHeader) != 88):
        raise ValueError('Original loader connection or reviewed SG ABI differs')
    install_path = root / 'event120-install-v2-campaign.json'
    install = json.loads(read_file(install_path, 65536), object_pairs_hook=unique_object)
    if canonical(install['sg_binding']) != canonical(c['sg_binding']):
        raise ValueError('Installation connection differs')
    evidence = dict(verified['evidence_sha256'])
    for file in (path, adapter, proof_path, ROOT / 'native/event120_reset.py'):
        evidence[str(file)] = digest(read_file(file, 32 * 1048576))
    p = Prepared(raw, digest(raw), canonical(c['sg_binding']), bridge, reader.SGHeader,
        tuple((Path(file), sha) for file, sha in evidence.items()))
    _AUTHORIZED.add(p)
    p.check()
    return p


class BootSG(CompletionFirstReset):
    def __init__(self, prepared, log):
        prepared.check()
        self.prepared, self.log = prepared, log
        self.fd, self.consumed, self.failed, self.ioctl_attempts = None, False, False, 0
        self.phase, self.started = 'event120-installed-fixed-loader', time.monotonic()
        self.usb = USB
        try:
            self.mapping = prepared.bridge.discover_sg(USB)
            if canonical(self.mapping) != prepared.expected_mapping:
                raise ValueError('Loader connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def binding(self):
        self.prepared.check()
        return super().binding()


def run(prepared):
    prepared.check()
    c = json.loads(prepared.campaign)
    out, bridge = Path(c['receipt_path']), prepared.bridge
    out.mkdir(mode=0o700)
    bridge.sync_dir(out.parent)
    with bridge.private_file(out.parent / '.event12038-boot.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode()); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(out.parent)
    with bridge.private_file(out / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + '\n')
            events.flush(); os.fsync(events.fileno())
        transport = None
        try:
            log('event120_boot_prepared', campaign_sha256=prepared.campaign_sha256,
                install_campaign_sha256=c['install_campaign_sha256'], commands=1,
                flash_operations=0, upload_operations=0, retry=False, boot_observed=False)
            transport = BootSG(prepared, log)
            result = transport.request_reset()
            log('event120_boot_request_completed', **result, retry=False,
                physical_recovery_verified=False)
            return result
        except BaseException as exc:
            log('event120_boot_stopped', error=type(exc).__name__, detail=str(exc),
                retry=False, boot_observed=False)
            raise
        finally:
            if transport is not None:
                transport.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(); os.umask(0o077)
    p = prepare(args.campaign)
    print(json.dumps(dict(preflight=True, hardware_operations=0) if args.preflight else run(p)))
