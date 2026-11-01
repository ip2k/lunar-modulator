/* Fake-only full-capacity two-slot transaction. MIT; no storage/device binding. */
#include "fm1_app_state.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define SLOT 102400u
#define HEADER 32u
#define MARK 0x314b4f43u
static fm1_app_t app;
static unsigned char arena[65536] FM1_APP_ALIGN16, scan_memory[16384] FM1_APP_ALIGN16;
static unsigned char host_memory[1024*1024] FM1_APP_ALIGN16;
static uint8_t expected[FM1_STATE_BIN_MAX],old_payload[FM1_STATE_BIN_MAX];
static uint32_t expected_n,old_n;
typedef struct {
 uint8_t slot[2][SLOT],saved[2][SLOT];
 unsigned operations,fail,partial,begins,writes,reads,commits,aborts,open,index;
 unsigned mutate,reenter,corrupt,short_read,alternative;uint32_t n,generation;
} fake_t;
static fake_t fake;
static uint32_t get32(const uint8_t*p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static int accept(void*c,const fm1_rec_t*r){(void)c;(void)r;return 1;}
typedef struct {const uint8_t *p;uint32_t n;} source_t;
static uint32_t scan_read(void*c,uint32_t off,uint8_t*b,uint32_t n){source_t*s=c;if(off>s->n||n>s->n-off)return 0;memcpy(b,s->p+off,n);return n;}
static int valid(unsigned i){
 const uint8_t*h=fake.slot[i];uint32_t n=get32(h+8);fm1_state_report_t r;
 if(memcmp(h,"LST1",4)||get32(h+28)!=MARK||get32(h+16)!=~get32(h+4)||get32(h+20)||
    get32(h+24)!=fm1_state_crc32(0,h,24)||n>FM1_STATE_BIN_MAX||n<32||
    get32(h+12)!=fm1_state_crc32(0,h+HEADER,n))return 0;
 source_t s={h+HEADER,n};fm1_state_report_init(&r);
 return fm1_state_bin_read_workspace(scan_memory,sizeof scan_memory,scan_read,&s,n,accept,NULL,&r,0);
}
/* -1 empty, -2 ambiguous, otherwise selected slot. */
static int scan(void){
 int a=valid(0),b=valid(1);if(!a)return b?1:-1;if(!b)return 0;
 uint32_t d=get32(fake.slot[1]+4)-get32(fake.slot[0]+4);
 if(!d)return !memcmp(fake.slot[0],fake.slot[1],HEADER+get32(fake.slot[0]+8))?0:-2;
 if(d==0x80000000u)return -2;return d<0x80000000u?1:0;
}
static void snapshot(void){
 int i=scan();assert(i>=0);const uint8_t*h=fake.slot[i];uint32_t n=get32(h+8);
 assert((n==old_n&&!memcmp(h+HEADER,old_payload,n))||(n==expected_n&&!memcmp(h+HEADER,expected,n)));
}
static uint32_t effect(uint8_t*dst,const uint8_t*src,uint32_t n,int erase){
 ++fake.operations;uint32_t take=n;
 if(fake.operations==fake.fail)take=fake.partial==0?0:fake.partial==1?n/2:n;
 if(erase)memset(dst,0xff,take);else memcpy(dst,src,take);
 snapshot();return fake.operations==fake.fail?0:n;
}
static void nested(void);
static int begin(void*ctx,uint32_t n){
 (void)ctx;++fake.begins;assert(!fake.open&&n<=FM1_STATE_BIN_MAX);int chosen=scan();if(chosen<0)return 0;
 fake.index=(unsigned)chosen^1u;fake.generation=get32(fake.slot[chosen]+4)+1u;fake.n=n;
 if(!effect(fake.slot[fake.index],NULL,SLOT,1))return 0;
 fake.open=1;if(fake.mutate==1)app.info.title[0]^=1;if(fake.reenter==1)nested();return 1;
}
static uint32_t write_at(void*ctx,uint32_t off,const uint8_t*b,uint32_t n){
 (void)ctx;++fake.writes;assert(fake.open&&off<=fake.n&&n<=fake.n-off);
 if(fake.mutate==2){app.info.title[0]^=1;fake.mutate=0;}
 if(fake.reenter==2){fake.reenter=0;nested();}
 return effect(fake.slot[fake.index]+HEADER+off,b,n,0);
}
static uint32_t read_at(void*ctx,uint32_t off,uint8_t*b,uint32_t n){
 (void)ctx;++fake.reads;++fake.operations;assert(fake.open&&off<=fake.n&&n<=fake.n-off);
 if(fake.alternative){assert(old_n==fake.n);memcpy(fake.slot[fake.index]+HEADER,old_payload,old_n);fake.alternative=0;}
 if(fake.short_read&&n>1)n=1;
 memcpy(b,fake.slot[fake.index]+HEADER+off,n);
 if(fake.mutate==3){app.info.title[0]^=1;fake.mutate=0;}
 if(fake.reenter==3){fake.reenter=0;nested();}
 if(fake.corrupt){b[0]^=1;fake.corrupt=0;}
 return fake.operations==fake.fail?0:n;
}
static int commit(void*ctx){
 (void)ctx;++fake.commits;assert(fake.open);uint8_t h[32]={0};
 memcpy(h,"LST1",4);put32(h+4,fake.generation);put32(h+8,fake.n);
 put32(h+12,fm1_state_crc32(0,fake.slot[fake.index]+HEADER,fake.n));put32(h+16,~fake.generation);
 put32(h+24,fm1_state_crc32(0,h,24));put32(h+28,MARK);fake.open=0;
 if(fake.reenter==4)nested();
 if(!effect(fake.slot[fake.index],h,28,0))return FM1_APP_STATE_REFUSED;
 if(!effect(fake.slot[fake.index]+28,h+28,4,0))return FM1_APP_STATE_INDETERMINATE;
 return FM1_APP_STATE_COMMITTED;
}
static void abort_stage(void*c){(void)c;++fake.aborts;assert(fake.open);fake.open=0;}
static const fm1_app_state_stage_t ops={begin,write_at,read_at,commit,abort_stage};
static void nested(void){
 fm1_state_report_t r;fm1_app_state_workspace_t w={arena,sizeof arena};unsigned calls=fake.operations;
 assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));assert(r.code==FM1_STATE_BAD&&fake.operations==calls);
}
static void output(void*c,const char*b,size_t n){(void)c;assert(n<=sizeof expected-expected_n);memcpy(expected+expected_n,b,n);expected_n+=(uint32_t)n;}
static void save_expected(void){fm1_state_report_t r;fm1_app_state_workspace_t w={host_memory,sizeof host_memory};expected_n=0;assert(fm1_app_state_save_with_workspace(&app,FM1_STATE_PROJECT,0,2,output,NULL,&w,&r));}
static void seed(unsigned i,uint32_t generation,const uint8_t*b,uint32_t n){
 uint8_t*h=fake.slot[i];memset(h,0xff,SLOT);memset(h,0,HEADER);memcpy(h,"LST1",4);
 put32(h+4,generation);put32(h+8,n);put32(h+12,fm1_state_crc32(0,b,n));put32(h+16,~generation);
 put32(h+24,fm1_state_crc32(0,h,24));put32(h+28,MARK);memcpy(h+HEADER,b,n);
}
static void reset(void){
 memcpy(fake.slot,fake.saved,sizeof fake.slot);
 memset((uint8_t*)&fake+offsetof(fake_t,operations),0,sizeof fake - offsetof(fake_t,operations));
 strcpy(app.info.title,"New project");
}
static int run(void){fm1_state_report_t r;fm1_app_state_workspace_t w={arena,sizeof arena};return fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r);}
static void guards(void){
 fm1_state_report_t r;fm1_app_state_workspace_t w={arena,sizeof arena};
 reset();assert(!fm1_app_state_project_stage(&app,0,&ops,&fake,&w,&r));assert(!fake.begins);
 w.bytes=65535;assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));w.bytes=sizeof arena;
 w.memory=arena+1;assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));w.memory=arena;
 memset(arena,0x5a,sizeof arena);assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,(fm1_state_report_t*)arena));
 for(unsigned i=0;i<sizeof arena;i++)assert(arena[i]==0x5a);
 assert(!fm1_app_state_project_stage(&app,2,&ops,arena,&w,&r));
 memcpy(arena,&ops,sizeof ops);assert(!fm1_app_state_project_stage(&app,2,(const fm1_app_state_stage_t*)arena,&fake,&w,&r));
 fm1_seq_t *seq=app.seq;app.seq=(fm1_seq_t*)arena;assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));app.seq=seq;
 fm1_mod_t *mod=app.mod;app.mod=(fm1_mod_t*)arena;assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));app.mod=mod;
 fm1_engine_t copy=*app.unit[0].e;const fm1_engine_t *e=app.unit[0].e;
 memcpy(arena,&copy,sizeof copy);app.unit[0].e=(fm1_engine_t*)arena;
 assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,&r));app.unit[0].e=e;
 /* A known aliased report is refused without changing the live source. */
 char title[sizeof app.info.title];memcpy(title,app.info.title,sizeof title);
 assert(!fm1_app_state_project_stage(&app,2,&ops,&fake,&w,(fm1_state_report_t*)&app));assert(!memcmp(title,app.info.title,sizeof title));
 assert(!fake.begins&&!fake.writes&&!fake.commits);assert(run()==1);
}
int main(void){
 fm1_app_init(&app,44118);assert(!fm1_app_select(&app,0,fm1_app_find("test-sine")));app.seq=NULL;
 strcpy(app.info.title,"Old project");save_expected();memcpy(old_payload,expected,expected_n);old_n=expected_n;
 memset(&fake,0xff,sizeof fake);seed(0,7,old_payload,old_n);memcpy(fake.saved,fake.slot,sizeof fake.slot);
 reset();save_expected();assert(run()==1);unsigned operations=fake.operations;assert(scan()==1&&fake.commits==1&&!fake.aborts);
 unsigned faults=0;
 for(unsigned i=1;i<=operations;i++)for(unsigned partial=0;partial<3;partial++){
  reset();fake.fail=i;fake.partial=partial;int result=run();assert(result!=1&&!fake.open);
  assert(!memcmp(fake.slot[0],fake.saved[0],SLOT));snapshot();int selected=scan();
  if(result==2){assert(i==operations);assert(selected==(partial==2?1:0));assert(!fake.aborts&&fake.commits==1);}
  else assert(selected==0);
  ++faults;
 }
 for(unsigned i=1;i<=3;i++){reset();fake.mutate=i;assert(!run()&&fake.aborts==1&&!fake.commits&&scan()==0);}
 for(unsigned i=1;i<=4;i++){reset();fake.reenter=i;assert(run()==1&&scan()==1);}
 reset();fake.corrupt=1;assert(!run()&&fake.aborts==1&&!fake.commits&&scan()==0);
 reset();fake.short_read=1;assert(run()==1&&scan()==1);
 reset();fake.alternative=1;assert(!run()&&fake.aborts==1&&!fake.commits&&scan()==0);
 /* Valid alternative candidate does not satisfy the frozen manifest. */
 reset();fake.fail=1;assert(!run()&&!fake.writes&&!fake.commits);
 reset();seed(0,UINT32_MAX,old_payload,old_n);assert(run()==1&&scan()==1&&get32(fake.slot[1]+4)==0);
 reset();seed(1,7,expected,expected_n);assert(scan()==-2);assert(!run()&&!fake.writes);
 reset();seed(1,7+0x80000000u,expected,expected_n);assert(scan()==-2);assert(!run()&&!fake.writes);
 reset();seed(1,7,old_payload,old_n);assert(scan()==0);
 guards();
 printf("fake transaction operations=%u faults=%u geometry=%u bytes; mutations/reentry/corruption/wrap/ambiguity passed\n",operations,faults,2*SLOT);
}
