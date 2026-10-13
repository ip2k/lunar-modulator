"""MIT. Offline strict replay of the first native controls installation.

This opens only saved files. A proof grants no live connection or boot authority.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fm1_fixed_target_reset import Replay, canonical, digest, read_file
from native.controls_live import SOURCES
from native.controls_transactions import V8_SHA, NATIVE_SHA, MANIFEST_SHA, changed_ranges

LIVE_SHA = 'd8c836e277aa2211415624dc2d287e91b865964a2a8546a278408237b255e4ef'
CAMPAIGN_SHA = '4560ebeca7018029d60300a9ee12c3ee3d4f43a41e1da4891bac815f4e97f562'
PLAN_SHA = 'b3b7970815653a32f4d0e4303029fa7ad8ae9a34b1431d41a5ce5032e1e17c4c'
CURSOR_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'


def verify(directory):
    directory = Path(directory).absolute()
    for name, sha in dict(SOURCES, **{'native/controls_live.py': LIVE_SHA,
                                     'fm1_fixed_target_reset.py': CURSOR_SHA}).items():
        if digest(read_file(ROOT/name)) != sha:
            raise ValueError('Reviewed replay source differs')
    campaign_raw = read_file(directory/'native-install-campaign.json',65536)
    if digest(campaign_raw) != CAMPAIGN_SHA:
        raise ValueError('Exact physical campaign required')
    c = json.loads(campaign_raw)
    if read_file(directory/'.native-native-install.consumed',128) != CAMPAIGN_SHA.encode():
        raise ValueError('Completed one-use campaign marker required')
    planroot = directory/'controls-plans/native'
    plan_raw = read_file(planroot/'plan.json',65536)
    if digest(plan_raw) != PLAN_SHA:
        raise ValueError('Exact reviewed plan required')
    plan = json.loads(plan_raw)
    baseline = read_file(planroot/'backupA.bin')
    if (digest(baseline) != V8_SHA or read_file(planroot/'backupB.bin') != baseline):
        raise ValueError('Matching admitted baseline required')
    target = read_file(planroot/'target.bin')
    if digest(target) != NATIVE_SHA or changed_ranges(baseline,target) != plan['writable_ranges']:
        raise ValueError('Target or protected ranges differ')
    journal = json.loads(read_file(planroot/'journal.json',65536))
    recorded = journal.pop('record_sha256')
    if (digest(canonical(journal)) != recorded or journal['state'] != 'complete'
            or journal['intent'] is not None or journal['direction'] != 'install'
            or journal['plan_sha256'] != PLAN_SHA or journal['verified_sha256'] != NATIVE_SHA
            or journal['sector_order'] != plan['sector_order']):
        raise ValueError('Verified complete journal required')
    raw = read_file(directory/'native-install-001/commands.jsonl',32*1048576)
    events = [json.loads(line) for line in raw.decode().splitlines()]
    if not events or len(events)>100000:
        raise ValueError('Bounded complete transcript required')
    times = [event.get('time') for event in events]
    if (not all(type(t) in (int,float) and math.isfinite(t) for t in times)
            or times != sorted(times) or times[-1]>time.time()):
        raise ValueError('Invalid chronology')
    r = Replay(events)
    r.event('native_transaction_prepared',campaign_sha256=CAMPAIGN_SHA,
        source_sha256=SOURCES,adapter_sha256=LIVE_SHA,backup_manifest_sha256=MANIFEST_SHA,
        sg_binding=c['sg_binding'],variant='native',direction='install',retry=False)
    r.direction='install'
    r.command(0xFC0A); r.read(baseline,0,1048576)
    current, changed = baseline,0
    for address in plan['sector_order']:
        sector = target[address:address+4096]
        actual = current[address:address+4096]
        r.read(current,address,4096)
        if actual == sector:
            continue
        if actual != b'\xff'*4096:
            r.event('durable_intent',operation='erase',address=address)
            r.command(0xFC0A); r.command(0xFB01,address)
            r.event('operation_returned',operation='erase',address=address)
        blank = current[:address]+b'\xff'*4096+current[address+4096:]
        r.read(blank,address,4096)
        for page in range(address,address+4096,256):
            payload=target[page:page+256]
            if payload != b'\xff'*256:
                r.event('durable_intent',operation='program',address=page)
                r.command(0xFC0A); r.command(0xFB04,page,payload)
                r.event('operation_returned',operation='program',address=page)
        current=current[:address]+sector+current[address+4096:]
        r.read(current,address,4096)
        r.event('sector_verified',address=address)
        changed+=1
    r.read(target,0,1048576)
    accepted=dict(campaign_sha256=CAMPAIGN_SHA,direction='install',variant='native',
        verified_sha256=NATIVE_SHA,sectors_written=changed,full_flash_readback_verified=True,
        boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
    r.event('native_transaction_completed',**accepted)
    result=json.loads(read_file(directory/'native-install-001/result.json',65536))
    if r.position != len(events) or canonical(result) != canonical(accepted):
        raise ValueError('Exact complete terminal result required')
    return dict(verified=True,hardware_operations=0,commands=r.index,events=len(events),
        sectors=changed,seconds=times[-1]-times[0],target_sha256=NATIVE_SHA,
        transcript_sha256=digest(raw),boot_observed=False,physical_recovery_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    print(json.dumps(verify(parser.parse_args().directory),sort_keys=True))
