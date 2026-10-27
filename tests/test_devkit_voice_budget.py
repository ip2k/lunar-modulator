"""Load policy: deterministic ownership, hysteresis and long-run bounds."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("headroom", [0, 1, 2, 3], ids=["original", "headroom85", "burst75", "burst65"])
@pytest.mark.parametrize("sanitize", [False, True])
def test_render_owner_feedback(tmp_path, sanitize, headroom):
    cc = os.environ.get("CC", "cc")
    if not shutil.which(cc):
        pytest.skip("C compiler unavailable")
    source = tmp_path / "policy.c"
    source.write_text(r'''
#include "voice_budget.h"
#include <assert.h>
#include <stdio.h>
#if HEADROOM == 3
#define policy_init lunar_voice_budget_init_burst_safety
#elif HEADROOM == 2
#define policy_init lunar_voice_budget_init_burst_reserve
#elif HEADROOM
#define policy_init lunar_voice_budget_init_headroom
#else
#define policy_init lunar_voice_budget_init
#endif
#define FLOOR (HEADROOM == 3 ? 2u : 4u)
#define CHANGES (12u - FLOOR)
#define RECOVERY_SAMPLES (HEADROOM == 3 ? 14000u : 10000u)
struct engine { unsigned limit, calls, refuse; };
static int apply(void *ctx,unsigned n) {
    struct engine *e=(struct engine *)ctx;
    assert(n>=FLOOR && n<=12); ++e->calls;
    if(e->refuse)return 0;
    e->limit=n;return 1;
}
int main(void) {
    lunar_voice_budget_t s;
    struct engine e={12,0,0};
    assert(!policy_init(0,34829));
    assert(!policy_init(&s,0));
    assert(!policy_init(&s,24000000));
    assert(policy_init(&s,34829));
    uint32_t tag=0;
    for(;tag<16;++tag)assert(lunar_voice_budget_feedback(&s,tag,200000,1,apply,&e)==0);
    assert(s.limit==12 && e.calls==0);
    for(unsigned n=0;n<RECOVERY_SAMPLES;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
    assert(lunar_voice_budget_feedback(&s,tag++,200000,5,apply,&e)==0);
    for(unsigned n=0;n<64;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)==0);
    assert(s.limit==12 && e.calls==0);
    for(unsigned n=0;n<128;++n)assert(lunar_voice_budget_feedback(&s,tag++,40000,5,apply,&e)>=0);
    assert(s.limit==FLOOR && s.decreases==CHANGES && e.calls==CHANGES);
    assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)==0 && s.limit==FLOOR);
    for(unsigned n=0;n<RECOVERY_SAMPLES;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
    assert(s.limit==12 && s.increases==CHANGES && e.calls==2*CHANGES);
    /* 100 complete load/recovery cycles exceed the old 32-event trace cap. */
    for(unsigned cycle=0;cycle<100;++cycle) {
        for(unsigned n=0;n<128;++n)assert(lunar_voice_budget_feedback(&s,tag++,40000,5,apply,&e)>=0);
        assert(s.limit==FLOOR);
        for(unsigned n=0;n<RECOVERY_SAMPLES;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
        assert(s.limit==12);
    }
    assert(s.decreases==101*CHANGES && s.increases==101*CHANGES && e.calls==202*CHANGES);
    /* The burst profile reserves time even when a full queue masks pressure.
       A 75% load is above its recovery threshold, so it cannot oscillate back. */
    assert(policy_init(&s,34829));
    for(unsigned n=0;n<128;++n)assert(lunar_voice_budget_feedback(&s,tag++,28000,6,apply,&e)>=0);
    assert(s.limit==(HEADROOM>=2 ? FLOOR : 12u));
    if(HEADROOM>=2) {
        for(unsigned n=0;n<4096;++n)assert(lunar_voice_budget_feedback(&s,tag++,26000,6,apply,&e)==0);
        assert(s.limit==FLOOR && s.increases==0);
        for(unsigned n=0;n<RECOVERY_SAMPLES;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,6,apply,&e)>=0);
        assert(s.limit==12 && s.increases==CHANGES);
    }
    /* A full queue masks headroom pressure only in the original mode. */
    const uint32_t full_queue_loads[]={30000,40000};
    for(unsigned load=0;load<2;++load) {
        assert(policy_init(&s,34829));
        for(unsigned n=0;n<100;++n) {
            int changed=lunar_voice_budget_feedback(&s,tag++,full_queue_loads[load],6,apply,&e);
            assert(changed>=0);
            if(!HEADROOM)assert(changed==0);
        }
        assert(s.limit==(HEADROOM ? FLOOR : 12u));
    }
#if HEADROOM == 3
    /* Exact strict boundaries and 1024-observation recovery of the soak policy. */
    assert(policy_init(&s,10000));
    for(unsigned n=0;n<16;++n)assert(lunar_voice_budget_feedback(&s,tag++,6500,6,apply,&e)==0);
    assert(s.limit==12 && s.pressure==0);
    s.mean=6501;
    for(unsigned n=0;n<3;++n)assert(lunar_voice_budget_feedback(&s,tag++,6501,6,apply,&e)==0);
    assert(lunar_voice_budget_feedback(&s,tag++,6501,6,apply,&e)==1 && s.limit==11);
    s.mean=6000;
    for(unsigned n=0;n<2048;++n)assert(lunar_voice_budget_feedback(&s,tag++,6000,6,apply,&e)==0);
    assert(s.limit==11 && s.recover==0);
    s.mean=5999;
    for(unsigned n=0;n<1023;++n)assert(lunar_voice_budget_feedback(&s,tag++,5999,6,apply,&e)==0);
    assert(lunar_voice_budget_feedback(&s,tag++,5999,6,apply,&e)==1 && s.limit==12);
#endif
    assert(policy_init(&s,34829));
    assert(lunar_voice_budget_feedback(&s,tag++,40000,1,apply,&e)==1 && s.limit==11);
    /* Refused engine changes never advance the controller's admitted cap. */
    e.refuse=1;
    assert(lunar_voice_budget_feedback(&s,tag++,40000,1,apply,&e)==-1);
    assert(s.limit==11 && s.failed);
    unsigned calls=e.calls;
    assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)==-1 && e.calls==calls);
    assert(policy_init(&s,34829));
    assert(lunar_voice_budget_feedback(&s,16,24000000,5,apply,&e)==-1 && s.failed);
    assert(policy_init(&s,34829));
    assert(lunar_voice_budget_feedback(&s,16,1000,5,0,&e)==-1 && s.failed);
    assert(policy_init(&s,34829));
    s.decreases=UINT32_MAX;e.refuse=0;
    assert(lunar_voice_budget_feedback(&s,16,40000,1,apply,&e)==1);
    assert(s.decreases==UINT32_MAX);
    puts("PASS hysteresis, owner refusal, startup, long-run transitions, saturation and bounds");
}
''')
    exe = tmp_path / "policy"
    flags = [f"-DHEADROOM={int(headroom)}", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror"]
    if sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run([cc, *flags, "-I", str(ROOT / "firmware/devkit"),
                    str(source), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=30)
    assert result.stdout.startswith("PASS hysteresis"), result.stdout
