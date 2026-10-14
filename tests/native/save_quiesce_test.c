/* SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { FM1_IRQ_ALNK0 = 11 };
static uint32_t cfg[16], spi;
static uint16_t con0;
static unsigned irq_enabled = 1, syncs, offs, ons;
static uint8_t lcd_busy;
#define FM1_ICFG(n) cfg[(n) >> 3]
#define FM1_ALNK_CON0 con0
#define FM1_LCD_SPI_CON spi
static void fm1_irq_mask(uint32_t n) { assert(!irq_enabled); cfg[n>>3] &= ~(1u << ((n&7)*4)); }
static void fm1_audio_stop(void) { assert(!irq_enabled); con0 &= ~0x800u; }
static void fm1_irq_off(void) { assert(irq_enabled); irq_enabled=0; offs++; }
static void fm1_irq_on(void) { assert(!irq_enabled); irq_enabled=1; ons++; }
static void lcd_sync(void) { assert(!lcd_busy || (spi & 0x8000)); syncs++; lcd_busy=0; }
#include "audio_queue.h"
static lunar_audio_queue_t audio_queue;
static int32_t abuf[1024];
/* Exact unmodified packet/producer functions extracted from the pinned USB
 * source by the verification driver; registers and endpoints are modeled. */
#include "uac_save_functions.h"
#include "save_quiesce.h"
int main(int argc, char **argv) {
    unsigned shard=argc>1?(unsigned)strtoul(argv[1],0,10):0;
    assert(shard<30);
    for (unsigned cycle=0;cycle<1000;cycle++) {
        lunar_audio_pause_t p={0};
        uint32_t d[49], saved_cfg=0x75463210u ^ (cycle << 12);
        uint16_t saved_con=(uint16_t)(0xABC0u ^ cycle);
        cfg[1]=saved_cfg; con0=saved_con; irq_enabled=1;
        offs=ons=syncs=0;
        ua_r=0xFFFFFF00u+cycle; ua_w=ua_r;
        memset(&uac,0,sizeof uac);
        uac.alt=uac.flowing=uac.go=uac.feed=1;
        uac.r48=uac.ring48=(cycle+shard)&1;
        uac.fill_min=uac.r48?UA_LO48:UA_LO;
        uac.last=0x12345678;
        usb.config=1;
        /* An empty primed ring repeats its prior frame: establish the hazard. */
        unsigned n=uac_packet(d);
        for(unsigned i=0;i<n;i++) assert(d[i]==0x12345678);
        memset(abuf,0xA7,sizeof abuf);
        audio_queue.read=7; audio_queue.written=10;
        lcd_busy=1; spi=0;
        assert(lunar_save_quiesce_begin(&p)==0);
        assert(!p.active && !offs && !syncs && uac.go);
        spi=0x8000;
        assert(lunar_save_quiesce_begin(&p)==1);
        assert(p.active && !lcd_busy && syncs==1 && offs==1 && ons==1 && irq_enabled);
        assert(!uac.go && !uac.feed && !uac.last && ua_w==ua_r);
        assert(!(con0&0x800) && !(cfg[1]&(1u<<12)));
        assert(lunar_save_quiesce_begin(&p)<0 && syncs==1);
        for(unsigned packets=0;packets<50;packets++) {
            memset(d,0xA7,sizeof d); n=uac_packet(d);
            for(unsigned i=0;i<n;i++) assert(!d[i]);
        }
        lunar_save_quiesce_end(&p);
        assert(!p.active && offs==2 && ons==2 && irq_enabled);
        assert(cfg[1]==saved_cfg && con0==saved_con);
        for(unsigned i=0;i<1024;i++) assert(!abuf[i]);
        assert(!audio_queue.read && !audio_queue.written && !uac.go);
        /* The real producer re-primes with silence, including 48k history. */
        memset(&rs,0xA7,sizeof rs);
        uac_render_start();
        assert(uac.go && uac.feed && uac.ring48==uac.r48);
        n=uac_packet(d); for(unsigned i=0;i<n;i++) assert(!d[i]);
        if(uac.r48) {
            for(unsigned i=0;i<2*RS_H;i++) assert(!rs.l[i] && !rs.r[i]);
            assert(!rs.w && !rs.ph);
        }
    }
    printf("shard=%u cycles=1000 PASS\n",shard);
    return 0;
}
