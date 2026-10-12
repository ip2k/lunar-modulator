#!/usr/bin/python3
"""Closed source-only one-use sequencer; root alone reviews/stages/runs.

Only fixed commands to unchanged reviewed factories/wrappers. No direct device
opener, transport, PID signal, fallback, timestamp refresh or authority patch.
Child wrappers remain the real parents of their captures and enforce their own
bounded lifetimes. No external timeout kills a wrapper and abandons its capture.
"""
import argparse,hashlib,json,math,os,re,stat,subprocess,sys,time,types
from pathlib import Path

STAGE=Path('/home/claude/fm1-sdk-trace-campaign-20261012-v3')
ENTRY=Path('/home/claude/fm1-sdk-trace-entry-20261012-v3-2')
RUN=ENTRY/'automatic-trace-chain-v2'
H=STAGE/'build/sdk-trace-fresh-entry-bench-v1/next-campaign'
WIRE_PATH=ENTRY/'validate-owned-backup-fastpath-v3.py'
WIRE_SHA=None
CLOSURE_SHA=None
ROOT_ACCEPTANCE_SHA=None
# This records root review of the distinct partial-write recovery dependency;
# it grants no automatic opener or retry and does not replace its factory.
RECOVERY_PLAN_SHA=None
PYTHON='/usr/bin/python3'
FIXED_ARGS=['-B','-E','-s','-S']
ENV={'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path,limit=32*1048576):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('Direct regular file required')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(limit+1)
    finally:os.close(fd)
    if len(raw)>limit:raise ValueError('Bounded evidence exceeded')
    return raw

def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as stream:stream.write(raw);stream.flush();os.fsync(fd)
    finally:os.close(fd)
    sync(path.parent)

def obj(path):return json.loads(read(path,65536))
def require_open():
    for pin in (WIRE_SHA,CLOSURE_SHA,ROOT_ACCEPTANCE_SHA,RECOVERY_PLAN_SHA):
        if type(pin) is not str or re.fullmatch('[0-9a-f]{64}',pin) is None:
            raise ValueError('Closed proposal: source/wire/recovery/root review pins pending')

def private(path):
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o700 or info.st_uid!=os.geteuid():
        raise ValueError('Direct owner-private directory required')

def freshness(then,now,limit,label):
    if (type(then) not in (int,float) or type(now) not in (int,float)
            or not math.isfinite(then) or not math.isfinite(now) or not 0<=now-then<=limit):
        raise ValueError(label+' admission elapsed; original timestamp unchanged')

def closure_check():
    raw=read(ENTRY/'source-closure.json',65536)
    if digest(raw)!=CLOSURE_SHA:raise ValueError('Source closure differs')
    c=json.loads(raw)
    if c['entry_root']!=str(ENTRY) or c['unchanged_stage']!=str(STAGE):raise ValueError('Exact roots differ')
    for name,pin in c['stage_files'].items():
        if digest(read(STAGE/name))!=pin:raise ValueError('Frozen staged file differs: '+name)
    for name,pin in c['entry_files'].items():
        if digest(read(ENTRY/name))!=pin:raise ValueError('Frozen entry input differs: '+name)
    for name,pin in c['entry_derivatives'].items():
        if digest(read(ENTRY/name))!=pin:raise ValueError('Entry derivative differs: '+name)
    for name,pin in c['inputs'].items():
        if digest(read(ENTRY/'inputs'/name))!=pin:raise ValueError('Exact new input template differs')
    if digest(read(WIRE_PATH))!=WIRE_SHA:raise ValueError('Wire validator differs')
    if digest(read(ENTRY/'root-launch-acceptance.json',65536))!=ROOT_ACCEPTANCE_SHA:
        raise ValueError('Exact root review receipt differs')
    if digest(read(ENTRY/'partial-recovery-plan.json',65536))!=RECOVERY_PLAN_SHA:
        raise ValueError('Reviewed failure recovery plan differs')
    return c

def command(label,script,args=(),*,accept_nonzero=False):
    """One synchronous child; exact argv and source frozen before Popen.

    No adaptive rerun and no outer signal/kill. Existing wrapper owns capture
    cleanup. If externally interrupted, this chain remains consumed and root
    must inspect real descendants and receipts; it cannot restart this phase.
    """
    closure_check()
    index=len(list(RUN.glob('*.intent.json')))
    argv=[PYTHON,*FIXED_ARGS,str(script),*map(str,args)]
    save(RUN/f'{index:02d}-{label}.intent.json',dict(time=time.time(),argv=argv,
        cwd=str(STAGE),env=ENV,source_sha256=digest(read(script)),retry=False))
    out=RUN/f'{index:02d}-{label}.stdout'
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        with os.fdopen(fd,'wb',buffering=0,closefd=False) as log:
            try:result=subprocess.run(argv,cwd=STAGE,env=ENV,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=False)
            finally:os.fsync(fd)
    finally:os.close(fd)
    sync(RUN)
    save(RUN/f'{index:02d}-{label}.exit.json',dict(time=time.time(),exit_status=result.returncode,
        stdout_sha256=digest(read(out)),retry=False,nonzero_preserved=result.returncode!=0))
    if result.returncode!=0 and not accept_nonzero:raise RuntimeError(label+' stopped; no retry')
    return result.returncode

def packet_run(mode,campaign,packet,run):
    command(mode+'-packet',H/'prepare-admitted-wrapper-packet.py',
            [mode,'--stage',STAGE,'--campaign',campaign,'--packet',packet])
    return command(mode+'-worker',H/'owned-admitted-backup-restore-once-v1.py',
            [mode,'--stage',STAGE,'--run',run,'--packet',packet,'--packet-sha256',digest(read(packet,65536))])

def canonical_baseline_check():
    """Read-only real dbbe factory replay, never run_campaign/ResetSG."""
    m=obj(ENTRY/'stock-backup-001/manifest.json');path=ENTRY/'backup-campaign.json'
    sha='dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116'
    c=dict(schema=1,kind='fm1-fixed-loader-baseline-reset-campaign',adapter_sha256=sha,
        backup_adapter_path=str(STAGE/'tools/fm1_fixed_loader_backup.py'),
        backup_manifest_path=str(ENTRY/'stock-backup-001/manifest.json'),
        backup_manifest_sha256=digest(read(ENTRY/'stock-backup-001/manifest.json')),
        backup_campaign_path=str(path),backup_campaign_sha256=digest(read(path)),
        backup_commands_sha256=digest(read(ENTRY/'stock-backup-001/commands.jsonl')),
        backup_exit_status=0,active_session_state='matching-backup-no-later-commands',
        usb_binding=m['usb_binding'],sg_binding=m['sg_binding'],
        receipt_path=str(ENTRY/'stock-backup-001/core-reset-once'))
    campaign=RUN/'review-only-baseline-reset.json';save(campaign,c)
    source=STAGE/'tools/fm1_fixed_loader_reset.py';raw=read(source)
    if digest(raw)!=sha:raise ValueError('Canonical baseline factory source differs')
    module=types.ModuleType('_automatic_baseline_file_check');module.__file__=str(source)
    sys.modules[module.__name__]=module;exec(compile(raw,str(source),'exec'),module.__dict__)
    prepared=module.prepare_campaign(campaign)
    if prepared.campaign_sha256!=digest(read(campaign)):raise ValueError('Canonical baseline campaign differs')
    save(RUN/'baseline-file-replay.json',dict(time=time.time(),factory_passed=True,device_opener_called=False,
        backup_manifest_sha256=c['backup_manifest_sha256'],backup_commands_sha256=c['backup_commands_sha256']))

def completion_time():
    rows=[json.loads(line) for line in read(ENTRY/'stock-backup-001/commands.jsonl').splitlines()]
    if not rows or rows[-1].get('event')!='campaign_completed':raise ValueError('Actual completed backup required')
    return rows[-1]['time']

def pipeline():
    entry_source=ENTRY/'orchestrate-entry-backup-v3.py'
    command('entry-backup',entry_source,['--reviewed-self-sha256',digest(read(entry_source))])
    command('entry-wire',WIRE_PATH,[ENTRY,'--wrapper-dir','initial-entry-backup-v3-2','--expected-topology','1-1','--output',RUN/'initial-wire.json'])
    # The validator is additive; real canonical replay closes source, entry,
    # exact inventory, dump geometry and original private path safeguards.
    canonical_baseline_check()
    command('install-identity',ENTRY/'derive-install-identity.py')
    freshness(completion_time(),time.time(),120,'Backup-to-install')
    command('install-prepare',H/'prepare-packets-v2.py',['install','--stage',STAGE,
        '--packet',STAGE/'install.packet.json',ENTRY/'inputs/install.json',STAGE/'install-campaign.json'])
    command('install-worker',H/'owned-campaign-once-v2.py',['install','--stage',STAGE,
        '--run',STAGE/'install-run','--packet',STAGE/'install.packet.json',
        '--packet-sha256',digest(read(STAGE/'install.packet.json',65536))])
    command('boot-prepare',H/'prepare-packets-v2.py',['boot','--stage',STAGE,
        '--packet',STAGE/'boot.packet.json',ENTRY/'inputs/boot.json',STAGE/'boot-campaign.json'])
    command('boot-worker',H/'owned-campaign-once-v2.py',['boot','--stage',STAGE,
        '--run',STAGE/'boot-run','--packet',STAGE/'boot.packet.json',
        '--packet-sha256',digest(read(STAGE/'boot.packet.json',65536))],accept_nonzero=True)
    command('boot-lineage',H/'prepare-packets-v2.py',['boot-lineage','--stage',STAGE,
        ENTRY/'inputs/boot-lineage.json',STAGE/'boot-lineage.json'])
    snapshot=obj(STAGE/'boot-run/rom-snapshot.json')
    freshness(snapshot['observed_at'],time.time(),120,'Original-ROM-to-native')
    parent=ENTRY/'stock-backup-001'
    native=STAGE/'native-read-stage';nr=native/'run'
    command('native-prepare',H/'prepare-native-read-packet.py',['--stage',native,'--run',nr,
        '--lineage',STAGE/'boot-lineage.json','--elf',STAGE/'assets/native/lunar-sdk-diagnostic.elf',
        '--app',STAGE/'assets/native/lunar-sdk-diagnostic.app.bin','--manifest',STAGE/'assets/native/build-manifest.json',
        '--receipt',parent/'sdk-trace-read-001'])
    command('native-worker',nr/'execute-once.py',accept_nonzero=True)
    admitted=STAGE/'returned-admission.json';journal=STAGE/'transaction/journal.json'
    prep=H/'prepare-admitted-recovery-v4.py'
    command('returned-admission',prep,['admission','--factory-tools',STAGE/'tools',
        '--boot-lineage',STAGE/'boot-lineage.json','--native-campaign',nr/'campaign.json',
        '--owned-capture',nr/'owned-capture.json','--install-journal',journal,'--output',admitted])
    backup=STAGE/'returned-backup-campaign.json';preserved=parent/'journal-before-admitted-backup.json'
    command('returned-backup-prepare',prep,['backup','--factory-tools',STAGE/'tools',
        '--returned-admission',admitted,'--connection-witness',STAGE/'returned-backup-witness.json',
        '--install-journal',journal,'--preserve-journal',preserved,'--loader',STAGE/'assets/loader/loader.bin',
        '--profile',STAGE/'assets/loader/profile.json','--profile-source',STAGE/'tools/jieli/loader_config_profile.py',
        '--receipt',parent/'returned-target-backup-001','--output',backup])
    packet_run('backup',backup,STAGE/'returned-backup.packet.json',STAGE/'returned-backup-run')
    restore=STAGE/'returned-restore-campaign.json'
    command('returned-restore-prepare',prep,['restore','--factory-tools',STAGE/'tools',
        '--completed-backup-campaign',backup,'--backup-run',STAGE/'returned-backup-run',
        '--install-journal',journal,'--preserve-journal',preserved,
        '--receipt',parent/'returned-target-backup-001/stock-restore-001','--output',restore])
    packet_run('restore',restore,STAGE/'returned-restore.packet.json',STAGE/'returned-restore-run')
    completed_restore_check(restore,journal)
    save(RUN/'chain-completed.json',dict(time=time.time(),stock_full_readback_verified=True,
        stock_boot_observed=False,display_observed=False,physical_recovery_verified=False,retry=False))

def completed_restore_check(restore,journal):
    # Final real completed helper replay is still necessary. Its returned
    # registered proof is evidence-only, never an implicit stock reset opener.
    raw=read(STAGE/'tools/fm1_sdk_trace_admitted_stock_restore.py')
    expected='7d84f0d8699deded1990fc9758bc9580dcca771918c79a19d8ac31208f6c7a59'
    if digest(raw)!=expected:raise ValueError('Completed restore source differs')
    sys.path.insert(0,str(STAGE/'tools'))
    import fm1_sdk_trace_admitted_stock_restore as restored
    if Path(restored.__file__).absolute()!=STAGE/'tools/fm1_sdk_trace_admitted_stock_restore.py':raise ValueError('Canonical restore import differs')
    receipt=Path(obj(restore)['receipt_path'])
    def freeze(path,expected=None,limit=2*1048576):
        data=read(path,limit)
        if expected is not None and digest(data)!=expected:raise ValueError('Completed pinned evidence differs')
        return data
    restored.validate_completed_restore(restore,campaign_sha256=digest(read(restore)),
        commands_sha256=digest(read(receipt/'commands.jsonl')),result_sha256=digest(read(receipt/'result.json')),
        journal_sha256=digest(read(journal)),freeze=freeze)

def main():
    require_open() # Must precede persistent activity or process creation.
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reviewed-self-sha256',required=True)
    args=ap.parse_args()
    if digest(read(Path(__file__).absolute()))!=args.reviewed_self_sha256:
        raise ValueError('Sequencer differs from exact reviewed invocation source')
    if sys.platform!='linux' or os.geteuid()!=0 or sys.flags.optimize:raise ValueError('Reviewed nonoptimized Linux root required')
    os.umask(0o077);private(STAGE);private(ENTRY);private(RUN);closure_check()
    if any(RUN.iterdir()):raise ValueError('One-shot chain run must be empty')
    destinations=['transaction','install-campaign.json','install.packet.json','boot-campaign.json','boot.packet.json',
        'boot-lineage.json','native-read-stage','returned-admission.json','returned-backup-campaign.json',
        'returned-restore-campaign.json','returned-backup.packet.json','returned-restore.packet.json','returned-backup-witness.json']
    if os.path.lexists(ENTRY/'derived-install-identity.json'):
        raise ValueError('New derived identity destination must remain unused')
    if any(os.path.lexists(STAGE/name) for name in destinations):raise ValueError('Original stage destinations must remain unused')
    for name in ('install-run','boot-run','returned-backup-run','returned-restore-run'):
        private(STAGE/name)
        if any((STAGE/name).iterdir()):raise ValueError('Exact private empty wrapper run required')
    marker=ENTRY/'.automatic-trace-chain.consumed'
    save(marker,dict(time=time.time(),source_sha256=digest(read(Path(__file__).absolute())),retry=False))
    try:pipeline()
    except BaseException as exc:
        save(RUN/'chain-stopped.json',dict(time=time.time(),error=type(exc).__name__,detail=str(exc),retry=False,
            stock_unchanged_not_assumed=True,capture_cleanup_not_assumed=True,automatic_recovery=False))
        raise

if __name__=='__main__':main()
