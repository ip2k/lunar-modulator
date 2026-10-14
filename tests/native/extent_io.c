/* SPDX-License-Identifier: GPL-3.0-only */
#include "extent_io.h"
#include "project_store.h"
#include <assert.h>
#include <stdio.h>
#define FLASH_BYTES 1048576u
#define SLOT 49152u
static uint8_t flash[FLASH_BYTES],body[SLOT-LP_HEADER],scratch[SLOT];
static unsigned calls,fail_at,fail_erase_next,fail_program_next;
static lunar_extent_io map;
static int rd(void *ctx,uint32_t at,void *p,uint32_t n) {
 (void)ctx; assert(at<=FLASH_BYTES&&n<=FLASH_BYTES-at);
 calls++; if(calls==fail_at) return -1;
 memcpy(p,flash+at,n); return 0;
}
static int er(void *ctx,uint32_t at) {
 (void)ctx; assert(!(at%LE_SECTOR)&&at<=FLASH_BYTES-LE_SECTOR);
 calls++; if(calls==fail_at||fail_erase_next) {
  fail_erase_next=0; memset(flash+at,255,2048); return -1;
 }
 memset(flash+at,255,LE_SECTOR); return 0;
}
static int wr(void *ctx,uint32_t at,const void *p,uint32_t n) {
 const uint8_t *b=p; uint32_t i; int failed;
 (void)ctx; assert(at<=FLASH_BYTES&&n<=FLASH_BYTES-at);
 calls++; failed=calls==fail_at||fail_program_next; fail_program_next=0;
 if(failed) n/=2;
 for(i=0;i<n;i++) { assert((flash[at+i]&b[i])==b[i]); flash[at+i]=b[i]; }
 return failed?-1:0;
}
static const lunar_extent_backend backend={0,rd,er,wr};
static lunar_extent extents[]={{0xd9000,SLOT},{0xea000,32768},{0xf7000,16384}};
static const lunar_extent protected_ranges[]={
 {0,0xd9000},{0xe5000,0x5000},{0xf2000,0x5000},{0xfb000,0x5000}
};
static void setup(void) {
 memset(flash,0xa5,sizeof flash); calls=fail_at=fail_erase_next=fail_program_next=0;
 assert(!lunar_extent_init(&map,&backend,extents,3,protected_ranges,4,FLASH_BYTES));
 assert(map.bytes==2*SLOT);
}
static void guards(void) {
 unsigned i;
 for(i=0;i<FLASH_BYTES;i++)
  if(i<0xd9000||(i>=0xe5000&&i<0xea000)||(i>=0xf2000&&i<0xf7000)||i>=0xfb000)
   assert(flash[i]==0xa5);
}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 if(n!=sizeof body||lunar_extent_read(ctx,off,scratch,n)) return -1;
 return memcmp(scratch,body,n)?1:0;
}
static void save(lunar_project_store *s,const lunar_project_io *io) {
 assert(!lunar_project_begin(s,io,SLOT));
 assert(!lunar_project_write(s,0,body,sizeof body));
 assert(!lunar_project_commit(s,sizeof body));
}
static void geometry(void) {
 lunar_extent e[3]; lunar_extent protected_bad={0xf1000,8192}; unsigned before;
 setup(); memcpy(e,extents,sizeof e);
 e[1].base=0xe4000; /* partial overlap with the larger first extent */
 assert(lunar_extent_init(&map,&backend,e,3,protected_ranges,4,FLASH_BYTES)==-2);
 assert(!map.ready);
 e[1]=extents[1]; e[2].base=0xfffff000u;
 assert(lunar_extent_init(&map,&backend,e,3,protected_ranges,4,UINT32_MAX)==-2);
 assert(lunar_extent_init(&map,&backend,extents,3,&protected_bad,1,FLASH_BYTES)==-2);
 assert(lunar_extent_init(&map,&backend,extents,3,0,0,FLASH_BYTES)==-2);
 setup(); before=calls;
 assert(lunar_extent_read(&map,2*SLOT-1,scratch,2)==-2);
 assert(lunar_extent_program(&map,UINT32_MAX,body,1)==-2);
 assert(lunar_extent_erase(&map,1)==-2);
 assert(lunar_extent_erase(&map,2*SLOT)==-2);
 assert(lunar_extent_read(&map,0,0,1)==-2);
 assert(lunar_extent_read(&map,2*SLOT,0,0)==0);
 assert(calls==before); guards();
}
static void crossing(void) {
 unsigned i; uint8_t bytes[128],out[128];
 setup(); for(i=0;i<sizeof bytes;i++) bytes[i]=(uint8_t)i;
 assert(!lunar_extent_erase(&map,SLOT+32768-4096));
 assert(!lunar_extent_erase(&map,SLOT+32768));
 assert(!lunar_extent_program(&map,SLOT+32768-64,bytes,sizeof bytes));
 assert(!memcmp(flash+0xf2000-64,bytes,64));
 assert(!memcmp(flash+0xf7000,bytes+64,64));
 assert(!lunar_extent_read(&map,SLOT+32768-64,out,sizeof out));
 assert(!memcmp(bytes,out,sizeof bytes)); guards();
 fail_at=calls+2;
 assert(lunar_extent_read(&map,SLOT+32768-64,out,sizeof out)==-1);
}
static void journal(void) {
 lunar_project_store s; lunar_project_io io={&map,lunar_extent_read,lunar_extent_erase,lunar_extent_program,validate};
 uint32_t gen,n; int slot; unsigned i;
 setup(); for(i=0;i<sizeof body;i++) body[i]=(uint8_t)(i*17u);
 /* Empty slots, while all protected bytes retain their sentinel. */
 for(i=0;i<2*SLOT;i+=LE_SECTOR) assert(!lunar_extent_erase(&map,i));
 save(&s,&io); save(&s,&io);
 assert(!lunar_project_scan(&s,&slot,&gen,&n));
 assert(slot==1&&gen==1&&n==sizeof body); guards();
 /* A transport error may have partially erased the inactive slot. */
 fail_erase_next=1;
 assert(lunar_project_begin(&s,&io,SLOT)<0);
 assert(!fail_erase_next); /* Verify failure occurred in erase, after scanning. */
 assert(!lunar_project_scan(&s,&slot,&gen,&n));
 assert(slot==1&&gen==1&&n==sizeof body); guards();
 assert(!lunar_project_begin(&s,&io,SLOT));
 fail_program_next=1;
 assert(lunar_project_write(&s,0,body,sizeof body)<0);
 assert(!fail_program_next);
 assert(lunar_project_commit(&s,sizeof body)<0);
 assert(!lunar_project_scan(&s,&slot,&gen,&n));
 assert(slot==1&&gen==1&&n==sizeof body); guards();
}
int main(void) { geometry(); crossing(); journal(); puts("extent IO checks passed"); return 0; }
