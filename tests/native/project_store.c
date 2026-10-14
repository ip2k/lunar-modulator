/* SPDX-License-Identifier: MIT */
#include "project_store.h"
#include <assert.h>
#include <stdlib.h>
static uint8_t flash[2*102400u],before[102400u],data[98304u];
static unsigned ops,fail_at,valid_fail;
static int rd(void *ctx,uint32_t off,void *p,uint32_t n) {
 (void)ctx; assert(off<=sizeof flash&&n<=sizeof flash-off); if(++ops==fail_at) return -1;
 memcpy(p,flash+off,n);return 0;
}
static int er(void *ctx,uint32_t off) {
 (void)ctx; assert(!(off%4096)&&off<sizeof flash); if(++ops==fail_at) return -1;
 memset(flash+off,255,4096);return 0;
}
static int wr(void *ctx,uint32_t off,const void *p,uint32_t n) {
 const uint8_t *b=p; unsigned i; (void)ctx; assert(off<=sizeof flash&&n<=sizeof flash-off&&n<=256);
 if(++ops==fail_at) return -1;
 for(i=0;i<n;i++) { assert((flash[off+i]&b[i])==b[i]);flash[off+i]=b[i]; }return 0;
}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 (void)ctx; assert(off+n<=sizeof flash); return valid_fail?-1:0;
}
int main(int argc,char **argv) {
 lunar_project_store s; lunar_project_io io={0,rd,er,wr,validate};
 unsigned case_id,i,total_ops; int slot,rc; uint32_t gen,n,bytes=102400u;
 assert(argc==2);case_id=(unsigned)atoi(argv[1]);
 for(i=0;i<sizeof data;i++) data[i]=(uint8_t)(i*17u);
 memset(flash,255,sizeof flash);
 assert(!lunar_project_begin(&s,&io,bytes));assert(!lunar_project_write(&s,0,data,sizeof data));
 assert(!lunar_project_commit(&s,sizeof data));assert(!lunar_project_scan(&s,&slot,&gen,&n));
 assert(slot==0&&gen==0&&n==sizeof data);memcpy(before,flash,bytes);
 if(case_id<25) {
  static const unsigned failures[25]={1,2,3,100,384,385,386,387,400,410,411,412,413,500,796,797,798,1180,1181,1182,1183,1400,1566,1567,1568};
  fail_at=ops+failures[case_id];rc=lunar_project_begin(&s,&io,bytes);
  if(!rc) {rc=lunar_project_write(&s,0,data,sizeof data);if(!rc)rc=lunar_project_commit(&s,sizeof data);}
  assert(rc);assert(!memcmp(before,flash,bytes));
 } else if(case_id==25) {
  assert(!lunar_project_begin(&s,&io,bytes));valid_fail=1;
  assert(!lunar_project_write(&s,0,data,sizeof data));assert(lunar_project_commit(&s,sizeof data));
 } else if(case_id==26) {
  assert(!lunar_project_begin(&s,&io,bytes));assert(lunar_project_write(&s,LP_MAX,data,1));
  total_ops=ops;assert(lunar_project_write(&s,0,data,1));assert(ops==total_ops);
 } else if(case_id==27) {
  assert(!lunar_project_begin(&s,&io,bytes));assert(!lunar_project_write(&s,0,data,sizeof data));
  assert(!lunar_project_commit(&s,sizeof data));total_ops=ops;
  assert(lunar_project_commit(&s,sizeof data));assert(ops==total_ops);
  assert(!lunar_project_scan(&s,&slot,&gen,&n));assert(slot==1&&gen==1);
 } else if(case_id==28) {
  assert(lunar_project_begin(&s,&io,bytes+1));assert(!memcmp(before,flash,bytes));
  assert(lunar_project_scan(&s,&slot,&gen,&n));
  memset(&s,0,sizeof s);s.io=io;s.slot_bytes=bytes;
 } else {
  assert(!lunar_project_begin(&s,&io,bytes));assert(!lunar_project_write(&s,0,data,sizeof data));
  assert(!lunar_project_commit(&s,sizeof data));flash[bytes+LP_HEADER+100]^=1;
  assert(!lunar_project_scan(&s,&slot,&gen,&n));assert(slot==0);
 }
 fail_at=0;valid_fail=0;assert(!lunar_project_scan(&s,&slot,&gen,&n));
 assert(!memcmp(before,flash,bytes));return 0;
}
