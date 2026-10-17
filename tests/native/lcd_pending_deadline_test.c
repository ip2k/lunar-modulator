/* SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "lcd_pending_deadline.h"
#include "render_stage_profile.h"
#include "producer_gap_profile.h"

/* Only hardware/app dependencies are modeled. The driver extracts the complete
 * production display state and display_strip body, without rewriting either. */
#define FM1_TICKS_PER_US 24u
#define FM1_LCD_SPI_CON spi
static uint32_t now, spi, row, reads, submits, syncs, services, calls;
static uint8_t lcd_busy, selected, valid;
static uint16_t cv_px[240u * 16u], dma_snapshot[240u * 16u];
static struct { int tft; } app;
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
static lunar_producer_gap_profile_t producer_gap_profile;
#endif
#ifdef LUNAR_RENDER_STAGE_PROFILE
static uint32_t profile_calls;
uint32_t lunar_profile_ticks(void) { return now; }
void lunar_profile_finish(unsigned stage, uint32_t start)
{
    assert(stage == LUNAR_PROFILE_DISPLAY_STRIP && start == now);
    ++profile_calls;
}
#endif
static uint32_t fm1_ticks(void) { return now; }
static int fm1_tft_pixels_valid(const int *p) { assert(p == &app.tft); return valid; }
static uint16_t fm1_tft_pixel(const int *p, uint32_t i)
{
    assert(p == &app.tft && !lcd_busy && !selected);
    ++reads;
    return (uint16_t)(i ^ calls);
}
static uint16_t swap16(uint16_t v) { return (uint16_t)((v << 8) | (v >> 8)); }
static void lcd_sync(void)
{
    assert(lcd_busy && selected && (spi & 0x8000u));
    ++syncs;
    lcd_busy = selected = 0;
}
static void lcd_blit(unsigned x, unsigned y, unsigned w, unsigned h, const uint16_t *p)
{
    assert(!lcd_busy && !selected && x == 0 && y == row && w == 240 && h == 16);
    assert(p == cv_px);
    memcpy(dma_snapshot, p, sizeof dma_snapshot);
    ++submits;
    lcd_busy = selected = 1;
    spi = 0;
}
#include "display_strip_exact.h"

static void poll_display(void)
{
    /* A service surrogate checks that each display poll returns; it is not a
     * compiled main loop or proof of real USB/audio scheduling. */
    ++services;
    ++calls;
    display_strip(&row);
    assert(services == calls);
#ifdef LUNAR_RENDER_STAGE_PROFILE
    assert(profile_calls == calls);
#endif
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    assert(producer_gap_profile.display_calls == calls);
#endif
}
static void reset(void)
{
    now = spi = row = reads = submits = syncs = services = calls = 0;
    lcd_busy = selected = 0;
    valid = 1;
    memset(&lcd_pending_deadline, 0, sizeof lcd_pending_deadline);
    lunar_lcd_pending_timeouts = 0;
#ifdef LUNAR_RENDER_STAGE_PROFILE
    profile_calls = 0;
#endif
#ifdef LUNAR_DIAGNOSTIC_PRODUCER_GAPS
    lunar_producer_gap_init(&producer_gap_profile);
#endif
}
static void frozen(uint32_t expected_row, uint32_t expected_submits, uint32_t expected_syncs)
{
    assert(lcd_busy && selected && !spi);
    assert(row == expected_row && submits == expected_submits && syncs == expected_syncs);
    assert(reads == submits * 240u * 16u);
    assert(!memcmp(cv_px, dma_snapshot, sizeof cv_px));
}
int main(void)
{
    const uint32_t limit = LUNAR_LCD_PENDING_DEADLINE_US * FM1_TICKS_PER_US;
    lunar_lcd_pending_deadline_t p = {0};
    assert(!lunar_lcd_pending_expired(&p, UINT32_MAX, limit));
    lunar_lcd_pending_begin(&p, UINT32_MAX - limit / 2u);
    assert(!lunar_lcd_pending_expired(&p, p.started + limit - 1u, limit));
    assert(lunar_lcd_pending_expired(&p, p.started + limit, limit));
    assert(!lunar_lcd_pending_expired(&p, p.started - 1u, limit));
    lunar_lcd_pending_complete(&p);
    assert(!lunar_lcd_pending_expired(&p, UINT32_MAX, limit));

    reset();
    valid = 0;
    poll_display();
    assert(!submits && !lcd_pending_deadline.active);
    valid = 1;
    now = UINT32_MAX - limit / 2u;
    poll_display();
    assert(submits == 1 && row == 16 && !syncs);
    const uint32_t start = now;
    now = start + limit - 1u;
    poll_display();
    frozen(16, 1, 0);
    assert(!lunar_lcd_pending_timeouts);
    now = start + limit;
    poll_display();
    assert(lunar_lcd_pending_timeouts == 1 && lcd_pending_deadline.reported);
    for (unsigned i = 0; i < 10000; ++i) {
        now += 1000003u;
        poll_display();
        frozen(16, 1, 0);
        assert(lunar_lcd_pending_timeouts == 1);
    }
    /* A late DONE releases ownership normally and rearms on the next submit. */
    spi = 0x8000;
    poll_display();
    frozen(32, 2, 1);
    assert(lunar_lcd_pending_timeouts == 1 && !lcd_pending_deadline.reported);
    now += limit;
    poll_display();
    frozen(32, 2, 1);
    assert(lunar_lcd_pending_timeouts == 2);

    reset();
    poll_display();
    now += limit;
    spi = 0x8000;
    poll_display();
    assert(!lunar_lcd_pending_timeouts && row == 32 && syncs == 1 && submits == 2);
    /* DONE takes priority after the boundary too, without a spurious timeout. */
    now += limit + 1u;
    spi = 0x8000;
    poll_display();
    assert(!lunar_lcd_pending_timeouts && row == 48 && syncs == 2);
    /* A missing framebuffer must not release or modify a pending DMA buffer. */
    valid = 0;
    now += limit;
    poll_display();
    frozen(48, 3, 2);
    assert(lunar_lcd_pending_timeouts == 1);
    spi = 0x8000;
    poll_display();
    assert(lcd_busy && selected && syncs == 2 && submits == 3);
    valid = 1;
    poll_display();
    assert(row == 64 && syncs == 3 && submits == 4 && lunar_lcd_pending_timeouts == 1);

    /* Startup transfer: conservatively start from first observation. */
    reset();
    lcd_busy = selected = 1;
    now = 1234;
    valid = 0;
    poll_display();
    assert(lcd_pending_deadline.started == now && !lunar_lcd_pending_timeouts);
    now += limit;
    poll_display();
    assert(lunar_lcd_pending_timeouts == 1 && !submits && !syncs);
    /* Completion by an external synchronous owner clears stale observation. */
    lcd_busy = selected = 0;
    poll_display();
    assert(!lcd_pending_deadline.active);
    valid = 1;
    poll_display();
    assert(submits == 1 && !lcd_pending_deadline.reported);
    for (unsigned i = 0; i < 15; ++i) {
        spi = 0x8000;
        poll_display();
    }
    assert(row == 16 && submits == 16 && syncs == 15);
    puts("LCD pending deadline: production integration PASS");
    return 0;
}
