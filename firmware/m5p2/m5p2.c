/* SPDX-License-Identifier: MIT
 * m5-plan-2 portable logic (see m5p2.h for what changed from M5 and why).
 *
 * Register facts (all already used by earlier images):
 *   JL_TIMER4 0x10800: CON +0, CNT +4, PRD +8; CON 0x29 runs it from the
 *     oscillator divided by 16, 1 << 14 stops it and clears pending
 *     [verified on the dev kit: notes/2026-11-09-m6-image.md, wdtprobe].
 *   P33 watchdog kick: lunar_ramtest_wdt_kick (ramtest.c) [verified on the
 *     dev kit: notes/2026-11-10-devkit-watchdog-probes.md, run b].
 *   SPI1 0x11d00 (CON, BAUD +4, BUF +8), PORTC OUT 0x50080, DIR 0x50088,
 *     IOMAP_CON1 0x51020: the M5 panel path (display/spi1_transport.c)
 *     [reported: Felucca, fm1-nes; never run on silicon].
 *   PA2 backlight, the 595 matrix and the LED lines: board/matrix.c
 *     [reported: Felucca, fm1-nes].
 *   Boot marker "usb_update_mode\0" at 0x01c7fd80: with it set, a watchdog
 *     reset lands in the ROM with SRAM kept [verified on the dev kit, K3].
 */
#include "m5p2.h"

#include "../board/board_io.h"
#include "../board/matrix.h"
#include "../display/m5_pattern.h"
#include "../display/panel_probe.h"
#include "../display/spi1_transport.h"
#include "../third_party/fm1-nes/fm1_keys.h"

#define TIMER4_CON 0x10800u
#define TIMER4_CNT 0x10804u
#define TIMER4_PRD 0x10808u
#define TIMER_STOP (1u << 14)
#define TIMER_RUN 0x29u
#define TIMER_MASK 0x7fffu
#define SPI1_CON 0x11d00u
#define SPI1_BAUD 0x11d04u
#define SPI1_BUF 0x11d08u
#define PORTC_OUT 0x50080u
#define PORTC_DIR 0x50088u
#define IOMAP_CON1 0x51020u
#define SPI_PENDING (1u << 15)
#define SPI_CLEAR (1u << 14)
#define TIMER_DEAD_FLAG 0x100u /* in the stage crumb: TIMER4 failed at some point */

static const unsigned marker_words[4] = {
    0x5f627375u, 0x61647075u, 0x6d5f6574u, 0x0065646fu /* "usb_update_mode\0" */
};

struct m5p2 {
    struct lunar_m5p2_io *io;
    const struct lunar_m5p2_config *cfg;
    unsigned crumb[LUNAR_M5P2_CRUMB_WORDS];
    unsigned timer_live, last_count, total, last_kick, kicked;
    unsigned stub_reads, stub_writes, spi_pending, flags;
    struct lunar_board_io board;
    struct lunar_spi1_io spi_io;
    struct lunar_spi1 spi;
    struct lunar_panel_transport panel;
};

/* ---- output (trace builds only) ---------------------------------------- */

static void puts_(struct m5p2 *m, const char *s)
{
    if (m->cfg->trace) lunar_ramtest_puts(&m->io->base, s);
}

static void putu_(struct m5p2 *m, unsigned value)
{
    if (m->cfg->trace) lunar_ramtest_putu(&m->io->base, value);
}

static void puthex(struct m5p2 *m, unsigned value)
{
    static const char digits[] = "0123456789abcdef";
    char text[11];
    unsigned i;
    if (!m->cfg->trace) return;
    text[0] = '0';
    text[1] = 'x';
    for (i = 0; i < 8u; ++i) text[2u + i] = digits[(value >> (28u - 4u * i)) & 15u];
    text[10] = 0;
    lunar_ramtest_puts(&m->io->base, text);
}

static void field(struct m5p2 *m, const char *name, unsigned value)
{
    puts_(m, " ");
    puts_(m, name);
    puts_(m, "=");
    putu_(m, value);
}

/* ---- breadcrumbs ---------------------------------------------------------- */

static void crumb(struct m5p2 *m, unsigned index, unsigned value)
{
    m->crumb[index] = value;
    m->io->base.write(m->io->base.context, LUNAR_M5P2_CRUMBS + 4u * index, 4, value);
}

