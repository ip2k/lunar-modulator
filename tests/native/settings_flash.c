/* SPDX-License-Identifier: MIT */
#include "settings_flash.h"
#include <assert.h>
#include <stdlib.h>
static uint8_t memory[2 * LJ_SECTOR];
static uint32_t base;
static int ready = 1, stopped = 1, calls, writes, fail, resume_after_erase;
static int rd(void *ctx, uint32_t off, void *dst, uint32_t n)
{
    assert(ctx == memory); assert(off >= base && off-base <= sizeof memory);
    assert(n <= sizeof memory-(off-base)); ++calls;
    memcpy(dst, memory+off-base, n); return 0;
}
static int er(void *ctx, uint32_t off)
{
    assert(ctx == memory); assert(off == base || off == base+LJ_SECTOR);
    ++calls; ++writes; memset(memory+off-base, 0xff, LJ_SECTOR);
    if (resume_after_erase) stopped = 0;
    return fail ? -17 : 0;
}
static int pr(void *ctx, uint32_t off, const void *src, uint32_t n)
{
    const uint8_t *p = src; unsigned i;
    assert(ctx == memory); assert(off >= base && off-base <= sizeof memory);
    assert(n <= sizeof memory-(off-base)); ++calls; ++writes;
    for (i=0; i<n; ++i) {
        assert((memory[off-base+i] & p[i]) == p[i]);
        memory[off-base+i] &= p[i];
    }
    return fail ? -17 : 0;
}
static int fr(void *ctx) { assert(ctx == memory); return ready; }
static int as(void *ctx) { assert(ctx == memory); return stopped; }
int main(int argc, char **argv)
{
    lunar_settings_flash s; lunar_journal_io io;
    lunar_settings_hal hal = {memory,rd,er,pr,fr,as};
    uint8_t value[256], got[256]; uint32_t len = 999;
    unsigned id; int before;
    assert(argc == 2); id = (unsigned)strtoul(argv[1],0,10); assert(id<30);
    base = id % 2 ? 0xFD000u : 0xFC000u;
    memset(memory,0xff,sizeof memory); memset(value,0x55,sizeof value);
    assert(!lunar_settings_flash_init(&s,base,&hal,&io));
    if (id == 0) {
        assert(lunar_journal_save(&io,value,256)); assert(!calls); return 0;
    }
    s.admitted = 1;
    if (id == 1 || id == 2) {
        assert(!lunar_journal_save(&io,value,256));
        assert(!lunar_journal_load(&io,got,256,&len));
        assert(len==256 && !memcmp(got,value,256));
        before=writes; assert(!lunar_journal_save(&io,value,256)); assert(writes==before);
        return 0;
    }
    if (id == 3) ready=0;
    if (id == 4) stopped=0;
    if (id == 5) ready=-1;
    if (id == 6) stopped=-1;
    if (id >= 3 && id <= 6) {
        assert(lunar_journal_save(&io,value,256)); assert(!writes); return 0;
    }
    if (id == 7 || id == 8) {
        fail=1;
        assert((id==7 ? io.erase(&s,0) : io.program(&s,0,value,1)) == -17);
        assert(s.uncertain); fail=0; before=writes;
        assert(io.erase(&s,LJ_SECTOR)==-8); assert(io.program(&s,1,value,1)==-8);
        assert(writes==before); assert(!io.read(&s,0,got,1)); return 0;
    }
    if (id == 9) {
        assert(!lunar_journal_save(&io,value,256));
        before=writes; value[0]=0xaa;
        resume_after_erase=1;
        assert(lunar_journal_save(&io,value,256)); assert(writes==before+1);
        assert(!lunar_journal_load(&io,got,256,&len));
        assert(len==256 && got[0]==0x55); return 0;
    }
    if (id == 10) assert(io.read(&s,8192,got,1)==-8);
    if (id == 11) assert(io.read(&s,0xffffffffu,got,2)==-8);
    if (id == 12) assert(io.read(&s,1,got,0xffffffffu)==-8);
    if (id == 13) assert(io.erase(&s,1)==-8);
    if (id == 14) assert(io.erase(&s,8192)==-8);
    if (id == 15) assert(io.program(&s,8191,value,2)==-8);
    if (id == 16) assert(io.program(&s,0,value,257)==-8);
    if (id == 17) assert(io.program(&s,0xffffffffu,value,1)==-8);
    if (id == 18) assert(io.program(&s,0,0,1)==-8);
    if (id == 19) assert(io.read(&s,0,0,1)==-8);
    if (id == 20) { assert(!io.read(&s,8192,0,0)); assert(!io.program(&s,8192,0,0)); }
    if (id == 21) { s.base=0xFE000u; assert(io.erase(&s,0)==-8); }
    if (id == 22) { s.admitted=0; assert(io.program(&s,0,value,1)==-8); }
    if (id == 23) { s.hal.read=0; assert(io.read(&s,0,got,1)==-8); }
    if (id == 24) { s.hal.erase=0; assert(io.erase(&s,0)==-8); }
    if (id == 25) { s.hal.program=0; assert(io.program(&s,0,value,1)==-8); }
    if (id == 26) { s.hal.flash_ready=0; assert(io.read(&s,0,got,1)==-8); }
    if (id == 27) { s.hal.audio_stopped=0; assert(io.erase(&s,0)==-8); }
    if (id == 28) { assert(lunar_settings_flash_init(&s,0xFE000u,&hal,&io)==-8); assert(!io.read && !s.admitted); }
    if (id == 29) { hal.program=0; assert(lunar_settings_flash_init(&s,base,&hal,&io)==-8); assert(!io.program && !s.admitted); }
    assert(!calls); return 0;
}
