#!/usr/bin/env python3
"""MIT. Exact SDK diagnostic install and full NOR verification, without boot.

The frozen rehearsal factory still validates both recovery directions. This
distinct runner executes only install. Target boot and stock restore require
separate reviewed campaigns; no command is added to the frozen SG allowlist.
"""
import argparse
from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import stat
import time
from weakref import WeakSet

REHEARSAL_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
_AUTHORIZED = WeakSet()


def read_source(path, limit=2 * 1024 * 1024):
    """Establish bounded regular source bytes before importing its reader."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Regular frozen source required')
        fp = os.fdopen(fd, 'rb')
        fd = None
        with fp:
            data = fp.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Frozen source exceeds bound')
        return data
    finally:
        if fd is not None:
            os.close(fd)


def rehearsal_module():
    root = Path(__file__).absolute().parent
    path = root / 'fm1_sdk_rehearsal.py'
    # Use the frozen reader only after its location and bytes are established.
    if hashlib.sha256(read_source(path)).hexdigest() != REHEARSAL_SHA:
        raise ValueError('Frozen rehearsal implementation changed')
    sys.path.insert(0, str(root))
    module = importlib.import_module('fm1_sdk_rehearsal')
    if Path(module.__file__).absolute() != path:
        raise ValueError('Ambient rehearsal implementation')
    if module.digest(module.read_file(path)) != REHEARSAL_SHA:
        raise ValueError('Frozen rehearsal implementation changed')
    return module


@dataclass(frozen=True, eq=False)
class Prepared:
    config: bytes
    campaign_sha256: str
    campaign_path: Path
    rehearsal_path: Path
    rehearsal_sha256: str
    adapter_sha256: str
    underlying: object
    runtime: object

    @property
    def policies(self):
        return (self.underlying.policies[0],)

    @property
    def mapping(self):
        return self.underlying.mapping

    @property
    def bridge(self):
        return self.underlying.bridge

    @property
    def header_type(self):
        return self.underlying.header_type

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact prepared install instance required')
        r = self.runtime
        if (r.digest(r.read_file(Path(__file__).absolute())) != self.adapter_sha256
                or r.digest(r.read_file(Path(r.__file__).absolute())) != REHEARSAL_SHA
                or r.digest(r.read_file(self.campaign_path, 65536)) != self.campaign_sha256
                or r.digest(r.read_file(self.rehearsal_path, 65536)) != self.rehearsal_sha256):
            raise ValueError('Frozen install adapter or campaign changed')
        self.underlying.check()
        if (len(self.underlying.policies) != 2
                or self.policies[0].direction != 'install'
                or self.underlying.policies[1].direction != 'restore'):
            raise ValueError('Exact install and preflighted restore policies required')


def prepare_campaign(path):
    """Freeze the new schema plus the exact unchanged rehearsal preparation."""
    r = rehearsal_module()
    path = Path(path).absolute()
    raw = r.read_file(path, 65536)
    config = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'rehearsal_campaign_path',
                'rehearsal_campaign_sha256', 'receipt_path'}
    if (not isinstance(config, dict) or set(config) != required
            or type(config['schema']) is not int or config['schema'] != 1
            or config['kind'] != 'fm1-exact-sdk-install-only'
            or config['adapter_sha256'] != r.digest(r.read_file(Path(__file__).absolute()))
            or not isinstance(config['rehearsal_campaign_path'], str)
            or not Path(config['rehearsal_campaign_path']).is_absolute()):
        raise ValueError('Exact reviewed install-only campaign required')
    old_path = Path(config['rehearsal_campaign_path'])
    old_raw = r.read_file(old_path, 65536)
    if r.digest(old_raw) != config['rehearsal_campaign_sha256']:
        raise ValueError('Underlying rehearsal campaign differs')
    underlying = r.prepare_campaign(old_path)
    old_config = json.loads(underlying.config)
    if config['receipt_path'] != old_config['receipt_path']:
        raise ValueError('Exact original prepared receipt path required')
    result = Prepared(r.canonical(config), r.digest(raw), path, old_path,
                      r.digest(old_raw), config['adapter_sha256'], underlying, r)
    _AUTHORIZED.add(result)
    result.check()
    return result


def run_campaign(prepared):
    prepared.check()
    r, bridge = prepared.runtime, prepared.bridge
    config = json.loads(prepared.config)
    receipt = Path(config['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    # Share the frozen rehearsal marker: changing adapters or receipt names
    # cannot re-use one attested active fixed-loader backup session.
    with bridge.private_file(receipt.parent / '.sdk-rehearsal.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii'))
        fp.flush()
        os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush()
            os.fsync(events.fileno())
            bridge.sync_dir(receipt)

        try:
            log('install_prepared', campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=prepared.adapter_sha256, rehearsal_sha256=REHEARSAL_SHA,
                rehearsal_campaign_sha256=prepared.rehearsal_sha256,
                source_sha256=r.SOURCES, sg_binding=json.loads(prepared.mapping),
                kernel_exclusivity=False, boot_observed=False,
                physical_recovery_verified=False, stock_restore_preflighted=True)
            policy = prepared.policies[0]
            transport = r.RehearsalSG(prepared, policy, log)
            try:
                result = policy.bind(transport).run(checkpoint=log)
            finally:
                transport.close()
            if result['verified_sha256'] != r.TARGET_SHA:
                raise ValueError('Final complete NOR verification differs')
            result = dict(campaign_sha256=prepared.campaign_sha256,
                          adapter_sha256=prepared.adapter_sha256,
                          rehearsal_sha256=REHEARSAL_SHA,
                          rehearsal_campaign_sha256=prepared.rehearsal_sha256,
                          direction='install', verified_sha256=r.TARGET_SHA,
                          baseline_sha256=r.BASELINE_SHA,
                          full_flash_readback_verified=True,
                          sectors_written=result['sectors_written'],
                          stock_restore_preflighted=True,
                          stock_baseline_restored=False,
                          boot_observed=False, physical_recovery_verified=False,
                          kernel_exclusivity=False)
            log('install_completed', **result)
            with bridge.private_file(receipt / 'result.json', 'w') as fp:
                json.dump(result, fp, indent=2)
                fp.write('\n')
                fp.flush()
                os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            try:
                (receipt / 'result.json').unlink(missing_ok=True)
                bridge.sync_dir(receipt)
            except OSError:
                pass
            try:
                log('install_stopped_ambiguous', error=type(exc).__name__, detail=str(exc),
                    retry=False, stock_baseline_restored=False, boot_observed=False)
            except OSError:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()
