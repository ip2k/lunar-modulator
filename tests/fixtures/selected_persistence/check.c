/* MIT. Actual selected-app staging over the EXISTING host transaction fake.
 * Include its model/helpers rather than maintain a second publication protocol.
 * Its original broad fixture remains independently runnable and unchanged. */
#define main native_transaction_original_main
#include "../native_state/transaction.c"
#undef main
#include "selected_interactive_app.h"
#include "diagnostic_app.h"
#include "selected_project.h"
#include "selected_project_blob.h"
#include <stdlib.h>
#include <math.h>

static unsigned char oracle_sound[16384] FM1_APP_ALIGN16;
static fm1_app_arena_t oracle_arenas[FM1_APP_UNITS];
static fm1_state_report_t host_report;
static unsigned char before_app[sizeof(fm1_app_t)], before_sound[16384];
static unsigned callbacks, guard_checks, inject_fault, injected, probe_reentry;
static unsigned hook_counts[6];
static const fm1_app_state_stage_t selected_ops;

static void unchanged(void) {
  const fm1_app_t *a=lunar_diagnostic_state();
  assert(!memcmp(before_app,a,sizeof *a));
  assert(!memcmp(before_sound,a->unit[0].mem,sizeof before_sound));
}
static void take_snapshot(void) {
  const fm1_app_t *a=lunar_diagnostic_state();
  memcpy(before_app,a,sizeof *a);
  assert(a->unit[0].cap==sizeof before_sound);
  memcpy(before_sound,a->unit[0].mem,sizeof before_sound);
}
static void hook(unsigned phase) {
  ++callbacks; ++hook_counts[phase];
  if(probe_reentry) {
    int32_t untouched[128]; memset(untouched,0x5a,sizeof untouched);
    int32_t copy[128]; memcpy(copy,untouched,sizeof copy);
    lunar_input_t e={0,LUNAR_INPUT_ENCODER,FM1_ENC_KNOB1,1};
    unsigned ops_before=fake.operations, callbacks_before=callbacks;
    fm1_state_report_t nested_report, copy_report;
    memset(&nested_report,0x5a,sizeof nested_report); copy_report=nested_report;
    assert(lunar_selected_interactive_apply(NULL,&e)==-1);
    assert(lunar_selected_interactive_render(NULL,untouched)==-1);
    assert(!memcmp(untouched,copy,sizeof copy));
    assert(!lunar_selected_interactive_draw(NULL,1));
    lunar_diagnostic_key(0,1); lunar_diagnostic_note(72,100,1);
    lunar_diagnostic_knob(FM1_ENC_KNOB1,1);
    assert(lunar_diagnostic_init()==-1);
    assert(lunar_diagnostic_render(untouched,64)==-1);
    /* Even invalid/reentrant render must not create a diagnostic fault. */
    assert(lunar_diagnostic_render(NULL,65)==-1);
    assert(lunar_selected_interactive_stage(2,&selected_ops,&fake,&nested_report)==0);
    assert(!memcmp(&nested_report,&copy_report,sizeof nested_report));
    assert(callbacks==callbacks_before && fake.operations==ops_before);
    unchanged(); ++guard_checks;
  }
  if(inject_fault==phase && !injected) {
    injected=1; lunar_diagnostic_fault(77);
  }
}
static int selected_begin(void *c,uint32_t n) {
  int r=begin(c,n); hook(1); return r;
}
static uint32_t selected_write(void*c,uint32_t off,const uint8_t*b,uint32_t n) {
  uint32_t r=write_at(c,off,b,n); hook(2); return r;
}
static uint32_t selected_read(void*c,uint32_t off,uint8_t*b,uint32_t n) {
  uint32_t r=read_at(c,off,b,n); hook(3); return r;
}
static int selected_commit(void*c) { int r=commit(c); hook(4); return r; }
static void selected_abort(void*c) { abort_stage(c); hook(5); }
static const fm1_app_state_stage_t selected_ops={
  selected_begin,selected_write,selected_read,selected_commit,selected_abort
};
static void reset_candidate(void) {
  memcpy(fake.slot,fake.saved,sizeof fake.slot);
  memset((uint8_t*)&fake+offsetof(fake_t,operations),0,sizeof fake - offsetof(fake_t,operations));
  callbacks=0; memset(hook_counts,0,sizeof hook_counts);
}
static void expected_save(unsigned mode) {
  fm1_app_state_workspace_t w={host_memory,sizeof host_memory}; expected_n=0;
  assert(fm1_app_state_save_with_workspace(&app,FM1_STATE_PROJECT,0,(int)mode,
                                         output,NULL,&w,&host_report));
}
static int stage_save(unsigned mode,fm1_state_report_t *r) {
  take_snapshot();
  int result=lunar_selected_interactive_stage(mode,&selected_ops,&fake,r);
  unchanged(); return result;
}
static unsigned records,params,views,sessions,sets;
static int decoded(void*c,const fm1_rec_t*r) {
  (void)c; ++records;
  if(r->type==FM1_REC_HEAD) assert(r->u.head.kind==FM1_STATE_PROJECT);
  if(r->type==FM1_REC_PARAM && r->role==FM1_ROLE_SOUND && r->sound==0) ++params;
  if(r->type==FM1_REC_VIEW) ++views;
  if(r->type==FM1_REC_SESSION) ++sessions;
  if(r->type==FM1_REC_LINE) ++sets;
  return 1;
}
static void check_candidate(unsigned mode) {
  int chosen=scan(); assert(chosen==1);
  const uint8_t *bytes=fake.slot[chosen]+HEADER;
  assert(get32(fake.slot[chosen]+8)==expected_n && !memcmp(bytes,expected,expected_n));
  source_t source={bytes,expected_n}; fm1_state_report_t r;
  records=params=views=sessions=sets=0;
  assert(fm1_state_bin_read_workspace(scan_memory,sizeof scan_memory,
      scan_read,&source,expected_n,decoded,NULL,&r,0));
  assert(r.code==FM1_STATE_OK && !r.skipped && !r.unknown && !r.repaired);
  assert(params==14 && sessions==1 && views==(mode==2) && sets);
  assert(records>30); /* Full current PROJECT, not the narrow starter shape. */
}
static void compare_pcm(void) {
  int32_t pcm[128];
  assert(!lunar_selected_interactive_render(NULL,pcm));
  const float *ref=fm1_app_render(&app,64); unsigned nonzero=0;
  for(unsigned i=0;i<128;++i) {
    float f=ref[i]; assert(isfinite(f));
    int32_t want=(f>=1?32767:f<=-1?-32767:(int32_t)(f*32767.0f))*128;
    assert(pcm[i]==want); nonzero|=pcm[i]!=0;
  }
  assert(nonzero);
}
static void apply_both(lunar_input_t e) {
  assert(!lunar_selected_interactive_apply(NULL,&e));
  if(e.kind==LUNAR_INPUT_KEY) fm1_app_key(&app,e.id,e.value,100);
  else if(e.kind==LUNAR_INPUT_BUTTON) fm1_app_button(&app,e.id,e.value);
  else fm1_app_encoder(&app,e.id,e.value);
}
static void initialize(void) {
  fm1_state_report_t early, copy; memset(&early,0x5a,sizeof early);copy=early;
  assert(!lunar_selected_interactive_stage(2,&selected_ops,&fake,&early));
  assert(!memcmp(&early,&copy,sizeof early)&&!callbacks);
  assert(!lunar_diagnostic_init());
  oracle_arenas[0]=(fm1_app_arena_t){oracle_sound,sizeof oracle_sound};
  assert(!fm1_app_init_arenas(&app,LUNAR_DIAGNOSTIC_RATE,oracle_arenas));
  fm1_app_load_opts_t opts;fm1_app_load_opts_init(&opts);
  opts.kind=FM1_STATE_PROJECT;opts.flags=FM1_APP_LOAD_QUIET;
  fm1_app_state_report_t report;
  fm1_app_state_workspace_t work={host_memory,sizeof host_memory};
  fm1_app_state_mem_t source={lunar_selected_project_blob,lunar_selected_project_blob_bytes};
  assert(fm1_app_state_load_with_workspace(&app,fm1_app_state_mem_read,&source,
      source.n,&opts,&work,&report));
  assert(!report.r.code);
  expected_save(2); memcpy(old_payload,expected,expected_n);old_n=expected_n;
  memset(&fake,0xff,sizeof fake);seed(0,7,old_payload,old_n);
  memcpy(fake.saved,fake.slot,sizeof fake.slot);reset_candidate();
  /* The same actual adapter calls used by A's owner, with no IRQ/platform
   * started: this fixture is the sole offline owner for the entire operation. */
  apply_both((lunar_input_t){0,LUNAR_INPUT_ENCODER,FM1_ENC_KNOB1,3});
  apply_both((lunar_input_t){0,LUNAR_INPUT_KEY,0,1});
  compare_pcm();
  assert(!lunar_diagnostic_state()->store_ready);
}
static void narrow_loader_stays_narrow(void) {
  static fm1_app_t cold; static unsigned char cold_sound[16384] FM1_APP_ALIGN16;
  fm1_app_arena_t a[FM1_APP_UNITS]={{0}};a[0]=(fm1_app_arena_t){cold_sound,sizeof cold_sound};
  memset(&cold,0,sizeof cold);
  assert(!fm1_app_init_arenas(&cold,LUNAR_DIAGNOSTIC_RATE,a));
  static unsigned char snap[sizeof cold];memcpy(snap,&cold,sizeof cold);
  fm1_state_report_t r;
  assert(!lunar_selected_project_load(&cold,expected,expected_n,scan_memory,sizeof scan_memory,&r));
  assert(!memcmp(snap,&cold,sizeof cold)&&!cold.unit[0].e);
}
int main(int argc,char **argv) {
  assert(argc==2);initialize();
  fm1_state_report_t r;
  if(!strcmp(argv[1],"positive")) {
    probe_reentry=1;
    for(unsigned mode=2;mode<=3;++mode) {
      expected_save(mode);reset_candidate();
      assert(stage_save(mode,&r)==1 && fake.commits==1 && !fake.aborts);
      assert(!memcmp(&r,&host_report,sizeof r));check_candidate(mode);
      narrow_loader_stays_narrow();compare_pcm();
    }
    expected_save(2);reset_candidate();assert(stage_save(2,&r)==1);
    unsigned operations=fake.operations,faults=0;
    probe_reentry=0;
    for(unsigned i=1;i<=operations;++i)for(unsigned partial=0;partial<3;++partial) {
      reset_candidate();fake.fail=i;fake.partial=partial;
      int result=stage_save(2,&r);assert(result!=1&&!fake.open);
      assert(!memcmp(fake.slot[0],fake.saved[0],SLOT));snapshot();
      if(result==2)assert(i==operations&&!fake.aborts&&fake.commits==1);
      else assert(scan()==0);
      ++faults;
    }
    reset_candidate();fake.short_read=1;assert(stage_save(2,&r)==1);
    reset_candidate();fake.corrupt=1;assert(!stage_save(2,&r)&&fake.aborts==1&&!fake.commits);
    reset_candidate();assert(!stage_save(0,&r)&&!fake.begins&&!callbacks);
    /* Original ops/report alias remains refused despite the callback bridge. */
    fm1_app_state_stage_t mutable_ops=selected_ops, saved_ops=mutable_ops;
    assert(!lunar_selected_interactive_stage(2,&mutable_ops,&fake,(fm1_state_report_t*)&mutable_ops));
    assert(!memcmp(&mutable_ops,&saved_ops,sizeof mutable_ops));
    take_snapshot();
    assert(!lunar_selected_interactive_stage(2,&selected_ops,&fake,(fm1_state_report_t*)lunar_diagnostic_state()));
    unchanged();
    compare_pcm();assert(!lunar_diagnostic_status());
    assert(!lunar_diagnostic_state()->store_ready);
    printf("selected actual-app modes2/3 bytes/full reports/shared reader/PCM; %u operations %u partial faults, %u guarded hook calls passed\n",operations,faults,guard_checks);
  } else {
    inject_fault=(unsigned)atoi(argv[1]);assert(inject_fault>=1&&inject_fault<=6);
    expected_save(2);reset_candidate();probe_reentry=1;
    if(inject_fault==5)fake.fail=2; /* opened write failure -> abort hook */
    if(inject_fault==6) { lunar_diagnostic_fault(77);injected=1; }
    int result=stage_save(2,&r);
    assert(injected && lunar_diagnostic_status()==77 && !fake.open);
    if(inject_fault==4) assert(result==2&&fake.commits==1&&!fake.aborts&&scan()==1);
    else { assert(result==0&&!fake.commits&&scan()==0);assert(fake.aborts==(inject_fault==6?0:1)); }
    unsigned calls=callbacks;
    assert(!lunar_selected_interactive_stage(2,&selected_ops,&fake,&r)&&callbacks==calls);
    int32_t pcm[128];memset(pcm,0x5a,sizeof pcm);
    assert(lunar_selected_interactive_render(NULL,pcm)==-1);
    for(unsigned i=0;i<128;++i)assert(!pcm[i]);
    printf("selected actual-app sticky fault at phase%u: result%d callbacks%u commits%u aborts%u\n",inject_fault,result,callbacks,fake.commits,fake.aborts);
  }
  return 0;
}