/* ---- TIMER4 stopwatch, wrap-accumulated ----------------------------------- */

static unsigned poll(struct m5p2 *m)
{
    unsigned now = m->io->base.read(m->io->base.context, TIMER4_CNT, 4) & TIMER_MASK;
    unsigned delta = (now - m->last_count) & TIMER_MASK;
    m->last_count = now;
    m->total += delta;
    return delta;
}

static void stage(struct m5p2 *m, unsigned value)
{
    crumb(m, LUNAR_M5P2_C_STAGE, value | m->flags);
    if (m->timer_live) crumb(m, LUNAR_M5P2_C_TICKS, m->total);
    puts_(m, "LUNAR_M5P2 stage=");
    putu_(m, value);
    field(m, "ticks", m->total);
    field(m, "elapsed_ms", m->crumb[LUNAR_M5P2_C_ELAPSED_MS]);
    field(m, "kicks", m->crumb[LUNAR_M5P2_C_KICKS]);
    field(m, "max_gap", m->crumb[LUNAR_M5P2_C_MAX_GAP]);
    puts_(m, "\r\n");
}

static void timer_dead(struct m5p2 *m)
{
    m->timer_live = 0;
    m->flags |= TIMER_DEAD_FLAG;
    crumb(m, LUNAR_M5P2_C_STAGE, m->crumb[LUNAR_M5P2_C_STAGE] | TIMER_DEAD_FLAG);
    puts_(m, "LUNAR_M5P2 timer=dead\r\n");
}

/* ---- the watchdog ---------------------------------------------------------- */

static unsigned kick(struct m5p2 *m)
{
    unsigned con = 0;
    if (m->timer_live) {
        unsigned gap;
        poll(m);
        gap = m->total - m->last_kick;
        if (m->kicked && gap > m->crumb[LUNAR_M5P2_C_MAX_GAP])
            crumb(m, LUNAR_M5P2_C_MAX_GAP, gap);
        m->last_kick = m->total;
        m->kicked = 1;
    }
    if (lunar_ramtest_wdt_kick(&m->io->base, &con))
        crumb(m, LUNAR_M5P2_C_KICKS, m->crumb[LUNAR_M5P2_C_KICKS] + 1u);
    else
        crumb(m, LUNAR_M5P2_C_KICK_FAILURES, m->crumb[LUNAR_M5P2_C_KICK_FAILURES] + 1u);
    return con;
}

/* ---- waits: every slice starts with a kick --------------------------------- */

static void spin_ms(struct m5p2 *m, unsigned ms)
{
    while (ms--) m->io->spin(m->io->base.context, LUNAR_M5P2_SPIN_PER_MS);
}

/* Nominal milliseconds at the 40 MHz binding, in slices of at most 10 ms.
 * A TIMER4 that stops counting (or never reaches a slice) switches every
 * later wait to an uncalibrated spin, still kicked per slice. */
static void wait_ms(struct m5p2 *m, unsigned ms)
{
    crumb(m, LUNAR_M5P2_C_ELAPSED_MS, m->crumb[LUNAR_M5P2_C_ELAPSED_MS] + ms);
    while (ms) {
        unsigned slice = ms < LUNAR_M5P2_SLICE_MS ? ms : LUNAR_M5P2_SLICE_MS;
        ms -= slice;
        kick(m);
        if (m->timer_live) {
            unsigned need = slice * LUNAR_M5P2_TICKS_PER_MS, got = 0, stall = 0, polls = 0;
            while (got < need) {
                unsigned delta = poll(m);
                got += delta;
                if (delta) stall = 0;
                else if (++stall >= LUNAR_M5P2_STALL_POLLS) break;
                if (++polls >= LUNAR_M5P2_SLICE_POLLS) break;
            }
            if (got >= need) continue;
            timer_dead(m);
        }
        spin_ms(m, slice);
    }
}

/* Spin-timed: `units` pieces of LUNAR_M5P2_SPIN_UNIT, each after a kick, in
 * the same LUNAR_M5P2_SPIN_CHUNK steps as measure(), so one half-period of
 * cadence B is exactly 20 measured blocks. TIMER4's 15-bit count wraps every
 * 21.8 ms at 24 MHz: a whole unit (31.6 ms on the kit) between two polls lost
 * wraps on the kit (notes/2026-11-14-m5-plan-2.md), so poll every chunk. */
