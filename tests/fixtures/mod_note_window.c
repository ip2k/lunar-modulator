/* Compare full modulation runtime and write bytes across note window routing. */
#define main note_window_existing_suite_main
#include CORE_TEST_SOURCE
#undef main
#include <stdlib.h>

static FILE *trace;
static unsigned snapshots, notes, tick_calls, independent_falls;
static void snapshot(fm1_mod_t *m, const fm1_mod_write_t *w, uint32_t n) {
  CHECK(fwrite(&snapshots,sizeof snapshots,1,trace)==1);
  CHECK(fwrite(&n,sizeof n,1,trace)==1);
  CHECK(fwrite(m,sizeof *m,1,trace)==1);
  if(n)CHECK(fwrite(w,sizeof *w,n,trace)==n);
  ++snapshots;if(failed)exit(2);
}
static fm1_mod_t *setup(unsigned seed, unsigned voices) {
  fm1_mod_t *m=make(0,0xa5,seed);fm1_mod_slot_t s;fm1_mod_plan_info_t info;
  for(unsigned sound=0;sound<FM1_MOD_SOUNDS;++sound)
    fm1_mod_bind(m,fm1_mod_sound_unit(sound),&kPolyEngine);
  fm1_mod_default_rack(m);
  s=cable(FM1_MOD_SRC_RAND,FM1_MOD_SOUND,3,.4f);fm1_mod_set_slot(m,0,&s);
  if(voices){
    s=voice_cable(FM1_MOD_SRC_VEL,FM1_MOD_SOUND,3,.4f);fm1_mod_set_slot(m,1,&s);
    s=voice_cable(FM1_MOD_SRC_RAND,FM1_MOD_HOST,FM1_MOD_HOST_PITCH_CUR_UID,.2f);fm1_mod_set_slot(m,2,&s);
    s=gate_voice_cable(FM1_MOD_SRC_TRIG,2,0,1.f);fm1_mod_set_slot(m,3,&s);
  }
  fm1_mod_get_plan(m,&info);if(failed)exit(2);return m;
}
static void note(fm1_mod_t *m,uint64_t at,unsigned sound,unsigned key,unsigned vel,unsigned scheduled) {
  /* Public entry points exercise actual static note_at, including uint64 wrap. */
  if(scheduled){m->blk=at-7u;fm1_mod_sound_note(m,7,sound,(uint8_t)key,(uint8_t)vel);}
  else {m->now=at;fm1_mod_live_sound_note(m,sound,(uint8_t)key,(uint8_t)vel);}
  ++notes;snapshot(m,NULL,0);
}
static void tick_block(fm1_mod_t *m) {
  fm1_mod_write_t w[128];memset(w,0,sizeof w);
  unsigned n=block_v(m,64,w,128);++tick_calls;snapshot(m,w,n);
}
int main(int argc,char **argv) {
  const uint64_t nexts[]={64,UINT64_C(0x100000040),UINT64_MAX-31u,0};
  unsigned dropped_seen=0;
  if(argc!=2)return 3;trace=fopen(argv[1],"wb");if(!trace)return 3;
  K_LFO=fm1_mod_kind_find("lfo");K_ENV=fm1_mod_kind_find("ENV");K_CHN=fm1_mod_kind_find("chance");
  for(unsigned ni=0;ni<4;++ni)for(unsigned ti=0;ti<10;++ti)
  for(unsigned fullness=0;fullness<3;++fullness)for(unsigned voices=0;voices<2;++voices){
    fm1_mod_t *m=setup(117+ni*100+ti,voices);uint64_t next=nexts[ni];
    uint64_t ats[]={0,next-65u,next-64u,next-1u,next,next+1u,next+31u,next+32u,next+1000u,UINT64_MAX};
    uint64_t at=ats[ti];unsigned sound=ti%FM1_MOD_SOUNDS;
    m->next_tick=next;
    /* Valid alternating histories, with a last offset beyond current-note offset.
     * Exercises clamping, inherited window-one level, capacity/drop transitions. */
    for(unsigned g=0;g<MOD_SYS_GATES;++g){
      for(unsigned w=0;w<2;++w){
        unsigned n=fullness==0?0:fullness==1?FM1_MOD_EDGES-1u:FM1_MOD_EDGES;
        fm1_mod_gate_t *q=&m->pend_g[w][g];mod_gate_clear(q,(g+w)&1u);
        for(unsigned j=0;j<n;++j)mod_gate_edge(q,FM1_MOD_TICK-2u+j,
          !fm1_mod_gate_end(q),&m->stats.edges_dropped);
      }
      m->glvl_fed[g]=(uint8_t)fm1_mod_gate_end(&m->pend_g[at<next?0:1][g]);
      /* Independent old timestamps: pending, due, same-frame, sentinel. */
      switch((g+ti)%4){case 0:m->trig_fall[g]=next-1u;break;
        case 1:m->trig_fall[g]=at;break;case 2:m->trig_fall[g]=at+1u;break;
        default:m->trig_fall[g]=MOD_NO_FRAME;break;}
    }
    for(unsigned g=1;g<MOD_SYS_GATES;++g)
      if((g==1 || (g>=20&&g<24))&&m->trig_fall[g]!=MOD_NO_FRAME&&
         m->trig_fall[g]<=at&&((m->trig_fall[g]<next)!=(at<next)))++independent_falls;
    m->rtrg_at=(ti&1)?at:at-1u;
    for(unsigned s=0;s<FM1_MOD_SOUNDS;++s)m->rtrg_at_s[s]=(ti&2)?at:at-1u;
    snapshot(m,NULL,0);
    note(m,at,sound,60,90,0);note(m,at,sound,64,255,1);
    note(m,at+1u,sound,60,127,0);note(m,at+1u,sound,60,0,1);
    note(m,at+1u,sound,64,0,0);
    note(m,at,sound,128,90,0);note(m,at,FM1_MOD_SOUNDS,60,90,1);
    if(m->stats.edges_dropped)dropped_seen++;
  }
  /* Real chronological evolution: per-voice activation, returned start writes,
   * same-frame chords, cross-window retriggers, releases and route removal. */
  for(unsigned voices=0;voices<2;++voices){
    fm1_mod_t *m=setup(991,voices);
    for(unsigned b=0;b<20;++b){
      for(unsigned k=0;k<12;++k){
        fm1_mod_write_t w[32];memset(w,0,sizeof w);
        note(m,m->now,k%4,48+k,90,0);
        unsigned n=fm1_mod_voice_start(m,k%4,48+k,w,32);snapshot(m,w,n);
      }
      tick_block(m);
      for(unsigned k=0;k<12;++k)note(m,m->now,k%4,48+k,0,1);
      tick_block(m);
      if(b==9){fm1_mod_slot_t s;memset(&s,0,sizeof s);s.via=FM1_MOD_NONE;
        fm1_mod_set_slot(m,1,&s);fm1_mod_set_slot(m,2,&s);fm1_mod_set_slot(m,3,&s);snapshot(m,NULL,0);}
    }
  }
  CHECK(independent_falls>0);CHECK(dropped_seen>0);CHECK(tick_calls==80);
  CHECK(fclose(trace)==0);if(failed)return 2;
  printf("{\"pass\":true,\"snapshots\":%u,\"notes\":%u,\"tick_calls\":%u,\"independent_falls\":%u,\"overflow_scenarios\":%u}\n",
    snapshots,notes,tick_calls,independent_falls,dropped_seen);return 0;
}
