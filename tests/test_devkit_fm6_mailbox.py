"""Copied CPU1 mailbox ownership and timeout faults, with host atomic flags.

This checks the protocol, not pi32v2 memory ordering, ABI, scheduling or speed.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mailbox_faults(tmp_path):
    source = tmp_path / 'test.cc'
    source.write_text(r'''
#include "fm6_pair_mailbox.h"
#include <cassert>
#include <cstring>
static unsigned calls;
extern "C" int fm1_dx7_compute_kernel(fm1_dx7_kernel_job_t *job) {
  ++calls;
  if (job->algorithm < 0 || job->algorithm > 31) return 0;
  ++job->op[0].phase;
  for (int i=0;i<64;++i) job->output[i]=job->op[0].phase+i;
  return 1;
}
struct Time { unsigned now, step; LunarFm6Mailbox *worker; };
static uint32_t tick(void *p) {
  Time &t=*static_cast<Time *>(p);
  if (t.worker) t.worker->WorkerStep();
  unsigned value=t.now; t.now+=t.step; return value;
}
int main() {
  fm1_dx7_kernel_job_t jobs[2]={};
  jobs[0].op[0].phase=10; jobs[1].op[0].phase=20;
  Time t={0xfffffffcu,1,0}; LunarFm6Mailbox m(tick,&t,20); t.worker=&m;
  assert(m.RenderPair(jobs)==1 && !m.disabled() && m.completed_pairs()==1);
  assert(jobs[0].op[0].phase==11 && jobs[1].op[0].phase==21);
  assert(m.WorkerStep()==0);
  assert(m.RenderPair(jobs)==1 && m.completed_pairs()==2);
  assert(jobs[1].output[63]==85);
  // Stalled worker: caller returns and may destroy/reuse its jobs. Only the
  // mailbox's private copy is accessed when the worker eventually completes.
  Time stall={0,1,0}; LunarFm6Mailbox late(tick,&stall,8);
  fm1_dx7_kernel_job_t original=jobs[1];
  assert(!late.RenderPair(jobs) && late.disabled());
  assert(!std::memcmp(&jobs[1],&original,sizeof original));
  std::memset(jobs,0xa5,sizeof jobs);
  fm1_dx7_kernel_job_t sentinel[2]; std::memcpy(sentinel,jobs,sizeof jobs);
  assert(late.WorkerStep()==1 && late.WorkerStep()==0);
  assert(!std::memcmp(jobs,sentinel,sizeof jobs));
  unsigned before=calls; assert(!late.RenderPair(jobs) && calls==before);
  // A completed but rejected worker result is never imported.
  std::memset(jobs,0,sizeof jobs); jobs[1].algorithm=32; original=jobs[1];
  Time reject={0,1,0}; LunarFm6Mailbox bad(tick,&reject,8); reject.worker=&bad;
  assert(!bad.RenderPair(jobs) && bad.disabled());
  assert(!std::memcmp(&jobs[1],&original,sizeof original));
  // Completion after the total deadline is rejected, as is a frozen clock.
  std::memset(jobs,0,sizeof jobs);
  Time slow={0,8,0}; LunarFm6Mailbox expired(tick,&slow,8); slow.worker=&expired;
  assert(!expired.RenderPair(jobs) && expired.disabled());
  Time frozen={0,0,0}; LunarFm6Mailbox stuck(tick,&frozen,8);
  assert(!stuck.RenderPair(jobs) && stuck.disabled());
  assert(stuck.WorkerStep()==1);
  LunarFm6Mailbox invalid(tick,&t,0), nullclock(0,0,8), wide(tick,&t,0x80000000u);
  assert(invalid.disabled() && nullclock.disabled() && wide.disabled());
  assert(!invalid.RenderPair(jobs));
  return 0;
}
''')
    exe = tmp_path / 'mailbox-test'
    subprocess.run(['c++', '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-DLUNAR_MAILBOX_HOST_TEST', '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), str(source),
                    str(ROOT/'firmware/devkit/fm6_pair_mailbox.cc'), '-o', str(exe)],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(exe)], check=True, timeout=10)


def test_bridge_one_time_lifetime_and_late_worker(tmp_path):
    source = tmp_path / 'bridge.cc'
    source.write_text(r'''
#include "fm6_pair_bridge.h"
#include <cassert>
#include <cstring>
extern "C" int fm1_dx7_compute_kernel(fm1_dx7_kernel_job_t *job) {
  ++job->op[0].phase; return 1;
}
static unsigned ticks;
static bool work=true;
static uint32_t tick() {
  if (work) lunar_fm6_pair_worker_step();
  return ticks++;
}
int main() {
  assert(!lunar_fm6_pair_adapter() && lunar_fm6_pair_worker_step()==-1);
  assert(lunar_fm6_pair_disabled() && !lunar_fm6_pair_completed());
  assert(!lunar_fm6_pair_init(0,20) && !lunar_fm6_pair_init(tick,0));
  assert(!lunar_fm6_pair_init(tick,0x80000000u));
  assert(lunar_fm6_pair_init(tick,20));
  const fm1_dx7_kernel_adapter_t *adapter=lunar_fm6_pair_adapter();
  assert(adapter && !lunar_fm6_pair_init(tick,20));
  fm1_dx7_kernel_job_t jobs[2]={};
  assert(adapter->render_pair(adapter->ctx,jobs));
  assert(jobs[0].op[0].phase==1 && jobs[1].op[0].phase==1);
  assert(lunar_fm6_pair_completed()==1 && !lunar_fm6_pair_disabled());
  work=false;
  assert(!adapter->render_pair(adapter->ctx,jobs));
  assert(lunar_fm6_pair_disabled() && lunar_fm6_pair_completed()==1);
  assert(jobs[1].op[0].phase==1);
  std::memset(jobs,0xa5,sizeof jobs);
  fm1_dx7_kernel_job_t sentinel[2];std::memcpy(sentinel,jobs,sizeof jobs);
  assert(lunar_fm6_pair_worker_step()==1 && lunar_fm6_pair_worker_step()==0);
  assert(!std::memcmp(sentinel,jobs,sizeof jobs));
  assert(!lunar_fm6_pair_init(tick,20));
  assert(lunar_fm6_pair_adapter()==adapter);
  assert(!adapter->render_pair(adapter->ctx,jobs));
  return 0;
}
''')
    exe = tmp_path / 'bridge-test'
    subprocess.run(['c++', '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-DLUNAR_MAILBOX_HOST_TEST', '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), str(source),
                    str(ROOT/'firmware/devkit/fm6_pair_mailbox.cc'),
                    str(ROOT/'firmware/devkit/fm6_pair_bridge.cc'), '-o', str(exe)],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(exe)], check=True, timeout=10)
