"""MIT. Exact native bench policy for injected, fixed-loader transports.

No physical opener, ROM entry, reset, upload or CLI. Matching evidence and
injected assertions are necessary checks, not proof of a live connection.
The eventual Linux opener must separately verify current SG/sysfs ownership.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from weakref import WeakSet

from fm1_bound_diagnostic import BoundDiagnosticSession
from fm1_flash_transaction import (load_transaction, encoded, digest,
                                   checked_plan_order)
from native.controls_transactions import (V8_SHA, STOCK_SHA, NATIVE_SHA, MANIFEST_SHA,
                                      COMMANDS_SHA, APP_BASE, changed_ranges, pinned)

LOADER_SHA = 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'
SOURCES = {
    'native/controls_transactions.py': '20aae9b173b0fac71031fd97dc71ef0dfe71c2fd54ce844a89123268272b672a',
    'fm1_bound_diagnostic.py': '25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36',
    'fm1_flash_transaction.py': 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
}
_POLICIES = WeakSet()


def check_sources():
    root = Path(__file__).resolve().parents[1]
    for name, sha in SOURCES.items():
        pinned(root / name, sha)


@dataclass(frozen=True, eq=False)
class Policy:
    directory: Path
    direction: str
    plan_bytes: bytes
    baseline: bytes
    target: bytes
    receipt_bytes: bytes
    binding_bytes: bytes
    sectors: tuple
    evidence: tuple

    def check_files(self):
        if self not in _POLICIES:
            raise ValueError('Exact factory-created native policy required')
        check_sources()
        for path, sha, limit in self.evidence:
            pinned(path, sha, limit)
        plan, journal, before, after = load_transaction(self.directory)
        if (encoded(plan) != self.plan_bytes or before != self.baseline or after != self.target):
            raise ValueError('Native transaction artifacts changed')
        return journal

    def receipt(self):
        return json.loads(self.receipt_bytes)

    def bind(self, transport):
        self.check_files()
        return NativeSession(self, transport)


def load_policy(directory, *, direction, receipt, variant='native'):
    """Validate exact recorded evidence and plan before touching a transport."""
    if direction not in ('install', 'restore') or variant not in ('native', 'stock'):
        raise ValueError('Explicit native/stock variant and install/restore required')
    check_sources()
    receipt = Path(receipt).resolve()
    manifest_path, commands_path = receipt / 'manifest.json', receipt / 'commands.jsonl'
    manifest = json.loads(pinned(manifest_path, MANIFEST_SHA, 65536))
    pinned(commands_path, COMMANDS_SHA, 8 * 1048576)
    a = pinned(receipt / 'dumpA.bin', V8_SHA)
    b = pinned(receipt / 'dumpB.bin', V8_SHA)
    directory = Path(directory).resolve()
    plan, _, baseline, target = load_transaction(directory)
    target_sha = NATIVE_SHA if variant == 'native' else STOCK_SHA
    scope = ('fresh bounded native Trio controls probe' if variant == 'native'
             else 'stock after verified V8 rollback')
    identity = dict(unit_id='owner-fm1-bench01-fresh-rom-device27',
                    flash_size=1048576, sector_size=4096, page_size=256,
                    jedec=0x856014, simulated=False,
                    usb_binding=manifest['usb_binding'], backup_manifest_sha256=MANIFEST_SHA)
    if (baseline != a or a != b or digest(target) != target_sha or
            plan['identity'] != identity or plan['scope'] != scope or
            plan['commit_sector'] != APP_BASE or
            plan['writable_ranges'] != changed_ranges(a, target)):
        raise ValueError('Exact recorded native or stock transaction required')
    order = checked_plan_order(plan)
    if order != list(range(0x5000, 0x22000, 4096)) + [APP_BASE]:
        raise ValueError('Exact 30-sector directory-last plan required')
    binding = dict(usb_binding=manifest['usb_binding'],
                   backup_manifest_sha256=MANIFEST_SHA,
                   backup_commands_sha256=COMMANDS_SHA,
                   backup_campaign_sha256=manifest['campaign_sha256'])
    result = dict(kind='native-controls-injected-policy', variant=variant,
                  hardware_admitted=False, installable=False,
                  physical_recovery_verified=False, target_sha256=target_sha,
                  baseline_sha256=V8_SHA, transaction_plan_sha256=digest(encoded(plan)))
    evidence = ((manifest_path, MANIFEST_SHA, 65536),
                (commands_path, COMMANDS_SHA, 8 * 1048576),
                (receipt / 'dumpA.bin', V8_SHA, 1048576),
                (receipt / 'dumpB.bin', V8_SHA, 1048576))
    policy = Policy(directory, direction, encoded(plan), baseline, target,
                    encoded(result), encoded(binding), tuple(sorted(order)), evidence)
    _POLICIES.add(policy)
    policy.check_files()
    return policy


class NativeSession(BoundDiagnosticSession):
    """Use inherited journal/page/wire guards with native provenance binding."""
    def __init__(self, policy, transport):
        if policy not in _POLICIES:
            raise ValueError('Exact native policy required')
        self._policy, self._transport = policy, transport
        self._latched, self._running, self._binding = False, False, None
        try:
            observed = self._capture_binding()
            required = json.loads(policy.binding_bytes)
            if (observed.get('phase') != 'loader' or observed.get('loader_sha256') != LOADER_SHA or
                    not isinstance(observed.get('session_id'), str) or not observed['session_id'].strip() or
                    observed.get('identity') != json.loads(policy.plan_bytes)['identity'] or
                    any(encoded(observed.get(k)) != encoded(v) for k, v in required.items())):
                raise ValueError('Fixed loader, native identity or fresh backup binding differs')
            self._binding = encoded(observed)
        except BaseException:
            self._stop()
            raise
