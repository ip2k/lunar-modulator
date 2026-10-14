/* SPDX-License-Identifier: MIT */
#include "project_store.h"
#include <assert.h>
#include <stdlib.h>
#define SLOT 4096u
static uint8_t flash[2*SLOT], before[2*SLOT];
static unsigned writes, erases;
static int rd(void *ctx,uint32_t off,void *p,uint32_t n) {
 (void)ctx;assert(off<=sizeof flash&&n<=sizeof flash-off);
 memcpy(p,flash+off,n);return 0;
}
static int er(void *ctx,uint32_t off) {
 (void)ctx;assert(off<SLOT*2&&!(off%SLOT));++erases;
 memset(flash+off,255,SLOT);return 0;
}
static int wr(void *ctx,uint32_t off,const void *p,uint32_t n) {
 unsigned i;const uint8_t *b=p;(void)ctx;
 assert(off<=sizeof flash&&n<=sizeof flash-off&&n<=256);++writes;
 for(i=0;i<n;i++){assert((flash[off+i]&b[i])==b[i]);flash[off+i]=b[i];}
 return 0;
}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 (void)ctx;return n==1&&flash[off]==0x5a?0:-1;
}
/* Fixture construction deliberately supplies CRC-valid committed generations. */
static void seed(unsigned slot,uint32_t gen) {
 uint8_t *h=flash+slot*SLOT;h[LP_HEADER]=0x5a;
 memset(h,0,LP_HEADER);lp_put(h,LP_MAGIC);lp_put(h+4,1);
 lp_put(h+8,gen);lp_put(h+12,1);lp_put(h+16,lp_crc(0,h+LP_HEADER,1));
 lp_put(h+24,lp_crc(0,h,24));lp_put(h+28,LP_COMMIT);
}
int main(int argc,char **argv) {
 static const uint32_t bases[5]={0u,1u,0x7fffffffu,0x80000000u,0xffffffffu};
 static const uint32_t deltas[6]={0u,1u,0x7fffffffu,0x80000000u,0x80000001u,0xffffffffu};
 lunar_project_io io={0,rd,er,wr,validate};lunar_project_store s;
 uint32_t g,n,g0,g1,d;int slot,rc,expected;unsigned id;uint8_t payload=0x5a;
 assert(argc==2);id=(unsigned)atoi(argv[1]);assert(id<30);
 g0=bases[id/6];d=deltas[id%6];g1=g0+d;
 memset(flash,255,sizeof flash);seed(0,g0);seed(1,g1);
 memcpy(before,flash,sizeof flash);memset(&s,0,sizeof s);s.io=io;s.slot_bytes=SLOT;
 rc=lunar_project_scan(&s,&slot,&g,&n);
 if(!d||d==0x80000000u) {
  assert(rc==-3);assert(lunar_project_begin(&s,&io,SLOT)==-3);
  assert(s.failed&&!s.active);assert(!erases&&!writes);
  assert(lunar_project_write(&s,0,&payload,1));assert(lunar_project_commit(&s,1));
  assert(!erases&&!writes&&!memcmp(before,flash,sizeof flash));
 } else {
  expected=d<0x80000000u?1:0;
  assert(!rc&&slot==expected&&g==(expected?g1:g0)&&n==1);
  assert(!erases&&!writes&&!memcmp(before,flash,sizeof flash));
  assert(!lunar_project_begin(&s,&io,SLOT));assert(erases==1);
  assert(s.base==(uint32_t)(1-expected)*SLOT);
  assert(s.generation==(expected?g1:g0)+1u);
  assert(!lunar_project_write(&s,0,&payload,1));assert(!lunar_project_commit(&s,1));
  assert(!lunar_project_scan(&s,&slot,&g,&n));
  assert(slot==1-expected&&g==s.generation&&n==1);
  assert(!memcmp(before+expected*SLOT,flash+expected*SLOT,SLOT));
 }
 return 0;
}
