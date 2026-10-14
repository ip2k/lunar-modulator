/* SPDX-License-Identifier: GPL-3.0-only */
/* Fault model for the unbound packed adapter over the proposed sector map. */
#include "project_store.h"
#include "tail_page_io.h"
#include <assert.h>
#include <stdint.h>
#include <string.h>

#define PHYS_SECTOR 4096u
#define TAIL_PAGE 256u
#define DATA_PER_SECTOR (PHYS_SECTOR-TAIL_PAGE)
#define PHYS_PER_SLOT 12u
#define LOGICAL_SLOT (11u*LP_SECTOR)
#define BODY_MAX 43130u
#define FLASH_BYTES 0x100000u

/* Offsets from the documented storage48 migration candidate. */
static const uint32_t slot_sector[2][PHYS_PER_SLOT]={
    {0x0d9000u,0x0da000u,0x0db000u,0x0dc000u,0x0dd000u,0x0de000u,0x0df000u,
     0x0e5000u,0x0e6000u,0x0e7000u,0x0e8000u,0x0ea000u},
    {0x0eb000u,0x0ec000u,0x0ed000u,0x0ee000u,0x0ef000u,0x0f0000u,0x0f1000u,
     0x0f2000u,0x0f3000u,0x0f4000u,0x0f5000u,0x0f6000u}
};
static uint8_t flash[FLASH_BYTES], initial[FLASH_BYTES];
static uint8_t old_body[BODY_MAX], new_body[BODY_MAX];
static uint32_t old_len=BODY_MAX, new_len=BODY_MAX;
static unsigned mutations, fail_at, failure_mode, programs;

