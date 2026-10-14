/* SPDX-License-Identifier: MIT */
#include "project_store.h"
#include <assert.h>
#include <stdlib.h>
#define SLOT 4096u
static uint8_t flash[2*SLOT], before[2*SLOT];
static unsigned reads,erases,programs,validated;
static int mode;
static int rd(void *ctx,uint32_t off,void *p,uint32_t n) {
 (void)ctx;assert(off<=sizeof flash&&n<=sizeof flash-off);++reads;
 memcpy(p,flash+off,n);return 0;
}
static int er(void *ctx,uint32_t off) {
 (void)ctx;assert(off<SLOT*2&&!(off%SLOT));++erases;
 memset(flash+off,255,SLOT);return 0;
}
static int wr(void *ctx,uint32_t off,const void *p,uint32_t n) {
 unsigned i;const uint8_t *b=p;(void)ctx;
 assert(off<=sizeof flash&&n<=sizeof flash-off&&n<=256);++programs;
 for(i=0;i<n;i++){assert((flash[off+i]&b[i])==b[i]);flash[off+i]=b[i];}
 return 0;
}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 unsigned slot=off/SLOT;(void)ctx;assert(n==1);++validated;
 if(mode==3&&slot==1)return -1;
 if(mode==4&&slot==0)return -1;
 return flash[off]==0x5a?0:1;
}
static void seed(unsigned slot,uint32_t gen,uint8_t payload) {
 uint8_t *h=flash+slot*SLOT;h[LP_HEADER]=payload;
 memset(h,0,LP_HEADER);lp_put(h,LP_MAGIC);lp_put(h+4,1);
 lp_put(h+8,gen);lp_put(h+12,1);lp_put(h+16,lp_crc(0,h+LP_HEADER,1));
 lp_put(h+24,lp_crc(0,h,24));lp_put(h+28,LP_COMMIT);
}
int main(int argc,char **argv) {
 lunar_project_io io={0,rd,er,wr,validate};lunar_project_store s;
 int slot,rc;uint32_t g,n;uint8_t payload=0x5a;unsigned count;
 assert(argc==2);mode=atoi(argv[1]);assert(mode>=0&&mode<6);
 memset(flash,255,sizeof flash);
 seed(0,10,mode==1||mode==2?0x99:0x5a);
 seed(1,11,mode==0||mode==2?0x99:0x5a);
 memcpy(before,flash,sizeof flash);memset(&s,0,sizeof s);s.io=io;s.slot_bytes=SLOT;
 if(mode==5){s.io.validate=NULL;io.validate=NULL;}
 rc=lunar_project_scan(&s,&slot,&g,&n);
 assert(!erases&&!programs&&!memcmp(before,flash,sizeof flash));
 if(mode<2) {
  assert(!rc&&slot==mode&&g==(uint32_t)(10+mode)&&n==1&&validated==2);
  assert(!lunar_project_begin(&s,&io,SLOT));assert(s.base==(uint32_t)(1-mode)*SLOT);
  assert(erases==1&&!memcmp(before+mode*SLOT,flash+mode*SLOT,SLOT));
  assert(!lunar_project_write(&s,0,&payload,1));assert(!lunar_project_commit(&s,1));
  assert(!lunar_project_scan(&s,&slot,&g,&n));assert(slot==1-mode&&g==(uint32_t)(11+mode));
 } else if(mode==2) {
  assert(rc==1&&slot==-1&&validated==2);
 } else {
  assert(rc==(mode==5?-2:-1));
  assert(lunar_project_begin(&s,&io,SLOT)==rc);
  count=reads;assert(s.failed&&!s.active);
  assert(lunar_project_write(&s,0,&payload,1));assert(lunar_project_commit(&s,1));
  assert(reads==count&&!erases&&!programs&&!memcmp(before,flash,sizeof flash));
 }
 return 0;
}
