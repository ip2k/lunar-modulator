"""Focused offline contracts for the opt-in schema-9 measurement path."""
import json
import subprocess
from pathlib import Path
import pytest
from tools.native import diagnostic_telemetry as codec
from tools.native import analyze_diagnostic_telemetry as analyzer
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/native"))
import build_application_probe as builder

ROOT = Path(__file__).resolve().parents[1]


def test_wire_packet_bounds_and_canonical_roundtrip(tmp_path):
    source = tmp_path / 'wire.c'
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
  uint32_t values[LUNAR_RESAMPLER_STAGE_FIELDS];
  for (unsigned i=0; i<LUNAR_RESAMPLER_STAGE_FIELDS; ++i) values[i]=UINT32_MAX-i;
  assert(LUNAR_RESAMPLER_STAGE_FIELDS == 36u);
  assert(LUNAR_RESAMPLER_STAGE_BYTES == 189u);
  assert(LUNAR_RESAMPLER_STAGE_PACKETS == 63u);
  for (unsigned i=0; i<LUNAR_RESAMPLER_STAGE_PACKETS; ++i) {
    uint32_t p=lunar_resampler_stage_packet(values,i);
    assert((p&15u)==(i==62u ? 7u : 4u));
    for (unsigned j=0;j<3;++j) putchar((p>>(8u*(j+1u)))&255u);
  }
  assert(!lunar_resampler_stage_packet(values,63));
}
''')
    exe = tmp_path/'wire'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'firmware/native'),'-I',str(ROOT/'sim/web/src'),str(source),'-o',str(exe)],check=True)
    frame=subprocess.check_output([str(exe)])
    assert len(frame)==codec.RESAMPLER_STAGE_FRAME_BYTES==189
    decoded=codec.decode_capture(frame)[0]
    assert decoded['schema']==9
    assert list(decoded['values'].values())==[0xffffffff-i for i in range(36)]
    with pytest.raises(ValueError): codec.decode_capture(frame[:-1])
    with pytest.raises(ValueError): codec.decode_capture(frame[:12]+b'\x7f'+frame[13:])


def test_sampling_counts_empty_active_tail_and_disabled_equivalence(tmp_path):
    source=tmp_path/'resampler.c'
    source.write_text(r'''
#include "fm1_resampler.h"
#include <assert.h>
#include <stdio.h>
#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
static uint32_t counts[4], stamps, stages[4];
void lunar_resampler_profile_snapshot(fm1_stage_stamp_t *s) { s->ticks=++stamps; s->irq_ticks=0; }
void lunar_resampler_profile_count(uint32_t e,uint32_t c) { assert(e==0 && c<4); ++counts[c]; }
void lunar_resampler_profile_stage(uint32_t e,uint32_t c,const fm1_stage_stamp_t *a,const fm1_stage_stamp_t *b) {
 assert(e==0 && c<4 && b->ticks>a->ticks); ++stages[c];
}
#endif
int main(void) {
 fm1_resampler_t r; assert(fm1_resampler_init(&r,47872.34f,44118.0f));
 for(unsigned f=0;f<4096;++f) {
  fm1_resampler_profile_output_(&r,0);
  unsigned n=fm1_resampler_needed(&r);
  float in[32]; for(unsigned i=0;i<n;++i) in[i]=f>=1024 && f<2048 ? 0.5f : 0;
  fm1_resampler_push_ready_(&r,in,n);
  float out=fm1_resampler_pop_ready_(&r); fwrite(&out,sizeof out,1,stdout);
#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
  if(f==1023) assert(counts[0]==32 && counts[1]==32 && !counts[2] && !counts[3] && !stamps);
#endif
 }
#ifdef LUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE
 assert(counts[0]==128 && counts[1]+counts[2]==128);
 assert(counts[2]>32 && counts[3]>32 && counts[3]<=counts[2]);
 assert(stages[2]==counts[2] && stages[3]==counts[3]);
#endif
}
''')
    outputs=[]
    for enabled in (False,True):
        exe=tmp_path/str(enabled)
        flags=['-DLUNAR_DIAGNOSTIC_RESAMPLER_STAGE_PROFILE=1'] if enabled else []
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',*flags,'-I',str(ROOT/'engines/include'),str(source),'-o',str(exe)],check=True)
        outputs.append(subprocess.check_output([str(exe)]))
        if not enabled:
            symbols=subprocess.check_output(['nm',str(exe)],text=True)
            assert 'lunar_resampler_profile' not in symbols
    assert outputs[0]==outputs[1]


def test_builder_exclusions_and_analyzer_wrap_irq_errors():
    enabled=builder.validate_resampler_stage_profile(True,'song-diagnostic',True,True,True,True,False,False)
    assert enabled['schema']==9 and enabled['packets_per_frame']==63 and enabled['sample_stride']==32
    for index in range(1,8):
        args=[True,'song-diagnostic',True,True,True,True,False,False]
        args[index]='diagnostic' if index==1 else not args[index]
        with pytest.raises(ValueError): builder.validate_resampler_stage_profile(*args)
    values=dict.fromkeys(codec.RESAMPLER_STAGE_FIELDS,0)
    values.update(sample_stride=32,drums_stage1_ticks=0xfffffff0)
    def row(v,t):return json.dumps(dict(event='resampler_stage_frame',schema=9,elapsed_seconds=t,values=v))
    later=dict(values,drums_stage1_ticks=3,irq_overflow_count=1)
    frames=analyzer.analyze_jsonl([row(values,0),row(later,1)])['resampler_stage_frames']
    assert frames[1]['counter_deltas']['drums_stage1_ticks']==19
    assert frames[0]['irq_accounting_valid'] and not frames[1]['irq_accounting_valid']
    assert 'CPU cycles' in frames[0]['timing_units']


def test_report_reserves_complete_frame_and_snapshot_is_coherent():
    source=(ROOT/'firmware/native/app_probe.c').read_text()
    report=source.split('static void diagnostic_resampler_stage_report(void)',1)[1].split('\n#endif',1)[0]
    assert report.index('MQ - LUNAR_RESAMPLER_STAGE_PACKETS') < report.index('midi_out_event(')
    assert 'last_report) < 4000u' in report
    snapshot=source.split('void lunar_resampler_profile_snapshot(',1)[1].split('\n}',1)[0]
    assert snapshot.index('irq_save()') < snapshot.index('fm1_ticks()') < snapshot.index('busy_ticks') < snapshot.index('irq_restore(')
