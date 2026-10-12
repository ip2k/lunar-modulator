#!/usr/bin/env python3
"""MIT. Evidence-only interrupted returned-stock restore admission, WIP.

There is deliberately no device opener or execution capability. Existing
one-shot sources and consumed markers are never changed. A new reviewed live
acquisition envelope is still required before partial NOR can authorise resume.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

RESTORE_SOURCE_SHA = 'f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33'
REPLAY_SOURCE_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TARGET_SHA = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
EXECUTION_POLICY_SHA = None
ORDER = tuple(range(0x5000, 0x22000, 4096)) + (0x4000,)
_PROOFS = WeakSet()


def digest(data): return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try: fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd); raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode): raise ValueError('Regular evidence required')
        data = fp.read(limit + 1)
    if len(data) > limit: raise ValueError('Evidence exceeds bound')
    return data


def load_replay():
    path = Path(__file__).absolute().parent / 'fm1_fixed_target_reset.py'
    source = read_file(path)
    if digest(source) != REPLAY_SOURCE_SHA: raise ValueError('Frozen replay source differs')
    module = types.ModuleType('_returned_resume_replay')
    module.__file__ = str(path); sys.modules[module.__name__] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


@dataclass(frozen=True, eq=False)
class InterruptedProof:
    expected_nor: bytes
    baseline: bytes
    uncertainty: tuple
    journal_intents: bytes
    initial_verified: bool
    final_stock_verified: bool
    sectors_verified: tuple
    submitted_commands: int
    stop_error: str
    terminal_at: float


class _End(Exception): pass


class _Cursor:
    def __init__(self, rows, baseline, target, wire):
        self.rows, self.wire, self.baseline = rows, wire, baseline
        self.position = self.index = 0
        self.current = bytearray(target)
        self.uncertainty = ()
        self.intent = None
        self.possible_intents = []
        self.initial = self.final = False
        self.verified = []
        self.pending = None

    def boundary(self, next_name=None, fields=None):
        if self.position == len(self.rows):
            # Journal publication precedes its checkpoint event. A stopped
            # logger may leave precisely the next durable intent or a cleared
            # intent at the next sector_verified boundary, never arbitrary state.
            self.possible_intents = [self.intent]
            if next_name == 'durable_intent': self.possible_intents.append(fields)
            if next_name == 'sector_verified': self.possible_intents.append(None)
            raise _End()

    def add_uncertainty(self, start, end):
        spans = sorted((*self.uncertainty, (start, end)))
        merged = []
        for a,b in spans:
            if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0],max(b,merged[-1][1]))
            else: merged.append((a,b))
        self.uncertainty = tuple(merged)

    def verified_page(self, start):
        end = start + 256
        spans = []
        for a,b in self.uncertainty:
            if b <= start or a >= end: spans.append((a,b))
            else:
                if a < start: spans.append((a,start))
                if b > end: spans.append((end,b))
        self.uncertainty = tuple(spans)

    def event(self, name, **fields):
        self.boundary(name, fields)
        actual = dict(self.rows[self.position]); actual.pop('time')
        if canonical(actual) != canonical(dict(event=name, **fields)):
            raise ValueError('Interrupted restore order/fields differ at ' + str(self.position))
        self.position += 1
        if name == 'durable_intent': self.intent = fields
        elif name == 'operation_returned':
            operation, address = fields['operation'], fields['address']
            if operation == 'erase': self.current[address:address+4096] = b'\xff' * 4096
            else: self.current[address:address+256] = self.baseline[address:address+256]
            # Native handler return does not prove that NOR accepted the write.
            # Retain every attempted byte until actual matching FD05 readback.
            self.pending = None
        elif name == 'sector_verified':
            self.intent = None; self.verified.append(fields['address'])

    def command(self, op, address=0, payload=b'', response=None):
        cdb, payload, size = self.wire(op, address, payload)
        self.event('sg_submit_intent', index=self.index, direction='restore', cdb=cdb.hex(),
            out_len=len(payload), in_len=size,
            payload_sha256=digest(payload) if payload else None, retry=False)
        self.index += 1
        if op in (0xFB01, 0xFB04):
            self.add_uncertainty(address,address + (4096 if op == 0xFB01 else 256))
            self.pending = (op, address)
        self.boundary()
        e = dict(self.rows[self.position]); e.pop('time')
        keys = {'event','index','direction','status','masked','msg','host','driver','resid',
            'info','sense_len','sense_hex','retry','response_sha256'}
        if (set(e) != keys or e['event'] != 'sg_completion' or type(e['index']) is not int or
                e['index'] != self.index-1 or e['direction'] != 'restore' or e['retry'] is not False or
                any(type(e[k]) is not int for k in ('status','masked','msg','host','driver','resid','info','sense_len')) or
                any(not 0 <= e[k] <= 255 for k in ('status','masked','msg')) or
                any(not 0 <= e[k] <= 65535 for k in ('host','driver')) or
                not 0 <= e['info'] <= 0xffffffff or not 0 <= e['sense_len'] <= 255 or
                not isinstance(e['sense_hex'],str) or len(e['sense_hex']) != min(e['sense_len'],32)*2 or
                any(c not in '0123456789abcdef' for c in e['sense_hex'])):
            raise ValueError('Bounded exact SG completion required')
        sha = e['response_sha256']
        if (size and (not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha))
                or not size and sha is not None):
            raise ValueError('Bounded actual response hash required')
        ambiguous = any(e[k] for k in ('status','masked','msg','host','driver','resid','info','sense_len'))
        wrong_read = response is not None and sha != digest(response)
        self.position += 1
        if ambiguous or wrong_read:
            if self.position != len(self.rows): raise ValueError('Command followed an ambiguous completion')
            self.boundary()
        # Only actual matching readback clears uncertain physical write spans.
        # Native completion and operation_returned do not prove NOR success.
        if op == 0xFD05 and response is not None: self.verified_page(address)

    def read(self, address, size):
        for page in range(address,address+size,256):
            if (self.position < len(self.rows) and
                    self.rows[self.position].get('cdb') == self.wire(0xFC0A)[0].hex()):
                self.command(0xFC0A)
            self.command(0xFD05,page,response=bytes(self.current[page:page+256]))


def verify_interrupted_prefix(raw, c, campaign_sha, mapping, baseline, target):
    """Evidence only, strict caught-stop prefix; no opener or current-state claim.

    An sg_submit_intent means only an attempted request. Its final mutation can
    leave the addressed sector/page uncertain even if no transmission is proven.
    Every attempted mutation remains uncertain until matching FD05 page readback;
    several unverified program pages may accumulate within the current sector.
    A complete matching fresh dual dump is required to constrain actual NOR.
    """
    if (not isinstance(raw,bytes) or len(raw)>32*1048576 or
            len(baseline)!=1048576 or len(target)!=1048576 or
            digest(baseline)!=BASELINE_SHA or digest(target)!=TARGET_SHA):
        raise ValueError('Exact bounded stock/target interrupted evidence required')
    rows = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    times = [e.get('time') for e in rows]
    if (not 2 <= len(rows) <= 100000 or
            not all(type(t) in (int,float) and math.isfinite(t) for t in times) or
            times != sorted(times) or times[-1] > time.time()):
        raise ValueError('Chronological terminal stopped restore required')
    stop = dict(rows.pop()); stop.pop('time')
    error = stop.get('error')
    if (not isinstance(error,str) or not error or len(error)>128 or
            canonical(stop) != canonical(dict(event='returned_restore_stopped_ambiguous',
                error=error,retry=False,stock_baseline_restored=False,boot_observed=False))):
        raise ValueError('Exact caught-stop without success claim required')
    # Immutable target is permitted to differ only in the original thirty
    # sectors. The full genuine SDK provenance factory is an independent gate.
    for start,end in ((0,0x4000),(0x22000,1048576)):
        if baseline[start:end]!=target[start:end]: raise ValueError('Protected stock bytes differ')
    replay = load_replay()
    r = _Cursor(rows,baseline,target,replay.wire)
    try:
        r.event('returned_restore_prepared',campaign_sha256=campaign_sha,
            adapter_sha256=c['adapter_sha256'],returned_backup_campaign_sha256=c['returned_backup_campaign_sha256'],
            returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],sg_binding=mapping,
            initial_journal_sha256=c['install_journal_sha256'],target_sha256=TARGET_SHA,
            baseline_sha256=BASELINE_SHA,direction='restore',boot_observed=False,
            physical_recovery_verified=False,kernel_exclusivity=False)
        r.command(0xFC0A); r.read(0,1048576); r.initial=True
        for address in ORDER:
            r.read(address,4096)
            sector = baseline[address:address+4096]
            if bytes(r.current[address:address+4096]) == sector: continue
            if bytes(r.current[address:address+4096]) != b'\xff'*4096:
                r.event('durable_intent',operation='erase',address=address)
                r.command(0xFC0A); r.command(0xFB01,address)
                r.event('operation_returned',operation='erase',address=address)
            r.read(address,4096)
            for page in range(address,address+4096,256):
                payload=baseline[page:page+256]
                if payload!=b'\xff'*256:
                    r.event('durable_intent',operation='program',address=page)
                    r.command(0xFC0A); r.command(0xFB04,page,payload)
                    r.event('operation_returned',operation='program',address=page)
            r.read(address,4096);r.event('sector_verified',address=address)
        r.read(0,1048576);r.final=True
        r.event('returned_restore_completed',campaign_sha256=campaign_sha,direction='restore',
            initial_full_target_readback_verified=True,verified_sha256=BASELINE_SHA,
            full_flash_readback_verified=True,sectors_written=len(r.verified),stock_baseline_restored=True,
            boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
        r.boundary()
        raise ValueError('Unexpected events after completed restore')
    except _End:
        proof=InterruptedProof(bytes(r.current),baseline,r.uncertainty,canonical(r.possible_intents),
            r.initial,r.final,tuple(r.verified),r.index,error,times[-1])
        _PROOFS.add(proof);return proof


def check_partial_dumps(proof, dump_a, dump_b):
    """No source/USB/loader authority; constrain complete acquired NOR only."""
    if not isinstance(proof,InterruptedProof) or proof not in _PROOFS:
        raise ValueError('Exact replay-created interrupted proof required')
    if (not isinstance(dump_a,bytes) or len(dump_a)!=1048576 or dump_a!=dump_b):
        raise ValueError('Two matching complete recovery-state dumps required')
    if dump_a[:0x4000]!=proof.baseline[:0x4000] or dump_a[0x22000:]!=proof.baseline[0x22000:]:
        raise ValueError('Protected stock region changed')
    previous=0
    for start,end in (*proof.uncertainty,(1048576,1048576)):
        if dump_a[previous:start]!=proof.expected_nor[previous:start]:
            raise ValueError('NOR changed outside actual unverified mutation spans')
        previous=end
    return dict(partial_nor_sha256=digest(dump_a),uncertain_ranges=[list(x) for x in proof.uncertainty],
        dual_complete_identical=True,stock_baseline_restored=dump_a==proof.baseline,
        boot_observed=False,physical_recovery_verified=False)


def prepare_campaign(path):
    """Closed until independent partial-backup/live-lineage admission is reviewed."""
    raise ValueError('Interrupted resume execution policy is not reviewed or activated')
