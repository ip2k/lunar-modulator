/* SPDX-License-Identifier: GPL-3.0-only */
/* Test-only packed logical slots with each physical sector's final page reserved. */
#include "project_store.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define PHYS_SECTOR 4096u
#define TAIL_PAGE 256u
#define DATA_PER_SECTOR (PHYS_SECTOR-TAIL_PAGE)
#define PHYS_PER_SLOT 12u
#define LOGICAL_SLOT (11u*LP_SECTOR)
#define BODY_MAX 12000u
#define FLASH_BYTES (2u*PHYS_PER_SLOT*PHYS_SECTOR)

static uint8_t flash[FLASH_BYTES], initial[FLASH_BYTES];
static uint8_t old_body[BODY_MAX], new_body[BODY_MAX];
static uint32_t old_len=8193u, new_len=9473u;
static unsigned mutations, fail_at, failure_mode, programs;

static uint32_t map_byte(unsigned slot,uint32_t logical) {
    uint32_t sector=logical/DATA_PER_SECTOR;
    uint32_t within=logical%DATA_PER_SECTOR;
    assert(slot<2u && sector<PHYS_PER_SLOT);
    return slot*PHYS_PER_SLOT*PHYS_SECTOR+sector*PHYS_SECTOR+within;
}
static uint32_t logical_slot(uint32_t off) { return off/LOGICAL_SLOT; }
static uint32_t logical_in_slot(uint32_t off) { return off%LOGICAL_SLOT; }

static int mutate_should_fail(void) { return ++mutations==fail_at; }
static int read_packed(unsigned slot,uint32_t off,uint8_t *out,uint32_t n) {
    if(slot>=2u || off>LOGICAL_SLOT || n>LOGICAL_SLOT-off) return -1;
    while(n) {
        uint32_t phys=map_byte(slot,off);
        uint32_t k=DATA_PER_SECTOR-(off%DATA_PER_SECTOR);
        if(k>n) k=n;
        memcpy(out,flash+phys,k); out+=k; off+=k; n-=k;
    }
    return 0;
}
static int io_read(void *ctx,uint32_t off,void *out,uint32_t n) {
    uint32_t in; unsigned slot; (void)ctx;
    if(!out&&n) return -1;
    slot=(unsigned)logical_slot(off); in=logical_in_slot(off);
    if(slot>=2u || in>LOGICAL_SLOT || n>LOGICAL_SLOT-in) return -1;
    return read_packed(slot,in,out,n);
}
static int io_erase(void *ctx,uint32_t off) {
    uint32_t end,q,first,last; unsigned slot; (void)ctx;
    if(off%LP_SECTOR || off>=2u*LOGICAL_SLOT) return -1;
    if(programs) return -1; /* begin() must finish all erase callbacks before writes. */
    slot=(unsigned)logical_slot(off); q=logical_in_slot(off); end=q+LP_SECTOR;
    if(slot>=2u || end>LOGICAL_SLOT) return -1;
    first=q/DATA_PER_SECTOR; last=(end-1u)/DATA_PER_SECTOR;
    for(uint32_t sector=first;sector<=last;sector++) {
        uint32_t phys=(slot*PHYS_PER_SLOT+sector)*PHYS_SECTOR;
        int fail=mutate_should_fail();
        uint32_t n=(fail&&failure_mode==1u)?PHYS_SECTOR/2u:PHYS_SECTOR;
        memset(flash+phys,0xff,n);
        if(fail) return -1;
    }
    return 0;
}
static int io_program(void *ctx,uint32_t off,const void *data,uint32_t n) {
    const uint8_t *src=data; unsigned slot; uint32_t in; (void)ctx;
    if(!data&&n) return -1;
    slot=(unsigned)logical_slot(off); in=logical_in_slot(off);
    if(slot>=2u || in>LOGICAL_SLOT || n>LOGICAL_SLOT-in) return -1;
    programs++;
    while(n) {
        uint32_t phys=map_byte(slot,in);
        uint32_t chunk=DATA_PER_SECTOR-(in%DATA_PER_SECTOR);
        uint32_t page=TAIL_PAGE-(phys%TAIL_PAGE);
        if(chunk>page) chunk=page;
        if(chunk>n) chunk=n;
        int fail=mutate_should_fail();
        uint32_t write_n=(fail&&failure_mode==1u)?chunk/2u:chunk;
        for(uint32_t i=0;i<write_n;i++) {
            if((flash[phys+i]&src[i])!=src[i]) return -1;
            flash[phys+i]=src[i];
        }
        if(fail) return -1;
        src+=chunk; in+=chunk; n-=chunk;
    }
    return 0;
}
static int io_validate(void *ctx,uint32_t off,uint32_t n) {
    uint8_t prefix[8]; unsigned slot; uint32_t in; (void)ctx;
    slot=(unsigned)logical_slot(off); in=logical_in_slot(off);
    if(slot>=2u || in>LOGICAL_SLOT || n>LOGICAL_SLOT-in || n<8u) return 1;
    if(read_packed(slot,in,prefix,sizeof prefix)) return 1;
    if(!memcmp(prefix,"OLD_BODY",8u) && n==old_len) return 0;
    if(!memcmp(prefix,"NEW_BODY",8u) && n==new_len) return 0;
    return 1;
}
static lunar_project_io io={NULL,io_read,io_erase,io_program,io_validate};

