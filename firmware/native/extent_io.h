/* SPDX-License-Identifier: GPL-3.0-only */
/* Bounded logical-to-physical IO adapter. No addresses or device permission
 * are built in. Geometry must be independently admitted before hardware use. */
#ifndef LUNAR_EXTENT_IO_H
#define LUNAR_EXTENT_IO_H
#include <stdint.h>
#include <string.h>
#define LE_MAX_EXTENTS 4u
#define LE_MAX_PROTECTED 8u
#define LE_SECTOR 4096u
typedef struct { uint32_t base, bytes; } lunar_extent;
typedef struct {
 void *ctx;
 int (*read)(void *,uint32_t,void *,uint32_t);
 int (*erase)(void *,uint32_t);
 int (*program)(void *,uint32_t,const void *,uint32_t);
} lunar_extent_backend;
typedef struct {
 lunar_extent_backend backend;
 lunar_extent extents[LE_MAX_EXTENTS];
 uint32_t count, bytes;
 int ready;
} lunar_extent_io;
static int le_overlap(lunar_extent a,lunar_extent b) {
 return (uint64_t)a.base+a.bytes > (uint64_t)b.base &&
        (uint64_t)b.base+b.bytes > (uint64_t)a.base;
}
static int le_valid(lunar_extent e,uint32_t limit) {
 return e.bytes && !(e.base%LE_SECTOR) && !(e.bytes%LE_SECTOR) &&
        (uint64_t)e.base+e.bytes<=limit;
}
/* Extent order defines logical order; gaps in physical storage are invisible.
 * Protected ranges are mandatory policy inputs, not inferred from erased bytes.
 * Failed reinitialization disables a previously usable adapter. Inputs must not
 * alias the destination mapper. Program callers/backend must enforce device
 * page limits; this adapter only splits requests at physical extent boundaries.
 * Project IO callers supply their own format validator alongside these callbacks. */
static int lunar_extent_init(lunar_extent_io *m,const lunar_extent_backend *io,
 const lunar_extent *extents,uint32_t count,const lunar_extent *protected_ranges,
 uint32_t protected_count,uint32_t physical_limit) {
 uint32_t i,j; uint64_t total=0;
 if(!m) return -2;
 memset(m,0,sizeof *m);
 if(!io||!io->read||!io->erase||!io->program||!extents||!count||
    count>LE_MAX_EXTENTS||!protected_ranges||!protected_count||
    protected_count>LE_MAX_PROTECTED||!physical_limit) return -2;
 for(i=0;i<protected_count;i++)
  if(!le_valid(protected_ranges[i],physical_limit)) return -2;
 for(i=0;i<count;i++) {
  if(!le_valid(extents[i],physical_limit)) return -2;
  total+=extents[i].bytes; if(total>UINT32_MAX) return -2;
  for(j=0;j<i;j++) if(le_overlap(extents[i],extents[j])) return -2;
  for(j=0;j<protected_count;j++)
   if(le_overlap(extents[i],protected_ranges[j])) return -2;
 }
 m->backend=*io; memcpy(m->extents,extents,count*sizeof *extents);
 m->count=count; m->bytes=(uint32_t)total; m->ready=1; return 0;
}
static int le_range(const lunar_extent_io *m,uint32_t off,uint32_t n) {
 return m&&m->ready&&off<=m->bytes&&n<=m->bytes-off;
}
static uint32_t le_locate(const lunar_extent_io *m,uint32_t *off) {
 uint32_t i;
 for(i=0;i<m->count;i++) {
  if(*off<m->extents[i].bytes) return i;
  *off-=m->extents[i].bytes;
 }
 return m->count;
}
static int lunar_extent_read(void *ctx,uint32_t off,void *out,uint32_t n) {
 lunar_extent_io *m=ctx; uint8_t *p=out; uint32_t i,k;
 if(!le_range(m,off,n)||(!out&&n)) return -2;
 if(!n) return 0;
 i=le_locate(m,&off);
 while(n) {
  k=m->extents[i].bytes-off; if(k>n) k=n;
  if(m->backend.read(m->backend.ctx,m->extents[i].base+off,p,k)) return -1;
  p+=k; n-=k; off=0; i++;
 }
 return 0;
}
static int lunar_extent_program(void *ctx,uint32_t off,const void *data,uint32_t n) {
 lunar_extent_io *m=ctx; const uint8_t *p=data; uint32_t i,k;
 if(!le_range(m,off,n)||(!data&&n)) return -2;
 if(!n) return 0;
 i=le_locate(m,&off);
 while(n) {
  k=m->extents[i].bytes-off; if(k>n) k=n;
  if(m->backend.program(m->backend.ctx,m->extents[i].base+off,p,k)) return -1;
  p+=k; n-=k; off=0; i++;
 }
 return 0;
}
static int lunar_extent_erase(void *ctx,uint32_t off) {
 lunar_extent_io *m=ctx; uint32_t i;
 if(!le_range(m,off,LE_SECTOR)||off%LE_SECTOR) return -2;
 i=le_locate(m,&off);
 return m->backend.erase(m->backend.ctx,m->extents[i].base+off)?-1:0;
}
#endif