static void spin_units(struct m5p2 *m, unsigned units)
{
    while (units--) {
        unsigned i;
        kick(m);
        for (i = 0; i < LUNAR_M5P2_SPIN_UNIT / LUNAR_M5P2_SPIN_CHUNK; ++i) {
            m->io->spin(m->io->base.context, LUNAR_M5P2_SPIN_CHUNK);
            if (m->timer_live) poll(m);
        }
    }
}

/* ---- the FM-1 pins, or the kit's stubs ------------------------------------- */

static unsigned board_read(void *context, enum lunar_board_register reg)
{
    struct m5p2 *m = context;
    unsigned address = lunar_board_address(reg), width = lunar_board_width(reg);
    if (m->cfg->stub_pins) { ++m->stub_reads; return 0; }
    if (!address || !width) return 0;
    return m->io->base.read(m->io->base.context, address, width);
}

static void board_write(void *context, enum lunar_board_register reg, unsigned value)
{
    struct m5p2 *m = context;
    unsigned address = lunar_board_address(reg), width = lunar_board_width(reg);
    if (m->cfg->stub_pins) { ++m->stub_writes; return; }
    if (!address || !width) return;
    m->io->base.write(m->io->base.context, address, width, value);
}

static void board_sync(void *context)
{
    struct m5p2 *m = context;
    m->io->base.sync(m->io->base.context);
}

static unsigned spi_address(enum lunar_spi1_register reg)
{
    switch (reg) {
    case LUNAR_SPI1_CON: return SPI1_CON;
    case LUNAR_SPI1_BAUD: return SPI1_BAUD;
    case LUNAR_SPI1_BUF: return SPI1_BUF;
    case LUNAR_PANEL_PORTC_OUT: return PORTC_OUT;
    case LUNAR_PANEL_PORTC_DIR: return PORTC_DIR;
    case LUNAR_PANEL_IOMAP_CON1: return IOMAP_CON1;
    }
    return 0;
}

/* Kit stub: no access reaches the pins; SPI1's pending flag is faked so the
 * byte stream runs at the speed of its register calls. */
static unsigned spi_read(void *context, enum lunar_spi1_register reg)
{
    struct m5p2 *m = context;
    unsigned address = spi_address(reg);
    if (m->cfg->stub_pins) {
        ++m->stub_reads;
        return reg == LUNAR_SPI1_CON && m->spi_pending ? SPI_PENDING : 0;
    }
    if (!address) return 0;
    return m->io->base.read(m->io->base.context, address, 4);
}

static void spi_write(void *context, enum lunar_spi1_register reg, unsigned value)
{
    struct m5p2 *m = context;
    unsigned address = spi_address(reg);
    if (m->cfg->stub_pins) {
        ++m->stub_writes;
        if (reg == LUNAR_SPI1_BUF) m->spi_pending = 1;
        if (reg == LUNAR_SPI1_CON && (value & SPI_CLEAR)) m->spi_pending = 0;
        return;
    }
    if (!address) return;
    m->io->base.write(m->io->base.context, address, 4, value);
}

static int spi_wait(void *context, unsigned ms)
{
    wait_ms(context, ms);
    return 1;
}

static void backlight(struct m5p2 *m, unsigned on)
{
    if (on) lunar_backlight_on(&m->board);
    else lunar_backlight_off(&m->board);
    puts_(m, "LUNAR_M5P2 pa2=");
    putu_(m, on);
    field(m, "ticks", m->total);
    puts_(m, "\r\n");
}

/* ---- the panel label ------------------------------------------------------- */

void lunar_m5p2_label(char *out, unsigned size, const char *build_id,
                      unsigned wdt_con, unsigned ticks_per_block)
{
    static const char digits[] = "0123456789ABCDEF";
    char tail[10];
    unsigned n = 0, i;
    if (!out || !size) return;
    if (ticks_per_block > 0xfffffu) ticks_per_block = 0xfffffu;
    tail[0] = ' ';
    tail[1] = digits[(wdt_con >> 4) & 15u];
    tail[2] = digits[wdt_con & 15u];
    tail[3] = ' ';
    for (i = 0; i < 5u; ++i) tail[4u + i] = digits[(ticks_per_block >> (16u - 4u * i)) & 15u];
    tail[9] = 0;
    for (i = 0; build_id && build_id[i] && n + 1u < size; ++i) out[n++] = build_id[i];
    for (i = 0; tail[i] && n + 1u < size; ++i) out[n++] = tail[i];
    out[n] = 0;
}

