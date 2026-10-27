/* SPDX-License-Identifier: MIT
 * Directed state/write comparison for the modulation voice lifecycle shortcut.
 * Both variants update the auxiliary flag; the baseline retains every scan. */
#define main v154_existing_suite_main
#include CORE_TEST_SOURCE
#undef main
#include <stddef.h>
#include <stdlib.h>

static FILE *trace;
static unsigned snapshots, restoration_writes;
static int expect_started;
static size_t aux_offset(void) {
#ifdef V154_CANDIDATE
  return offsetof(fm1_mod_t, voice_ever_started);
#else
  return offsetof(fm1_mod_t, reserved);
#endif
}
static void snapshot(fm1_mod_t *m, uint32_t tag,
                     const fm1_mod_write_t *w, uint32_t n) {
  unsigned char copy[sizeof(fm1_mod_t)];
#ifdef V154_CANDIDATE
  CHECK(m->voice_ever_started == expect_started);
#else
  CHECK(m->reserved[0] == 0);
#endif
  if (failed) exit(2);
  memcpy(copy, m, sizeof copy);
  /* ONLY the new monotonic auxiliary byte, never a voice/state/stat field. */
  copy[aux_offset()] = 0;
  CHECK(fwrite(&tag, sizeof tag, 1, trace) == 1);
  CHECK(fwrite(&n, sizeof n, 1, trace) == 1);
  if (n) CHECK(fwrite(w, sizeof *w, n, trace) == n);
  CHECK(fwrite(copy, sizeof copy, 1, trace) == 1);
  ++snapshots;
  if (failed) exit(2);
}
static void start_note(fm1_mod_t *m, unsigned key, unsigned vel, unsigned tag,
                       int expected_activation) {
  fm1_mod_write_t w[32]; uint32_t n;
  memset(w, 0, sizeof w);
  fm1_mod_live_note(m, (uint8_t)key, (uint8_t)vel);
  if (expected_activation) expect_started = 1;
  snapshot(m, tag, NULL, 0);
  n = fm1_mod_voice_start(m, 0, (uint8_t)key, w, 32);
  snapshot(m, tag + 1, w, n);
}
static void ticks(fm1_mod_t *m, unsigned count, unsigned tag) {
  for (unsigned i=0;i<count;++i) {
    fm1_mod_write_t w[128]; memset(w,0,sizeof w);
    uint32_t n=block_v(m,64,w,128);
    snapshot(m,tag+i,w,n);
  }
}
int main(int argc, char **argv) {
  fm1_mod_t *m; fm1_mod_plan_info_t plan; fm1_mod_slot_t s;
  fm1_mod_write_t w[32]; unsigned n; uint64_t restore;
  if(argc!=2) return 3;
  trace=fopen(argv[1],"wb"); if(!trace)return 3;
  K_LFO=fm1_mod_kind_find("lfo");K_ENV=fm1_mod_kind_find("ENV");K_CHN=fm1_mod_kind_find("chance");
  m=make(0,0xa5,117); fm1_mod_bind(m,FM1_MOD_SOUND,&kPolyEngine);
  fm1_mod_default_rack(m);
  s=cable(FM1_MOD_SRC_VEL,FM1_MOD_SOUND,3,0.4f);fm1_mod_set_slot(m,0,&s);
  fm1_mod_get_plan(m,&plan);CHECK(!plan.voice_sounds);
  snapshot(m,1,NULL,0);
  /* All-free scans and same-frame notes, then normal ticks/writes. */
  for(unsigned i=0;i<12;++i)start_note(m,48+i,90,10+2*i,0);
  memset(w,0,sizeof w);n=fm1_mod_voice_writes(m,w,0);CHECK(!n);snapshot(m,40,w,n);
  ticks(m,4,50);CHECK(fm1_mod_voice_count(m)==0);
  for(unsigned why=0;why<3;++why){fm1_mod_reset(m,why);snapshot(m,60+why,NULL,0);}
  /* First route activation must defeat the guard immediately, including dirty build. */
  s=voice_cable(FM1_MOD_SRC_VEL,FM1_MOD_SOUND,3,0.4f);fm1_mod_set_slot(m,1,&s);
  s=voice_cable(FM1_MOD_SRC_RAND,FM1_MOD_HOST,FM1_MOD_HOST_PITCH_UID,0.2f);fm1_mod_set_slot(m,2,&s);
  snapshot(m,70,NULL,0);start_note(m,60,100,71,1);
  CHECK(fm1_mod_voice_count(m)==1);ticks(m,2,80);
  for(unsigned why=0;why<3;++why){fm1_mod_reset(m,why);snapshot(m,90+why,NULL,0);}
  /* The lifetime flag must not depend on serial/age counters avoiding zero. */
  m->vserial=UINT32_MAX;m->vage=UINT32_MAX;snapshot(m,100,NULL,0);
  start_note(m,61,110,101,1);CHECK(m->vserial==0&&m->vage==0);
  /* Remove all per-voice destinations while offsets remain live. */
  memset(&s,0,sizeof s);s.via=FM1_MOD_NONE;
  fm1_mod_set_slot(m,1,&s);fm1_mod_set_slot(m,2,&s);fm1_mod_get_plan(m,&plan);
  CHECK(plan.voice_sounds==0&&plan.n_vdest==0);
  restore=0;for(unsigned i=0;i<FM1_MOD_VOICES;++i)restore|=m->voice[i].restore;
  CHECK(restore!=0);snapshot(m,110,NULL,0);
  memset(w,0,sizeof w);n=fm1_mod_voice_start(m,0,60,w,1);
  CHECK(n==1&&mod_bits(w[0].value)==0);restoration_writes+=n;snapshot(m,111,w,n);
  for(unsigned i=0;i<8;++i){
    memset(w,0,sizeof w);n=fm1_mod_voice_writes(m,w,1);
    for(unsigned j=0;j<n;++j)CHECK(mod_bits(w[j].value)==0);
    restoration_writes+=n;snapshot(m,112+i,w,n);
  }
  CHECK(restoration_writes>=4);
  fm1_mod_live_note(m,60,0);fm1_mod_live_note(m,61,0);snapshot(m,125,NULL,0);
  ticks(m,4,130);CHECK(fm1_mod_voice_count(m)==0);
  /* Flag remains true after complete retirement, rebind and reset. */
  fm1_mod_bind(m,FM1_MOD_SOUND,&kEngine);snapshot(m,140,NULL,0);
  for(unsigned why=0;why<3;++why){fm1_mod_reset(m,why);snapshot(m,141+why,NULL,0);}
  fm1_mod_bind(m,FM1_MOD_SOUND,&kPolyEngine);
  /* Ensure reset callbacks run with real per-voice module instances. */
  s=voice_cable(out_of(2,0),FM1_MOD_SOUND,3,0.5f);fm1_mod_set_slot(m,1,&s);
  start_note(m,64,96,150,1);ticks(m,8,160);
  {unsigned ready=0;for(unsigned i=0;i<FM1_MOD_VOICES;++i)ready|=m->voice[i].ready;CHECK(ready!=0);}
  for(unsigned why=0;why<3;++why){fm1_mod_reset(m,why);snapshot(m,180+why,NULL,0);ticks(m,1,190+why);}
  memset(w,0,sizeof w);n=fm1_mod_voice_clear(m,w,32);snapshot(m,200,w,n);
  /* Allocation/retrigger/steal fallback, always with unchanged original logic. */
  for(unsigned i=0;i<16;++i)start_note(m,36+i,100,210+2*i,1);
  CHECK(m->stats.voice_steals>0);start_note(m,51,100,250,1);ticks(m,2,260);
  fm1_mod_destroy(m);
  /* Only an actual new object lifecycle resets the auxiliary fact. */
  expect_started=0;m=make(0,0xff,117);snapshot(m,270,NULL,0);
  fm1_mod_destroy(m);CHECK(!fclose(trace));
  if(failed)return 2;
  printf("{\"pass\":true,\"snapshots\":%u,\"restoration_writes\":%u,\"sizeof_mod\":%zu,\"aux_offset\":%zu}\n",
         snapshots,restoration_writes,sizeof(fm1_mod_t),aux_offset());
  return 0;
}