static void fill_body(uint8_t *p,uint32_t n,const char *prefix,uint32_t seed) {
    uint32_t x=seed;
    memcpy(p,prefix,8u);
    for(uint32_t i=8;i<n;i++) {
        x^=x<<13; x^=x>>17; x^=x<<5;
        p[i]=(uint8_t)x;
    }
}
static void write_body(const uint8_t *body,uint32_t n) {
    lunar_project_store store;
    assert(!lunar_project_begin(&store,&io,LOGICAL_SLOT));
    assert(!lunar_project_write(&store,0,body,n));
    assert(!lunar_project_commit(&store,n));
}
static void assert_tail_pages(void) {
    for(unsigned slot=0;slot<2;slot++)
      for(unsigned sector=0;sector<PHYS_PER_SLOT;sector++) {
        const uint8_t *p=flash+(slot*PHYS_PER_SLOT+sector)*PHYS_SECTOR;
        for(unsigned i=DATA_PER_SECTOR;i<PHYS_SECTOR;i++) assert(p[i]==0xff);
      }
}
/* Both stock predicates require this leading signature. CRC is intentionally
 * not evaluated because the invariant being tested rejects at that first gate. */
static int spl_candidate_rejected(const uint8_t *p) {
    uint16_t signature=(uint16_t)p[6]|(uint16_t)p[7]<<8;
    return signature!=0x5441u;
}
static int cleanup_candidate_rejected(const uint8_t *p) {
    uint16_t signature=(uint16_t)p[6]|(uint16_t)p[7]<<8;
    return signature!=0x5441u;
}
static void assert_all_candidates_rejected(void) {
    for(unsigned slot=0;slot<2;slot++)
      for(unsigned sector=0;sector<PHYS_PER_SLOT;sector++) {
        const uint8_t *p=flash+(slot*PHYS_PER_SLOT+sector)*PHYS_SECTOR+
                         DATA_PER_SECTOR;
        assert(spl_candidate_rejected(p));
        assert(cleanup_candidate_rejected(p));
      }
}
static void assert_active_physical_unchanged(unsigned slot) {
    uint32_t start=slot*PHYS_PER_SLOT*PHYS_SECTOR;
    assert(!memcmp(flash+start,initial+start,PHYS_PER_SLOT*PHYS_SECTOR));
}
static void sweep_transition(unsigned old_slot,uint32_t old_gen,
                             const uint8_t *old_data,uint32_t old_n,
                             unsigned next_slot,uint32_t next_gen,
                             const uint8_t *next_data,uint32_t next_n) {
    unsigned total,ordinal;
    memcpy(flash,initial,sizeof flash); mutations=0; fail_at=0; programs=0;
    write_body(next_data,next_n); total=mutations; assert(total>0);
    memcpy(flash,initial,sizeof flash);
    for(ordinal=1;ordinal<=total;ordinal++) {
        for(unsigned mode=1;mode<=2;mode++) {
            lunar_project_store scan={0};
            int rc,found; uint32_t got_gen,len; uint8_t got[BODY_MAX];
            memcpy(flash,initial,sizeof flash); mutations=0; fail_at=ordinal;
            failure_mode=mode; programs=0;
            lunar_project_store update;
            rc=lunar_project_begin(&update,&io,LOGICAL_SLOT);
            if(!rc) rc=lunar_project_write(&update,0,next_data,next_n);
            if(!rc) rc=lunar_project_commit(&update,next_n);
            assert(rc!=0);
            assert_active_physical_unchanged(old_slot);
            assert_tail_pages(); assert_all_candidates_rejected();
            scan.io=io; scan.slot_bytes=LOGICAL_SLOT;
            assert(!lunar_project_scan(&scan,&found,&got_gen,&len));
            if(got_gen==next_gen) {
                assert(found==(int)next_slot && len==next_n);
                assert(!read_packed(next_slot,LP_HEADER,got,next_n));
                assert(!memcmp(got,next_data,next_n));
            } else {
                assert(got_gen==old_gen && found==(int)old_slot && len==old_n);
                assert(!read_packed(old_slot,LP_HEADER,got,old_n));
                assert(!memcmp(got,old_data,old_n));
            }
        }
    }
}
int main(void) {
    lunar_project_store store={0};
    int slot; uint32_t gen,len;
    fill_body(old_body,old_len,"OLD_BODY",0x10293847u);
    fill_body(new_body,new_len,"NEW_BODY",0xabcdef01u);
    memset(flash,0xff,sizeof flash);
    memset(initial,0xff,sizeof initial);
    write_body(old_body,old_len);
    store.io=io; store.slot_bytes=LOGICAL_SLOT;
    assert(!lunar_project_scan(&store,&slot,&gen,&len));
    assert(slot==0 && gen==0 && len==old_len);
    memcpy(initial,flash,sizeof flash);
    assert_tail_pages(); assert_all_candidates_rejected();
    sweep_transition(0,0,old_body,old_len,1,1,new_body,new_len);
    /* Materialize generation 1, then fault the 1 -> 2 replacement in slot 0. */
    memcpy(flash,initial,sizeof flash); mutations=0; fail_at=0; programs=0;
    write_body(new_body,new_len); memcpy(initial,flash,sizeof flash);
    assert_tail_pages(); assert_all_candidates_rejected();
    sweep_transition(1,1,new_body,new_len,0,2,old_body,old_len);

    /* Mapping resets at slot boundary; malformed requests reject before mutation. */
    memcpy(flash,initial,sizeof flash); mutations=0; fail_at=0; programs=0;
    store.io=io; store.slot_bytes=LOGICAL_SLOT;
    assert(lunar_project_begin(&store,&io,LOGICAL_SLOT+1u));
    assert(!mutations);
    memset(&store,0,sizeof store);
    assert(!lunar_project_begin(&store,&io,LOGICAL_SLOT));
    {
        unsigned before=mutations;
        uint8_t byte=0;
        assert(lunar_project_write(&store,LOGICAL_SLOT,&byte,1u));
        assert(lunar_project_write(&store,UINT32_MAX,&byte,1u));
        assert(io_program(NULL,2u*LOGICAL_SLOT,&byte,1u));
        assert(io_erase(NULL,2u*LOGICAL_SLOT));
        assert(mutations==before);
    }
    assert_tail_pages(); assert_all_candidates_rejected();
    return 0;
}