/* ---- the sequence ---------------------------------------------------------- */

static void report_previous(struct m5p2 *m)
{
    unsigned words[LUNAR_M5P2_CRUMB_WORDS], i, valid;
    for (i = 0; i < LUNAR_M5P2_CRUMB_WORDS; ++i)
        words[i] = m->io->base.read(m->io->base.context, LUNAR_M5P2_CRUMBS + 4u * i, 4);
    valid = words[0] == LUNAR_M5P2_MAGIC &&
            words[LUNAR_M5P2_CRUMB_WORDS - 1u] == ~LUNAR_M5P2_MAGIC;
    puts_(m, "LUNAR_M5P2 prev valid=");
    putu_(m, valid);
    for (i = 0; i < LUNAR_M5P2_CRUMB_WORDS; ++i) {
        puts_(m, " ");
        puthex(m, words[i]);
    }
    puts_(m, "\r\n");
}

static int timer_start(struct m5p2 *m)
{
    unsigned first, stall;
    struct lunar_ramtest_io *io = &m->io->base;
    io->write(io->context, TIMER4_CON, 4, TIMER_STOP);
    io->sync(io->context);
    io->write(io->context, TIMER4_CNT, 4, 0);
    io->write(io->context, TIMER4_PRD, 4, TIMER_MASK);
    io->write(io->context, TIMER4_CON, 4, TIMER_RUN);
    io->sync(io->context);
    first = io->read(io->context, TIMER4_CNT, 4) & TIMER_MASK;
    m->last_count = first;
    for (stall = 0; stall < LUNAR_M5P2_STALL_POLLS; ++stall)
        if (poll(m)) return 1;
    return 0;
}

static void measure(struct m5p2 *m)
{
    unsigned start, i;
    kick(m);
    start = m->total;
    for (i = 0; i < LUNAR_M5P2_BLOCK / LUNAR_M5P2_SPIN_CHUNK; ++i) {
        m->io->spin(m->io->base.context, LUNAR_M5P2_SPIN_CHUNK);
        poll(m);
    }
    crumb(m, LUNAR_M5P2_C_TICKS_PER_BLOCK, m->total - start);
    puts_(m, "LUNAR_M5P2 measure");
    field(m, "spins", LUNAR_M5P2_BLOCK);
    field(m, "ticks_per_block", m->total - start);
    puts_(m, "\r\n");
    kick(m);
}

static enum lunar_panel_result draw(struct m5p2 *m)
{
    char label[LUNAR_M5_ID_MAX + 1u];
    unsigned x, y;
    int success;
    enum lunar_panel_result result;
    lunar_m5p2_label(label, sizeof label, m->cfg->build_id, m->crumb[LUNAR_M5P2_C_WDT_CON],
                     m->crumb[LUNAR_M5P2_C_TICKS_PER_BLOCK]);
    result = lunar_panel_setup(&m->panel);
    if (result != LUNAR_PANEL_OK) return result;
    stage(m, LUNAR_M5P2_SETUP_OK);
    /* Display on before the frame, so a partial frame shows. */
    if (!lunar_panel_command(&m->panel, 0x29)) return LUNAR_PANEL_TRANSFER_FAILED;
    stage(m, LUNAR_M5P2_DISPLAY_ON);
    kick(m);
    success = m->panel.begin(m->panel.context, 0x2c);
    for (y = 0; success && y < LUNAR_M5_HEIGHT; ++y) {
        kick(m); /* one per pixel row */
        for (x = 0; success && x < LUNAR_M5_WIDTH; ++x) {
            unsigned word = lunar_m5_pixel(x, y, label);
            if (!(x & 15u) && m->timer_live) poll(m); /* no lost wraps on a slow row */
            success = m->panel.write(m->panel.context, (unsigned char)(word >> 8));
            if (success) success = m->panel.write(m->panel.context, (unsigned char)word);
        }
    }
    m->panel.end(m->panel.context);
    return success ? LUNAR_PANEL_OK : LUNAR_PANEL_TRANSFER_FAILED;
}

/* Every column held 1 ms with `leds` lit; each 1 ms wait kicks. */
static void hold(struct m5p2 *m, unsigned ms, unsigned leds)
{
    unsigned column = 0;
    while (ms--) {
        lunar_matrix_select(&m->board, column, leds);
        if (++column == LUNAR_MATRIX_COLUMNS) column = 0;
        wait_ms(m, 1);
    }
    lunar_matrix_release(&m->board);
}

