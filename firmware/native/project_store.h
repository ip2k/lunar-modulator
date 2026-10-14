/* SPDX-License-Identifier: GPL-3.0-only */
/* Relative-offset two-slot project store. Geometry is supplied separately;
 * this header grants no physical flash permission. Audio must remain stopped.
 * Nonzero transport status ends the transaction without automatic retry.
 */
#ifndef LUNAR_PROJECT_STORE_H
#define LUNAR_PROJECT_STORE_H
#include <stdint.h>
#include <string.h>
#define LP_HEADER 32u
#define LP_SECTOR 4096u
#define LP_MAX 98304u
#define LP_MAGIC 0x50524e4cu
#define LP_COMMIT 0x434f4d54u
typedef struct {
 void *ctx;
 int (*read)(void *,uint32_t,void *,uint32_t);
 int (*erase)(void *,uint32_t);
 int (*program)(void *,uint32_t,const void *,uint32_t);
 /* Must validate the complete saved file using the supplied flash range. */
 int (*validate)(void *,uint32_t,uint32_t);
} lunar_project_io;
typedef struct {
 lunar_project_io io;
 uint32_t slot_bytes, base, generation;
 int active, failed;
} lunar_project_store;
static uint32_t lp_word(const uint8_t *p) {
 return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static void lp_put(uint8_t *p,uint32_t v) {
 unsigned i; for(i=0;i<4;i++) p[i]=(uint8_t)(v>>(8u*i));
}
static uint32_t lp_crc(uint32_t c,const uint8_t *p,uint32_t n) {
 unsigned j; c=~c; while(n--) { c^=*p++; for(j=0;j<8;j++) c=(c>>1)^((c&1u)?0xedb88320u:0u); } return ~c;
}
static int lp_hash(lunar_project_store *s,uint32_t off,uint32_t n,uint32_t *hash) {
 uint8_t b[256]; uint32_t c=0,k;
 while(n) { k=n>sizeof b?sizeof b:n;
  if(s->io.read(s->io.ctx,off,b,k)) return -1;
  c=lp_crc(c,b,k); off+=k; n-=k;
 } *hash=c; return 0;
}
/* 0 found; 1 empty; negative: transport/geometry/generation refusal. */
static int lunar_project_scan(lunar_project_store *s,int *slot,uint32_t *generation,uint32_t *length) {
 uint8_t h[2][LP_HEADER]; uint32_t n[2]={0,0},g[2]={0,0},hash,delta; int valid[2]={0,0},i;
 if(!s||!slot||!generation||!length||!s->io.read||s->slot_bytes<LP_SECTOR||
    s->slot_bytes%LP_SECTOR||s->slot_bytes>LP_MAX+LP_SECTOR) return -2;
 for(i=0;i<2;i++) {
  uint32_t base=(uint32_t)i*s->slot_bytes;
  if(s->io.read(s->io.ctx,base,h[i],LP_HEADER)) return -1;
  n[i]=lp_word(h[i]+12); g[i]=lp_word(h[i]+8);
  if(lp_word(h[i])!=LP_MAGIC||lp_word(h[i]+4)!=1u||lp_word(h[i]+20)!=0u||
     lp_word(h[i]+28)!=LP_COMMIT||lp_word(h[i]+24)!=lp_crc(0,h[i],24)||
     !n[i]||n[i]>LP_MAX||n[i]>s->slot_bytes-LP_HEADER) continue;
  if(lp_hash(s,base+LP_HEADER,n[i],&hash)) return -1;
  valid[i]=hash==lp_word(h[i]+16);
 }
 if(!valid[0]&&!valid[1]) { *slot=-1; return 1; }
 i=valid[0]?0:1;
 if(valid[0]&&valid[1]) {
  delta=g[1]-g[0]; if(!delta||delta==0x80000000u) return -3;
  i=delta<0x80000000u?1:0;
 }
 *slot=i; *generation=g[i]; *length=n[i]; return 0;
}
static int lunar_project_begin(lunar_project_store *s,const lunar_project_io *io,uint32_t slot_bytes) {
 int slot,rc; uint32_t gen=0,n=0,off;
 if(!s||!io) return -2;
 memset(s,0,sizeof *s); s->io=*io; s->slot_bytes=slot_bytes;
 if(!io->erase||!io->program||!io->validate) { s->failed=1; return -2; }
 rc=lunar_project_scan(s,&slot,&gen,&n);
 if(rc<0) { s->failed=1; return rc; }
 s->base=rc==1?0u:(uint32_t)(1-slot)*slot_bytes;
 s->generation=rc==1?0u:gen+1u;
 for(off=0;off<slot_bytes;off+=LP_SECTOR)
  if(io->erase(io->ctx,s->base+off)) { s->failed=1; return -1; }
 s->active=1; return 0;
}
/* Compatible with fm1_state_write_at_t; programs split into bounded pages. */
static int lunar_project_write(void *ctx,uint32_t off,const void *p,uint32_t n) {
 lunar_project_store *s=ctx; const uint8_t *b=p; uint32_t k;
 if(!s||!s->active||s->failed||(!p&&n)||off>s->slot_bytes-LP_HEADER||
    n>s->slot_bytes-LP_HEADER-off||off>LP_MAX||n>LP_MAX-off) {
  if(s) s->failed=1;
  return -1;
 }
 while(n) {
  uint32_t at=s->base+LP_HEADER+off;
  k=256u-(at&255u); if(k>n) k=n;
  if(s->io.program(s->io.ctx,at,b,k)) { s->failed=1; return -1; }
  off+=k; b+=k; n-=k;
 } return 0;
}
static int lunar_project_commit(lunar_project_store *s,uint32_t n) {
 uint8_t h[LP_HEADER],check[LP_HEADER]; uint32_t hash,check_hash;
 if(!s||!s->active||s->failed||!n||n>LP_MAX||n>s->slot_bytes-LP_HEADER) return -2;
 s->active=0;
 if(lp_hash(s,s->base+LP_HEADER,n,&hash)||
    s->io.validate(s->io.ctx,s->base+LP_HEADER,n)) { s->failed=1; return -1; }
 memset(h,0,sizeof h); lp_put(h,LP_MAGIC); lp_put(h+4,1u);
 lp_put(h+8,s->generation); lp_put(h+12,n); lp_put(h+16,hash);
 lp_put(h+24,lp_crc(0,h,24)); lp_put(h+28,LP_COMMIT);
 if(s->io.program(s->io.ctx,s->base,h,28)||
    s->io.read(s->io.ctx,s->base,check,28)||memcmp(h,check,28)||
    lp_hash(s,s->base+LP_HEADER,n,&check_hash)||check_hash!=hash||
    s->io.program(s->io.ctx,s->base+28,h+28,4)||
    s->io.read(s->io.ctx,s->base,check,LP_HEADER)||memcmp(h,check,LP_HEADER)) {
  s->failed=1; return -1;
 } return 0;
}
#endif
