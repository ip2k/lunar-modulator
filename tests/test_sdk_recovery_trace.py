"""Owned RAM publication and recovery ordering models; no device IO."""
import ctypes as c
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery_model', ROOT / 'tests/test_recovery_request.py')
MODEL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODEL)
NONCE = bytes(range(16))

@pytest.mark.parametrize('extra,message', [
    (['--recovery-trace-nonce', '00'*16], 'requires --recovery-trace'),
    (['--recovery-trace', '--recovery-trace-nonce', ''], '32 hexadecimal'),
    (['--recovery-trace', '--recovery-trace-nonce', '00'*15], '32 hexadecimal'),
    (['--recovery-trace', '--recovery-trace-nonce', '00'*17], '32 hexadecimal'),
    (['--recovery-trace', '--recovery-trace-nonce', 'gg'*16], '32 hexadecimal'),
])
def test_nonce_arguments_rejected_before_build(tmp_path, extra, message):
    out = tmp_path/'must-not-be-created'
    result = subprocess.run([sys.executable, str(ROOT/'tools/jieli/build-sdk-diagnostic.py'),
        '--sdk', str(tmp_path/'absent-sdk'), '--toolchain', str(tmp_path/'absent-toolchain'),
        '--out', str(out), *extra], capture_output=True, text=True)
    assert result.returncode == 2 and message in result.stderr
    assert not out.exists()

class Record(c.Structure):
    _fields_ = [('magic', c.c_uint32), ('version', c.c_uint16), ('length', c.c_uint16),
        ('nonce', c.c_uint32 * 4), ('phase', c.c_uint32), ('complement', c.c_uint32),
        ('mailbox', c.c_uint32), ('panel', c.c_int32), ('elapsed', c.c_uint32),
        ('heartbeat', c.c_uint32), ('reason', c.c_uint32), ('sys', c.c_uint32),
        ('lsb', c.c_uint32), ('sequence', c.c_uint32)]

@pytest.fixture(scope='module')
def libraries(tmp_path_factory):
    work = tmp_path_factory.mktemp('trace')
    (work / 'recovery_trace_nonce.h').write_text(''.join(
        f'#define LUNAR_SDK_RECOVERY_NONCE_{i} 0x{int.from_bytes(NONCE[4*i:4*i+4], "little"):08x}u\n' for i in range(4)))
    results = []
    for enabled in (False, True):
        target = work / ('enabled.so' if enabled else 'disabled.so')
        cmd = ['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-I'+str(work), str(ROOT / 'firmware/recovery/request.c')]
        if enabled:
            cmd += ['-DLUNAR_SDK_RECOVERY_TRACE', str(ROOT / 'firmware/sdk-diagnostic/recovery_trace.c')]
        subprocess.run([*cmd, '-o', str(target)], check=True)
        lib = c.CDLL(str(target))
        lib.lunar_recovery_bind.argtypes = [c.POINTER(MODEL.State), c.POINTER(MODEL.IO), c.c_uint]
        lib.lunar_recovery_request.argtypes = [c.POINTER(MODEL.State)]
        if enabled:
            lib.lunar_sdk_recovery_trace_before_lock.argtypes = [c.c_int32, *([c.c_uint32]*4)]
        results.append(lib)
    return results


def prepare(lib):
    lib.lunar_sdk_recovery_trace_init()
    lib.lunar_sdk_recovery_trace_before_lock(-3, 20000, 1976, 360000000, 60000000)
    lib.lunar_sdk_recovery_trace_phase(3)
    return Record.in_dll(lib, 'lunar_sdk_recovery_trace_record')

@pytest.mark.parametrize('options,phase,flag', [({},5,1),
    *[({'initial':v},3,0) for v in (1,0x100,2)],
    *[({'corrupt':v},3,0) for v in range(16)],
    *[({'fail_byte':v}, 5 if v==3 else 4,1) for v in (1,2,3)],
    *[({'fail_byte':v,'held_start':True}, 5 if v==3 else 4,1) for v in (1,2,3)]])
def test_trace_preserves_io_and_does_not_fabricate_later_phase(libraries, options, phase, flag):
    off, on = libraries
    record = prepare(on)
    a, b = MODEL.Bus(off, **options), MODEL.Bus(on, **options)
    assert a.request() == b.request()
    assert a.trace == b.trace
    assert a.bytes == b.bytes and a.mailbox == b.mailbox and a.polls == b.polls
    assert record.phase == phase and record.mailbox == flag
    assert record.complement == (~phase & 0xffffffff) and record.sequence % 2 == 0
    prior = bytes(record), b.trace[:]
    assert not b.request()
    assert prior == (bytes(record), b.trace)


