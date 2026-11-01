/* Actual current-app offline PROJECT staging differential. MIT. */
#include "fm1_app_state.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static fm1_app_t app;
static unsigned char arena[65536] FM1_APP_ALIGN16;
static unsigned char host_arena[1024*1024] FM1_APP_ALIGN16;
typedef struct {unsigned char bytes[FM1_STATE_BIN_MAX];uint32_t n;unsigned begins,writes,reads,commits,aborts;} stage_t;
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
 int y=fm1_app_state_project_stage(&app,mode,&ops,&stage,&nw,&b);
 if(x!=y||memcmp(&a,&b,sizeof a)||(x&&(host.n!=stage.n||memcmp(host.bytes,stage.bytes,host.n)))){
 fprintf(stderr,"case%u mode%u host%d/%u %s native%d/%u %s bytes%u/%u records%u/%u counters%u,%u,%u/%u,%u,%u\n",cases,mode,x,a.code,a.what,y,b.code,b.what,host.n,stage.n,a.records,b.records,a.defaulted,a.repaired,a.skipped,b.defaulted,b.repaired,b.skipped);assert(0);}
 assert(x ? stage.begins==1&&stage.commits==1&&!stage.aborts : !stage.begins&&!stage.writes&&!stage.commits);
 ++cases;
}
int main(void){
 fm1_app_init(&app,44118);assert(!fm1_app_select(&app,0,fm1_app_find("test-sine")));
 assert(!fm1_app_select(&app,1,fm1_app_find("test-gain")));assert(fm1_app_seq_demo(&app));
 compare(2);compare(3);
 strcpy(app.info.title,"quote\" slash\\ tab\t newline\n");
 app.midi_map.version=1;assert(!fm1_midi_map_add(&app.midi_map,"sound1.param.Pitch","keyboard",0,0,60));
 app.dx7.index=0;app.dx7.loaded[0]=1;memset(app.dx7.voice[0],0,155);memset(app.dx7.voice[0]+145,' ',10);
 for(unsigned k=0;k<16;k++){app.unit[0].value[0]=(float)(k*7);app.sound=(int)(k%4);app.mode=(int)(k%9);compare(2);compare(3);}
 app.seq=NULL;compare(2);compare(3);
 app.unit[0].e=NULL;compare(2);compare(3);
 printf("PROJECT differential cases=%u aux=%zu workspace=%zu\n",cases,fm1_app_state_project_aux_size(),fm1_app_state_workspace_size(FM1_APP_STATE_WORK_PROJECT));
}
