/* SPDX-License-Identifier: GPL-3.0-only */
/* Packed IO over explicit sectors with the final page reserved. No hardware
 * addresses or admission are built in. The backend must be independently safe.
 */
#ifndef LUNAR_TAIL_PAGE_IO_H
#define LUNAR_TAIL_PAGE_IO_H
#include <stdint.h>
#include <string.h>
#define LT_SECTOR 4096u
#define LT_PAGE 256u
#define LT_DATA (LT_SECTOR-LT_PAGE)
#define LT_MAX_SECTORS 24u
typedef struct {
 void *ctx;
 int (*read)(void *,uint32_t,void *,uint32_t);
 int (*erase)(void *,uint32_t);
 int (*program)(void *,uint32_t,const void *,uint32_t);
} lunar_tail_backend;
typedef struct {
 lunar_tail_backend backend;
 uint32_t sectors[LT_MAX_SECTORS], count, slot_bytes, per_slot;
 int ready;
} lunar_tail_io;
/* Two equally sized slots. Each slot owns distinct sectors. Callers supply an
 * already admitted exact sector list; an erased byte pattern proves no ownership.
 * Failed reinitialization disables the adapter. Inputs must not alias m.
 */
static int lunar_tail_init(lunar_tail_io *m,const lunar_tail_backend *b,
 const uint32_t *sectors,uint32_t count,uint32_t slot_bytes,uint32_t physical_limit) {
 uint32_t i,j;
 if(!m) return -2;
 memset(m,0,sizeof *m);
 if(!b||!b->read||!b->erase||!b->program||!sectors||!count||
    count>LT_MAX_SECTORS||count%2u||!slot_bytes||slot_bytes%LT_SECTOR||
    (uint64_t)slot_bytes>(uint64_t)(count/2u)*LT_DATA||
    (uint64_t)slot_bytes*2u>UINT32_MAX) return -2;
 for(i=0;i<count;i++) {
  if(sectors[i]%LT_SECTOR||(uint64_t)sectors[i]+LT_SECTOR>physical_limit) return -2;
  for(j=0;j<i;j++) if(sectors[i]==sectors[j]) return -2;
 }
 m->backend=*b; memcpy(m->sectors,sectors,count*sizeof *sectors);
 m->count=count; m->per_slot=count/2u; m->slot_bytes=slot_bytes; m->ready=1;
 return 0;
}
/* Operations cannot cross slots, including zero-length calls at the total end. */
static int lt_range(const lunar_tail_io *m,uint32_t off,uint32_t n) {
 return m&&m->ready&&off<2u*m->slot_bytes&&n<=m->slot_bytes-off%m->slot_bytes;
}
static uint32_t lt_physical(const lunar_tail_io *m,uint32_t off) {
 uint32_t slot=off/m->slot_bytes,in=off%m->slot_bytes;
 return m->sectors[slot*m->per_slot+in/LT_DATA]+in%LT_DATA;
}
static int lunar_tail_read(void *ctx,uint32_t off,void *out,uint32_t n) {
 lunar_tail_io *m=ctx; uint8_t *p=out; uint32_t k;
 if(!lt_range(m,off,n)||(!out&&n)) return -2;
 while(n) {
  k=LT_DATA-(off%m->slot_bytes)%LT_DATA; if(k>n) k=n;
  if(m->backend.read(m->backend.ctx,lt_physical(m,off),p,k)) return -1;
  p+=k; off+=k; n-=k;
 }
 return 0;
}
static int lunar_tail_program(void *ctx,uint32_t off,const void *data,uint32_t n) {
 lunar_tail_io *m=ctx; const uint8_t *p=data; uint32_t k,phys;
 if(!lt_range(m,off,n)||(!data&&n)) return -2;
 while(n) {
  phys=lt_physical(m,off); k=LT_PAGE-phys%LT_PAGE; if(k>n) k=n;
  if(m->backend.program(m->backend.ctx,phys,p,k)) return -1;
  p+=k; off+=k; n-=k;
 }
 return 0;
}
/* A logical block can overlap two physical sectors. Adjacent logical erases
 * can erase the same physical sector twice: erase the complete inactive slot
 * before ANY programming, as project_store.begin does. Never interleave writes
 * with block erases. The backend must erase the whole 4 KiB physical sector.
 * Safe first migration from unknown stock bytes remains a separate prerequisite.
 */
static int lunar_tail_erase(void *ctx,uint32_t off) {
 lunar_tail_io *m=ctx; uint32_t slot,in,first,last,i;
 if(!lt_range(m,off,LT_SECTOR)||off%LT_SECTOR) return -2;
 slot=off/m->slot_bytes; in=off%m->slot_bytes;
 first=in/LT_DATA; last=(in+LT_SECTOR-1u)/LT_DATA;
 for(i=first;i<=last;i++)
  if(m->backend.erase(m->backend.ctx,m->sectors[slot*m->per_slot+i])) return -1;
 return 0;
}
#endif
