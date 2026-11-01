/* Actual current-app offline PROJECT staging differential. MIT. */
#include "fm1_app_state.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#ifndef FM1_PROJECT_BASELINE
#define FM1_PROJECT_BASELINE 0
#endif
static FILE *corpus;
static fm1_app_t app;
static unsigned char arena[65536] FM1_APP_ALIGN16;
static unsigned char host_arena[1024*1024] FM1_APP_ALIGN16;
typedef struct {unsigned char bytes[FM1_STATE_CAP_PROJECT];uint32_t n;unsigned begins,writes,reads,commits,aborts;} stage_t;
static stage_t stage, host;
static void host_put(void *ctx,const char*b,size_t n){stage_t*s=ctx;assert(n<=sizeof(s->bytes)-s->n);memcpy(s->bytes+s->n,b,n);s->n+=(uint32_t)n;}
static int begin(void*ctx,uint32_t total){stage_t*s=ctx;s->n=total;++s->begins;memset(s->bytes,0xa5,sizeof(s->bytes));return 1;}
static uint32_t write_at(void*ctx,uint32_t off,const uint8_t*b,uint32_t n){stage_t*s=ctx;assert(off<=s->n&&n<=s->n-off);memcpy(s->bytes+off,b,n);++s->writes;return n;}
static uint32_t read_at(void*ctx,uint32_t off,uint8_t*b,uint32_t n){stage_t*s=ctx;++s->reads;if(off>=s->n)return 0;if(n>s->n-off)n=s->n-off;memcpy(b,s->bytes+off,n);return n;}
static int commit(void*ctx){++((stage_t*)ctx)->commits;return FM1_APP_STATE_COMMITTED;}
static void abort_stage(void*ctx){++((stage_t*)ctx)->aborts;}
static const fm1_app_state_stage_t ops={begin,write_at,read_at,commit,abort_stage};
static unsigned cases;
static void compare(unsigned mode){
 fm1_state_report_t a,b;fm1_app_state_workspace_t hw={host_arena,sizeof(host_arena)},nw={arena,sizeof(arena)};
 memset(&host,0,sizeof(host));memset(&stage,0,sizeof(stage));
 int x=fm1_app_state_save_with_workspace(&app,FM1_STATE_PROJECT,0,(int)mode,host_put,&host,&hw,&a);
 if(corpus){assert(fwrite(&x,sizeof x,1,corpus)==1);assert(fwrite(&a,sizeof a,1,corpus)==1);assert(fwrite(&host.n,sizeof host.n,1,corpus)==1);assert(fwrite(host.bytes,1,host.n,corpus)==host.n);}
#if !FM1_PROJECT_BASELINE
 if(mode>=2){
 int y=fm1_app_state_project_stage(&app,mode,&ops,&stage,&nw,&b);
 if(x!=y||memcmp(&a,&b,sizeof a)||(x&&(host.n!=stage.n||memcmp(host.bytes,stage.bytes,host.n)))){
 fprintf(stderr,"case%u mode%u host%d/%u %s native%d/%u %s bytes%u/%u records%u/%u counters%u,%u,%u/%u,%u,%u\n",cases,mode,x,a.code,a.what,y,b.code,b.what,host.n,stage.n,a.records,b.records,a.defaulted,a.repaired,a.skipped,b.defaulted,b.repaired,b.skipped);assert(0);}
 assert(x ? stage.begins==1&&stage.commits==1&&!stage.aborts : !stage.begins&&!stage.writes&&!stage.commits);
 }
#endif
 ++cases;
}
static void all_modes(void){for(unsigned m=0;m<4;m++)compare(m);}
/* The shared PROJECT extraction must leave every host-only kind unchanged. */
static unsigned host_cases;
static void host_kinds(void) {
 static const struct {unsigned kind;int arg;} kinds[]={
  {FM1_STATE_SOUND,0},{FM1_STATE_SOUND,3},{FM1_STATE_FX,-1},{FM1_STATE_FX,0},
  {FM1_STATE_MODS,0},{FM1_STATE_CLIP,0},{FM1_STATE_CLIP,63},{FM1_STATE_CLIP,-1},
  {FM1_STATE_SETTINGS,0},{FM1_STATE_SET,0}
 };
 for(unsigned k=0;k<sizeof(kinds)/sizeof(kinds[0]);++k)for(int mode=0;mode<4;++mode){
  fm1_state_report_t r;fm1_app_state_workspace_t w={host_arena,sizeof(host_arena)};
  memset(&host,0,sizeof(host));
  int ok=fm1_app_state_save_with_workspace(&app,kinds[k].kind,kinds[k].arg,mode,host_put,&host,&w,&r);
  if(corpus){assert(fwrite(&ok,sizeof ok,1,corpus)==1);assert(fwrite(&r,sizeof r,1,corpus)==1);assert(fwrite(&host.n,sizeof host.n,1,corpus)==1);assert(fwrite(host.bytes,1,host.n,corpus)==host.n);}
  ++host_cases;
 }
}
/* Real dense pool fixture reused from the current PROJECT overflow regression. */
static char text[131072],roundtrip[131072];static size_t text_n;
static void add(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(text + text_n, sizeof text - text_n, fmt, ap);
  va_end(ap);
  assert(n >= 0 && (size_t)n < sizeof text - text_n);
  text_n += (size_t)n;
}
static void dense_set(int oversized) {
  fm1_seq_stats_t st;
  /* Supported caller-selected pools, in the app's existing fixed arena.
   * Capture is runtime history, not saved set data. Trade it for 64 notes;
   * neither the production arena nor any format limit changes. */
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 8);
  if (oversized) {
    lim.capture = 0;
    lim.notes += 64;
  }
  assert(fm1_seq_size(&lim) <= sizeof app.seq_mem);
  app.seq_lim = lim;
  app.seq = fm1_seq_create(app.seq_mem, &lim, 44118);
  assert(app.seq);
  app.seq_host.seq = app.seq;
  text_n = 0;
  add("movy1\nbpm 12000\nswing 99\nlink 1\nkey 11 1\ndq 100\nsg");
  for (unsigned i = 0; i < 64; ++i) add(" 7");
  add("\nse 1\n");
  for (unsigned i = 0; i < 8; ++i) add("sn %u ABCDEF\n", i);
  for (unsigned t = 0; t < 8; ++t) {
    add("tk %u 7 0\ntn %u 4142434445464748494a4b4c4d4e4f50\n", t, t);
    for (unsigned i = 112; i < 128; ++i) add("pm %u %u\n", t, i);
    add("ps %u 127\n", t);
    for (unsigned l = 0; l < 8; ++l) add("au %u %u 127 ABCDEFGHIJKLMNOPQRSTUVW\n", t, l);
    for (unsigned c = 0; c < 8; ++c) {
      add("cl %u %u 256 0 ", t, c);
      for (unsigned i = 0; i < 24u + (unsigned)oversized; ++i)
        add("%s65535:65535:127:127:%u", i ? ";" : "", 232u - (unsigned)oversized + i);
      add("\ncp %u %u 255 255 -36 100\nlk %u %u ", t, c, t, c);
      for (unsigned i = 0; i < 24; ++i) add("%s7:%u:127", i ? ";" : "", 232 + i);
      add("\ntg %u %u ", t, c);
      for (unsigned i = 0; i < 4; ++i) add("%s%u:127:99:255:255:1", i ? ";" : "", 252 + i);
      add("\n");
    }
  }
  assert(fm1_app_seq_import(&app, text, text_n));
  fm1_seq_get_stats(app.seq, &st);
  assert(!st.refused && !st.movy_faults);
  assert(st.notes_used == 1536u + 64u * (unsigned)oversized && st.locks_used == 1536 && st.trigs_used == 256);
  text_n = fm1_seq_export_movy1(app.seq, text, sizeof text);
  printf("real set bytes=%zu notes=%u locks=%u trigs=%u\n", text_n, st.notes_used, st.locks_used, st.trigs_used);
  fflush(stdout);
  assert((text_n >= 65538) == oversized && text_n < sizeof text);
  /* A real current-app set, not a fabricated length: export/import/export
   * roundtrips at the original pool/format limits without refused edits. */
  assert(fm1_app_seq_import(&app, text, text_n));
  fm1_seq_get_stats(app.seq, &st);
  assert(!st.refused && !st.movy_faults);
  size_t n = fm1_seq_export_movy1(app.seq, roundtrip, sizeof roundtrip);
  assert(n == text_n && !memcmp(text, roundtrip, n));
}
static void rich(void){
 uint32_t rng=0x720319u;
 const char *engines[]={"dx7","drums","test-sine"};
 for(unsigned e=0;e<3;e++){
  assert(!fm1_app_select(&app,0,fm1_app_find(engines[e])));
  assert(!fm1_app_select(&app,fm1_app_sound_unit(1),fm1_app_find("test-sine")));
  assert(!fm1_app_select(&app,fm1_app_insert_unit(0,0),fm1_app_find("test-gain")));
  for(unsigned k=0;k<12;k++){
   for(unsigned p=0;p<app.unit[0].e->n_params;p++){
    const fm1_param_t *d=&app.unit[0].e->params[p];rng=rng*1664525u+1013904223u;
    fm1_app_set_param(&app,0,(int)p,d->min+(d->max-d->min)*(float)(rng&65535)/65535.0f);
   }
   for(unsigned p=0;p<8;p++){int kind=fm1_mod_kind_find(p%2?"register":"lfo");assert(kind>=0);assert(fm1_mod_set_kind(app.mod,p,kind)>=0);fm1_mod_set_param(app.mod,p,0,(float)(rng%97));}
   fm1_mod_slot_t cable={64,FM1_MOD_NONE,FM1_MOD_SOUND,0,app.unit[0].e->params[0].uid,8192,-512,0};
   assert(fm1_mod_set_slot(app.mod,0,&cable));
   all_modes();
  }
 }
 memset(&app.midi_map,0,sizeof app.midi_map);app.midi_map.version=1;
 for(unsigned i=0;i<64;i++){char id[64];snprintf(id,sizeof id,"sound1.param.P%u",i);assert(!fm1_midi_map_add(&app.midi_map,id,"keyboard",0,0,(uint8_t)i));}
 all_modes();
 for(unsigned i=0;i<FM1_DX7_USER_SLOTS;i++){app.dx7.loaded[i]=1;memset(app.dx7.voice[i],0,155);memset(app.dx7.voice[i]+145,'A'+i%26,10);}all_modes();
 { const fm1_engine_t *original=app.unit[0].e;fm1_engine_t custom=*original;fm1_param_t params[32];
   assert(original->n_params<=32);memcpy(params,original->params,original->n_params*sizeof(*params));custom.params=params;app.unit[0].e=&custom;
   if(custom.n_params>1){fm1_param_t swap=params[0];params[0]=params[1];params[1]=swap;all_modes();params[1].uid=params[0].uid;all_modes();}
   app.unit[0].e=original;
 }
 {float level=app.level[0];uint32_t nan=0x7fc00000;memcpy(&app.level[0],&nan,4);all_modes();app.level[0]=level;}
 {char title[sizeof app.info.title];memcpy(title,app.info.title,sizeof title);app.info.title[0]=(char)0xff;app.info.title[1]=0;all_modes();memcpy(app.info.title,title,sizeof title);}
 dense_set(0);all_modes();dense_set(1);all_modes();
 assert(!fm1_app_seq_reset(&app,8));
}
int main(int argc,char **argv){
 if(argc==2){corpus=fopen(argv[1],"wb");assert(corpus);}
 fm1_app_init(&app,44118);assert(!fm1_app_select(&app,0,fm1_app_find("test-sine")));
 assert(!fm1_app_select(&app,1,fm1_app_find("test-gain")));assert(fm1_app_seq_demo(&app));
 all_modes();host_kinds();
 strcpy(app.info.title,"quote\" slash\\ tab\t newline\n");
 app.midi_map.version=1;assert(!fm1_midi_map_add(&app.midi_map,"sound1.param.Pitch","keyboard",0,0,60));
 app.dx7.index=0;app.dx7.loaded[0]=1;memset(app.dx7.voice[0],0,155);memset(app.dx7.voice[0]+145,' ',10);
 for(unsigned k=0;k<16;k++){app.unit[0].value[0]=(float)(k*7);app.sound=(int)(k%4);app.mode=(int)(k%9);all_modes();}
 rich();host_kinds();
 app.seq=NULL;all_modes();
 app.unit[0].e=NULL;all_modes();
 if(corpus)assert(!fclose(corpus));
 printf("host-only kind oracle cases=%u\n",host_cases);
#if !FM1_PROJECT_BASELINE
 printf("PROJECT differential cases=%u aux=%zu workspace=%zu reader=%zu\n",cases,fm1_app_state_project_aux_size(),fm1_app_state_workspace_size(FM1_APP_STATE_WORK_PROJECT),fm1_state_bin_reader_size());
#else
 printf("PROJECT baseline cases=%u\n",cases);
#endif
}
