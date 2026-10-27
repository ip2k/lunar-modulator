"""Load policy: deterministic ownership, hysteresis and long-run bounds."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("headroom", [False, True])
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
#if HEADROOM
#define policy_init lunar_voice_budget_init_headroom
#else
#define policy_init lunar_voice_budget_init
#endif
struct engine { unsigned limit, calls, refuse; };
static int apply(void *ctx,unsigned n) {
    struct engine *e=(struct engine *)ctx;
    assert(n>=4 && n<=12); ++e->calls;
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
    for(unsigned n=0;n<10000;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
    assert(lunar_voice_budget_feedback(&s,tag++,200000,5,apply,&e)==0);
    for(unsigned n=0;n<64;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)==0);
    assert(s.limit==12 && e.calls==0);
    for(unsigned n=0;n<128;++n)assert(lunar_voice_budget_feedback(&s,tag++,40000,5,apply,&e)>=0);
    assert(s.limit==4 && s.decreases==8 && e.calls==8);
    assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)==0 && s.limit==4);
    for(unsigned n=0;n<10000;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
    assert(s.limit==12 && s.increases==8 && e.calls==16);
    /* 100 complete load/recovery cycles exceed the old 32-event trace cap. */
    for(unsigned cycle=0;cycle<100;++cycle) {
        for(unsigned n=0;n<128;++n)assert(lunar_voice_budget_feedback(&s,tag++,40000,5,apply,&e)>=0);
        assert(s.limit==4);
        for(unsigned n=0;n<10000;++n)assert(lunar_voice_budget_feedback(&s,tag++,20000,5,apply,&e)>=0);
        assert(s.limit==12);
    }
    assert(s.decreases==808 && s.increases==808 && e.calls==1616);
    /* A full queue masks headroom pressure only in the original mode. */
    const uint32_t full_queue_loads[]={30000,40000};
    for(unsigned load=0;load<2;++load) {
        assert(policy_init(&s,34829));
        for(unsigned n=0;n<100;++n) {
            int changed=lunar_voice_budget_feedback(&s,tag++,full_queue_loads[load],6,apply,&e);
            assert(changed>=0);
            if(!HEADROOM)assert(changed==0);
        }
        assert(s.limit==(HEADROOM ? 4u : 12u));
    }
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
    puts("PASS hysteresis, owner refusal, startup, 1616 transitions, saturation and bounds");
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