static uint32_t map_byte(unsigned slot,uint32_t logical) {
    uint32_t sector=logical/DATA_PER_SECTOR;
    uint32_t within=logical%DATA_PER_SECTOR;
    assert(slot<2u && sector<PHYS_PER_SLOT);
    return slot_sector[slot][sector]+within;
}
static uint32_t logical_slot(uint32_t off) { return off/LOGICAL_SLOT; }
static uint32_t logical_in_slot(uint32_t off) { return off%LOGICAL_SLOT; }
static int mapped_sector(uint32_t addr) {
    for(unsigned s=0;s<2;s++)
      for(unsigned i=0;i<PHYS_PER_SLOT;i++)
        if(addr>=slot_sector[s][i] && addr<slot_sector[s][i]+PHYS_SECTOR) return 1;
    return 0;
}
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
static int backend_read(void *ctx,uint32_t off,void *out,uint32_t n) {
    (void)ctx;
    assert(off<=FLASH_BYTES && n<=FLASH_BYTES-off);
    memcpy(out,flash+off,n); return 0;
}
static int backend_erase(void *ctx,uint32_t off) {
    (void)ctx;
    assert(off%PHYS_SECTOR==0u && off<FLASH_BYTES && mapped_sector(off));
    if(programs) return -1;
    int fail=mutate_should_fail();
    uint32_t n=(fail&&failure_mode==1u)?PHYS_SECTOR/2u:PHYS_SECTOR;
    memset(flash+off,0xff,n);
    return fail?-1:0;
}
static int backend_program(void *ctx,uint32_t off,const void *data,uint32_t n) {
    const uint8_t *src=data; (void)ctx;
    assert(mapped_sector(off) && n && n<=TAIL_PAGE-off%TAIL_PAGE);
    assert(off%PHYS_SECTOR<DATA_PER_SECTOR && n<=DATA_PER_SECTOR-off%PHYS_SECTOR);
    programs++;
    int fail=mutate_should_fail();
    uint32_t write_n=(fail&&failure_mode==1u)?n/2u:n;
    for(uint32_t i=0;i<write_n;i++) {
        if((flash[off+i]&src[i])!=src[i]) return -1;
        flash[off+i]=src[i];
    }
    return fail?-1:0;
}
static lunar_tail_io mapper;
static int io_read(void *ctx,uint32_t off,void *out,uint32_t n) {
    (void)ctx; return lunar_tail_read(&mapper,off,out,n);
}
static int io_erase(void *ctx,uint32_t off) {
    (void)ctx; return lunar_tail_erase(&mapper,off);
}
static int io_program(void *ctx,uint32_t off,const void *data,uint32_t n) {
    (void)ctx; return lunar_tail_program(&mapper,off,data,n);
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
static void assert_tail_pages_and_unused_suffix(void) {
    for(unsigned slot=0;slot<2;slot++) {
      for(unsigned sector=0;sector<PHYS_PER_SLOT;sector++) {
        const uint8_t *p=flash+slot_sector[slot][sector];
        for(unsigned i=DATA_PER_SECTOR;i<PHYS_SECTOR;i++) assert(p[i]==0xff);
      }
      /* The logical slot ends 1,024 bytes before the packed physical capacity. */
      const uint8_t *last=flash+slot_sector[slot][PHYS_PER_SLOT-1u];
      for(unsigned i=(LOGICAL_SLOT%DATA_PER_SECTOR);i<DATA_PER_SECTOR;i++) assert(last[i]==0xff);
    }
}
/* Only the common outer signature gate is evaluated here; CRC predicates are
 * not reimplemented. All-FF reserved pages fail at this first condition. */
static int spl_signature_gate_rejects(const uint8_t *p) {
    uint16_t signature=(uint16_t)p[6]|(uint16_t)p[7]<<8;
    return signature!=0x5441u;
}
static int cleanup_signature_gate_rejects(const uint8_t *p) {
    uint16_t signature=(uint16_t)p[6]|(uint16_t)p[7]<<8;
    return signature!=0x5441u;
}
static void assert_candidate_signature_gates(void) {
    for(unsigned slot=0;slot<2;slot++)
      for(unsigned sector=0;sector<PHYS_PER_SLOT;sector++) {
        const uint8_t *p=flash+slot_sector[slot][sector]+DATA_PER_SECTOR;
        assert(spl_signature_gate_rejects(p));
        assert(cleanup_signature_gate_rejects(p));
      }
}
static void assert_outside_storage_unchanged(void) {
    for(uint32_t i=0;i<FLASH_BYTES;i++)
        if(!mapped_sector(i)) assert(flash[i]==initial[i]);
}
static void assert_active_physical_unchanged(unsigned slot) {
    for(unsigned s=0;s<PHYS_PER_SLOT;s++)
        assert(!memcmp(flash+slot_sector[slot][s],initial+slot_sector[slot][s],PHYS_SECTOR));
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
            assert_outside_storage_unchanged();
            assert_tail_pages_and_unused_suffix(); assert_candidate_signature_gates();
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
static void initialize_sentinel_flash(void) {
    for(uint32_t i=0;i<FLASH_BYTES;i++) flash[i]=(uint8_t)(i*37u+23u);
    /* Model the already-formatted reserved pages; initial migration remains unresolved. */
    for(unsigned slot=0;slot<2;slot++) {
      for(unsigned s=0;s<PHYS_PER_SLOT;s++)
        memset(flash+slot_sector[slot][s]+DATA_PER_SECTOR,0xff,TAIL_PAGE);
      memset(flash+slot_sector[slot][PHYS_PER_SLOT-1u]+(LOGICAL_SLOT%DATA_PER_SECTOR),
             0xff,DATA_PER_SECTOR-(LOGICAL_SLOT%DATA_PER_SECTOR));
    }
}
int main(void) {
    lunar_project_store store={0};
    int slot; uint32_t gen,len;
    uint8_t byte=0,probe[2];
    lunar_tail_backend backend={NULL,backend_read,backend_erase,backend_program};
    uint32_t sectors[24];
    for(unsigned i=0;i<24;i++) sectors[i]=slot_sector[i/12u][i%12u];
    assert(!lunar_tail_init(&mapper,&backend,sectors,24u,LOGICAL_SLOT,FLASH_BYTES));
    fill_body(old_body,old_len,"OLD_BODY",0x10293847u);
    fill_body(new_body,new_len,"NEW_BODY",0xabcdef01u);
    initialize_sentinel_flash();
    assert(!lunar_project_begin(&store,&io,LOGICAL_SLOT));
    assert(!lunar_project_write(&store,0,old_body,old_len));
    assert(!lunar_project_commit(&store,old_len));
    store.io=io; store.slot_bytes=LOGICAL_SLOT;
    assert(!lunar_project_scan(&store,&slot,&gen,&len));
    assert(slot==0 && gen==0 && len==old_len);
    memcpy(initial,flash,sizeof flash);
    assert_tail_pages_and_unused_suffix(); assert_candidate_signature_gates();
    sweep_transition(0,0,old_body,old_len,1,1,new_body,new_len);
    /* Materialize generation 1, then fault the 1-to-2 replacement in slot 0. */
    memcpy(flash,initial,sizeof flash); mutations=0; fail_at=0; programs=0;
    write_body(new_body,new_len); memcpy(initial,flash,sizeof flash);
    assert_tail_pages_and_unused_suffix(); assert_candidate_signature_gates();
    sweep_transition(1,1,new_body,new_len,0,2,old_body,old_len);

    /* Invalid store size and backend ranges must reject before any mutation. */
    memcpy(flash,initial,sizeof flash); mutations=0; fail_at=0; programs=0;
    store.io=io; store.slot_bytes=LOGICAL_SLOT;
    assert(lunar_project_begin(&store,&io,LOGICAL_SLOT+1u));
    assert(!mutations);
    {
        unsigned before=mutations;
        assert(io_read(NULL,UINT32_MAX,&byte,1u));
        assert(io_read(NULL,2u*LOGICAL_SLOT-1u,probe,2u));
        assert(io_program(NULL,UINT32_MAX,&byte,1u));
        assert(io_program(NULL,2u*LOGICAL_SLOT-1u,&probe,2u));
        assert(io_erase(NULL,1u));
        assert(io_erase(NULL,2u*LOGICAL_SLOT));
        assert(mutations==before);
    }
    assert_tail_pages_and_unused_suffix(); assert_candidate_signature_gates();
    assert_outside_storage_unchanged();
    {
        uint32_t bad[24]; memcpy(bad,sectors,sizeof bad);
        bad[23]=bad[0];
        assert(lunar_tail_init(&mapper,&backend,bad,24u,LOGICAL_SLOT,FLASH_BYTES));
        assert(!mapper.ready && io_read(NULL,0,&byte,1u));
        assert(lunar_tail_init(&mapper,&backend,sectors,23u,LOGICAL_SLOT,FLASH_BYTES));
        assert(lunar_tail_init(&mapper,&backend,sectors,24u,12u*LP_SECTOR,FLASH_BYTES));
        assert(lunar_tail_init(&mapper,&backend,sectors,24u,LOGICAL_SLOT,0xf6000u));
        bad[23]=UINT32_MAX-4095u;
        assert(lunar_tail_init(&mapper,&backend,bad,24u,LOGICAL_SLOT,UINT32_MAX));
        assert(mutations==0);
    }
    return 0;
}