static void finish_line(struct m5p2 *m, const char *how)
{
    puts_(m, "LUNAR_M5P2 finish=");
    puts_(m, how);
    field(m, "ticks", m->total);
    field(m, "elapsed_ms", m->crumb[LUNAR_M5P2_C_ELAPSED_MS]);
    field(m, "kicks", m->crumb[LUNAR_M5P2_C_KICKS]);
    field(m, "kick_failures", m->crumb[LUNAR_M5P2_C_KICK_FAILURES]);
    field(m, "max_gap", m->crumb[LUNAR_M5P2_C_MAX_GAP]);
    field(m, "cycles", m->crumb[LUNAR_M5P2_C_CYCLES]);
    field(m, "stub_reads", m->stub_reads);
    field(m, "stub_writes", m->stub_writes);
    puts_(m, "\r\n");
}

enum lunar_m5p2_result lunar_m5p2_run(struct lunar_m5p2_io *io,
                                      const struct lunar_m5p2_config *config)
{
    struct m5p2 state, *m = &state;
    unsigned i, blinks, wdt_con, kicked;
    enum lunar_panel_result panel;
    if (!io || !config || !io->base.read || !io->base.write || !io->base.sync ||
        !io->spin || !config->build_id || config->finish > LUNAR_M5P2_RESET_APP)
        return LUNAR_M5P2_FAIL_ARGS;
    /* No structure assignment: the JieLi target lowers it to memcpy. */
    for (i = 0; i < LUNAR_M5P2_CRUMB_WORDS; ++i) m->crumb[i] = 0;
    m->io = io;
    m->cfg = config;
    m->timer_live = m->last_count = m->total = m->last_kick = m->kicked = 0;
    m->stub_reads = m->stub_writes = m->spi_pending = m->flags = 0;

    /* 1. The watchdog first: the ROM armed it ~4 s before the end. Called
     * directly, so a previous run's breadcrumbs are still intact to report. */
    wdt_con = 0;
    kicked = lunar_ramtest_wdt_kick(&io->base, &wdt_con);

    if (config->trace) {
        lunar_ramtest_uart_init(&io->base);
        io->base.uart_failed = 0;
        puts_(m, "\r\nLUNAR_M5P2 ready=1 build=");
        puts_(m, config->build_id);
        puts_(m, " entry=0x01c02000 wdt_con=");
        puthex(m, wdt_con);
        field(m, "mailbox", config->mailbox);
        field(m, "stub", config->stub_pins);
        field(m, "finish", config->finish);
        puts_(m, "\r\n");
        report_previous(m);
    }

    for (i = 0; i < LUNAR_M5P2_CRUMB_WORDS; ++i) crumb(m, i, 0);
    crumb(m, LUNAR_M5P2_C_MAGIC, LUNAR_M5P2_MAGIC);
    crumb(m, LUNAR_M5P2_C_CHECK, ~LUNAR_M5P2_MAGIC);
    crumb(m, LUNAR_M5P2_C_WDT_CON, wdt_con);
    crumb(m, LUNAR_M5P2_C_PANEL, 0xffu);
    crumb(m, kicked ? LUNAR_M5P2_C_KICKS : LUNAR_M5P2_C_KICK_FAILURES, 1u);
    if (config->mailbox)
        for (i = 0; i < 4u; ++i)
            io->base.write(io->base.context, LUNAR_RAMTEST_BOOT_MARKER + 4u * i, 4,
                           marker_words[i]);
    io->base.sync(io->base.context);
    stage(m, LUNAR_M5P2_ENTRY);

    /* 2. A sign that needs only a GPIO: PA2 low, backlight on. */
    m->board.context = m;
    m->board.read = board_read;
    m->board.write = board_write;
    m->board.sync = board_sync;
    backlight(m, 1);
    stage(m, LUNAR_M5P2_PA2_ON);

    /* 3. TIMER4 as a stopwatch, then the clock evidence. */
    m->timer_live = (unsigned)timer_start(m);
    if (m->timer_live) {
        m->last_kick = m->total;
        stage(m, LUNAR_M5P2_TIMER_OK);
    } else {
        m->flags |= TIMER_DEAD_FLAG;
        stage(m, LUNAR_M5P2_TIMER_DEAD);
    }
    measure(m);
    stage(m, LUNAR_M5P2_MEASURED);
    /* Cadence A: three TIMER4-timed flashes, 400 ms off and on at the 40 MHz
     * binding (667 ms at 24 MHz). Skipped if TIMER4 is dead. */
    if (m->timer_live) {
        for (i = 0; i < 3u; ++i) {
            backlight(m, 0);
            wait_ms(m, LUNAR_M5P2_FLASH_MS);
            backlight(m, 1);
            wait_ms(m, LUNAR_M5P2_FLASH_MS);
        }
        stage(m, LUNAR_M5P2_CADENCE_A);
    }
    /* Cadence B: CPU-spin-timed flashes, three (five if TIMER4 is dead). */
    for (i = 0; i < (m->timer_live ? 3u : 5u); ++i) {
        backlight(m, 0);
        spin_units(m, LUNAR_M5P2_FLASH_UNITS);
        backlight(m, 1);
        spin_units(m, LUNAR_M5P2_FLASH_UNITS);
    }
    stage(m, LUNAR_M5P2_CADENCE_B);

    /* 4. The panel: SPI1, setup, display on, then the frame. */
    m->spi_io.context = m;
    m->spi_io.read = spi_read;
    m->spi_io.write = spi_write;
    m->spi_io.wait_ms = spi_wait;
    panel = LUNAR_PANEL_INVALID;
    if (lunar_spi1_bind(&m->spi, &m->spi_io, LUNAR_M5P2_SPI_POLLS, &m->panel) &&
        lunar_spi1_configure(&m->spi)) {
        stage(m, LUNAR_M5P2_SPI_OK);
        panel = draw(m);
        crumb(m, LUNAR_M5P2_C_PANEL, (unsigned)panel);
        if (panel == LUNAR_PANEL_OK) stage(m, LUNAR_M5P2_FRAME_DONE);
    }

    /* 5. The LED blink code, forever or until finish_ms: 3 = frame sent
     * with TIMER4 alive, 2 = frame sent on spin waits, 1 = panel failed. */
    lunar_matrix_init(&m->board);
    stage(m, LUNAR_M5P2_BLINKING);
    blinks = panel != LUNAR_PANEL_OK ? 1u : (m->flags & TIMER_DEAD_FLAG) ? 2u : 3u;
    for (;;) {
        unsigned n;
        for (n = 0; n < blinks; ++n) {
            hold(m, 200, LUNAR_LED_LINES);
            hold(m, 200, 0);
        }
        hold(m, 1000, 0);
        crumb(m, LUNAR_M5P2_C_CYCLES, m->crumb[LUNAR_M5P2_C_CYCLES] + 1u);
        if (m->timer_live) crumb(m, LUNAR_M5P2_C_TICKS, m->total);
        if (config->finish_ms && m->crumb[LUNAR_M5P2_C_ELAPSED_MS] >= config->finish_ms) break;
    }

    stage(m, LUNAR_M5P2_FINISHING);
    if (config->finish == LUNAR_M5P2_RESET_APP) {
        finish_line(m, "reset_app");
        io->spin(io->base.context, LUNAR_M5P2_SPIN_UNIT); /* let the last byte leave */
        lunar_ramtest_reset_to_app(&io->base);
        return LUNAR_M5P2_RESET_FAILED;
    }
    if (config->finish == LUNAR_M5P2_STOP_KICKING) {
        finish_line(m, "stop_kicking");
        /* Heartbeats without kicks: the watchdog should end them ~4 s after
         * the last kick. 500 ms each at the 40 MHz binding, TIMER4 only. */
        for (i = 0; i < config->beats && m->timer_live; ++i) {
            unsigned got = 0, polls = 0;
            while (got < 500u * LUNAR_M5P2_TICKS_PER_MS && ++polls < (1u << 24)) got += poll(m);
            crumb(m, LUNAR_M5P2_C_TICKS, m->total);
            puts_(m, "LUNAR_M5P2 beat=");
            putu_(m, i + 1u);
            field(m, "ticks", m->total);
            field(m, "since_kick", m->total - m->last_kick);
            puts_(m, "\r\n");
        }
        return LUNAR_M5P2_STOPPED;
    }
    finish_line(m, "returned");
    return LUNAR_M5P2_RETURNED;
}