def test_layout_initialization_and_payload_frozen_during_locked_phases(libraries):
    on = libraries[1]
    on.lunar_sdk_recovery_trace_init()
    r = Record.in_dll(on, 'lunar_sdk_recovery_trace_record')
    assert c.sizeof(Record)==64 and Record.phase.offset==24 and Record.sequence.offset==60
    assert c.addressof(r)%16==0
    assert (r.magic,r.version,r.length,r.phase,r.sequence)==(0x4c525431,1,64,1,2)
    assert bytes(r)[8:24]==NONCE and r.reason==0xffffffff
    r = prepare(on)
    payload = bytes(r)[36:60]
    assert (r.panel,r.elapsed,r.heartbeat,r.sys,r.lsb)==(-3,20000,1976,360000000,60000000)
    for phase in (4,5,6,7):
        before = r.sequence
        on.lunar_sdk_recovery_trace_phase(phase)
        assert bytes(r)[36:60]==payload and r.sequence==before+2
        assert r.phase==phase and r.complement==(~phase & 0xffffffff)


def test_final_intent_is_committed_after_con_read_before_start(libraries):
    on = libraries[1]
    r = prepare(on)
    phases = []
    class Observed(MODEL.Bus):
        def read(self, ctx, reg):
            phases.append(('read',len(self.bytes),r.phase,r.sequence))
            return super().read(ctx,reg)
        def write(self, ctx, reg, value):
            phases.append(('write',reg,value,r.phase,r.sequence))
            return super().write(ctx,reg,value)
        def get(self, ctx, offset):
            assert r.phase==3 and r.mailbox==0
            return super().get(ctx,offset)
    bus = Observed(on)
    assert bus.request()
    final_dat = next(i for i,e in enumerate(phases) if e[:3]==('write',1,0x10))
    assert phases[final_dat][3]==4
    assert phases[final_dat+1][:3]==('read',3,4)
    assert phases[final_dat+2][0:2]==('write',0)
    assert phases[final_dat+2][3]==5 and phases[final_dat+2][4]%2==0


def test_enabled_missing_strong_trace_object_is_link_failure(tmp_path):
    (tmp_path/'main.c').write_text('#include "request.h"\nint main(void){return lunar_recovery_request(0);}\n')
    result = subprocess.run(['cc','-DLUNAR_SDK_RECOVERY_TRACE','-I'+str(ROOT/'firmware/recovery'),
        str(tmp_path/'main.c'),str(ROOT/'firmware/recovery/request.c'),'-o',str(tmp_path/'missing')],capture_output=True)
    assert result.returncode and b'lunar_sdk_recovery_trace_' in result.stderr


def test_nonreturning_final_start_retains_intent_without_return_code(tmp_path):
    (tmp_path/'recovery_trace_nonce.h').write_text(''.join(f'#define LUNAR_SDK_RECOVERY_NONCE_{i} {i}u\n' for i in range(4)))
    (tmp_path/'main.c').write_text(r'''
#include <setjmp.h>
#include <string.h>
#include "request.h"
#include "recovery_trace.h"
static jmp_buf jump;
static unsigned con, dat, starts;
static unsigned char mailbox[16];
static unsigned rd(void *x,enum lunar_recovery_register r){(void)x;(void)r;return con;}
static void wr(void *x,enum lunar_recovery_register r,unsigned v){(void)x;
 if(r==LUNAR_P33_DAT){dat=v;return;}
 if(v&16u){++starts;if(dat==0x10u){
  if(lunar_sdk_recovery_trace_record.phase!=5 || lunar_sdk_recovery_trace_record.publication_sequence&1u) longjmp(jump,2);
  longjmp(jump,1);}}
 con=v&~18u;}
static void sy(void*x){(void)x;}
static void put(void*x,unsigned o,unsigned char v){(void)x;mailbox[o]=v;}
static unsigned char get(void*x,unsigned o){(void)x;return mailbox[o];}
int main(void){struct lunar_recovery s;struct lunar_recovery_io io={0,rd,wr,sy,put,get};int code;
 lunar_sdk_recovery_trace_init();lunar_sdk_recovery_trace_before_lock(0,20000,1976,360000000,60000000);
 lunar_sdk_recovery_trace_phase(3);if(!lunar_recovery_bind(&s,&io,4))return 3;
 code=setjmp(jump);if(!code){lunar_recovery_request(&s);return 4;}
 return !(code==1 && starts==3 && lunar_sdk_recovery_trace_record.mailbox_verified==1 &&
  lunar_sdk_recovery_trace_record.phase_complement==~5u && !memcmp(mailbox,"usb_update_mode",16));}
''')
    target=tmp_path/'nonreturning'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DLUNAR_SDK_RECOVERY_TRACE',
        '-I'+str(tmp_path),'-I'+str(ROOT/'firmware/recovery'),'-I'+str(ROOT/'firmware/sdk-diagnostic'),
        str(tmp_path/'main.c'),str(ROOT/'firmware/recovery/request.c'),
        str(ROOT/'firmware/sdk-diagnostic/recovery_trace.c'),'-o',str(target)],check=True)
    subprocess.run([str(target)],check=True)
