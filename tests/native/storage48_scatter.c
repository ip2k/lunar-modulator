/* SPDX-License-Identifier: GPL-3.0-only */
/* Proposed geometry in an in-memory backend only; no device admission. */
#include "extent_io.h"
#include "project_store.h"
#include <assert.h>
#include <stdio.h>
#define FLASH_BYTES 1048576u
#define SLOT 49152u
static uint8_t flash[FLASH_BYTES], body[SLOT-LP_HEADER], observed[SLOT];
static lunar_extent_io map;
static unsigned mutations, fail_at;
static int rd(void *ctx,uint32_t at,void *out,uint32_t n) {
 (void)ctx; assert(at<=FLASH_BYTES&&n<=FLASH_BYTES-at);
 memcpy(out,flash+at,n); return 0;
}
static int er(void *ctx,uint32_t at) {
 (void)ctx; assert(!(at%LE_SECTOR)&&at<=FLASH_BYTES-LE_SECTOR);
 if(++mutations==fail_at) { memset(flash+at,255,LE_SECTOR/2); return -1; }
 memset(flash+at,255,LE_SECTOR); return 0;
}
static int wr(void *ctx,uint32_t at,const void *data,uint32_t n) {
 const uint8_t *p=data; uint32_t i; int fail;
 (void)ctx; assert(at<=FLASH_BYTES&&n<=FLASH_BYTES-at);
 assert(n<=256&&(at&255u)+n<=256);
 fail=++mutations==fail_at; if(fail) n/=2;
 for(i=0;i<n;i++) { assert((flash[at+i]&p[i])==p[i]); flash[at+i]=p[i]; }
 return fail?-1:0;
}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 /* Journal CRC validates the bytes; do not compare with the replacement body. */
 if(n!=sizeof body||lunar_extent_read(ctx,off,observed,n)) return -1;
 return 0;
}
static const lunar_extent_backend backend={0,rd,er,wr};
static const lunar_extent extents[]={
 {0xd9000,0x7000},{0xe5000,0x4000},{0xea000,0x1000},{0xeb000,0xc000}
};
static const lunar_extent protected_ranges[]={
 {0,0xd9000},{0xe0000,0x5000},{0xe9000,0x1000},{0xf7000,0x9000}
};
static void guards(void) {
 uint32_t i,j; int writable;
 for(i=0;i<FLASH_BYTES;i++) {
  writable=0;
  for(j=0;j<4;j++) if(i>=extents[j].base&&i-extents[j].base<extents[j].bytes) writable=1;
  if(!writable) assert(flash[i]==0xa5);
 }
}
static void setup(void) {
 memset(flash,0xa5,sizeof flash); mutations=fail_at=0;
 assert(!lunar_extent_init(&map,&backend,extents,4,protected_ranges,4,FLASH_BYTES));
 assert(map.bytes==2*SLOT);
}
static void crossings(void) {
 const uint32_t logical[]={0x7000,0xb000,0xc000};
 const uint32_t left[]={0xe0000,0xe9000,0xeb000};
 const uint32_t right[]={0xe5000,0xea000,0xeb000};
 uint8_t bytes[128],out[128]; unsigned i,j;
 setup(); memset(bytes,0x3c,sizeof bytes);
 for(i=0;i<3;i++) {
  assert(!lunar_extent_erase(&map,logical[i]-LE_SECTOR));
  assert(!lunar_extent_erase(&map,logical[i]));
  assert(!lunar_extent_program(&map,logical[i]-64,bytes,sizeof bytes));
  assert(!memcmp(flash+left[i]-64,bytes,64));
  assert(!memcmp(flash+right[i],bytes+64,64));
  assert(!lunar_extent_read(&map,logical[i]-64,out,sizeof out));
  for(j=0;j<sizeof out;j++) assert(out[j]==0x3c);
 }
 guards();
}
static int save(lunar_project_store *s,const lunar_project_io *io) {
 int rc=lunar_project_begin(s,io,SLOT);
 if(!rc) rc=lunar_project_write(s,0,body,sizeof body);
 if(!rc) rc=lunar_project_commit(s,sizeof body);
 return rc;
}
static void recovery(unsigned target_slot) {
 lunar_project_store s;
 lunar_project_io io={&map,lunar_extent_read,lunar_extent_erase,lunar_extent_program,validate};
 uint32_t gen,n,i; int slot; unsigned operations,cut;
 /* Measure the complete replacement before sweeping every mutation boundary. */
 setup(); memset(body,0x35,sizeof body); assert(!save(&s,&io));
 if(!target_slot) assert(!save(&s,&io));
 mutations=0; memset(body,0x6a,sizeof body); assert(!save(&s,&io)); operations=mutations;
 for(cut=1;cut<=operations;cut++) {
  setup(); memset(body,0x35,sizeof body); assert(!save(&s,&io));
  if(!target_slot) assert(!save(&s,&io));
  mutations=0; fail_at=cut; memset(body,0x6a,sizeof body); assert(save(&s,&io)<0);
  fail_at=0;
  assert(!lunar_project_scan(&s,&slot,&gen,&n));
  assert(slot==(int)(1-target_slot)&&gen==(target_slot?0u:1u)&&n==sizeof body);
  assert(!lunar_extent_read(&map,(uint32_t)slot*SLOT+LP_HEADER,observed,n));
  for(i=0;i<n;i++) assert(observed[i]==0x35);
  guards();
 }
}
int main(void) {
 crossings(); recovery(0); recovery(1);
 puts("storage48 scatter checks passed"); return 0;
}
