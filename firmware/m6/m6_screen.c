/* SPDX-License-Identifier: MIT
 * M6 panel (m6_screen.h). The 5x7 glyphs are a copy of the ones drawn for
 * display/m5_pattern.c, kept here so the approved M5 image's sources stay
 * untouched; the panel setup is panel_probe.c's (stock V15 facts).
 */
#include "m6_screen.h"

#define BACKGROUND 0x0008u /* dark blue */
#define WHITE 0xffffu
#define YELLOW 0xffe0u

static const char charset[] = " -.:0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
static const unsigned char glyphs[][7] = {
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, /* ' ' */
    {0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00}, /* '-' */
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x0c, 0x0c}, /* '.' */
    {0x00, 0x0c, 0x0c, 0x00, 0x0c, 0x0c, 0x00}, /* ':' */
    {0x0e, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0e}, /* '0' */
    {0x04, 0x0c, 0x04, 0x04, 0x04, 0x04, 0x0e}, /* '1' */
    {0x0e, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1f}, /* '2' */
    {0x1e, 0x01, 0x01, 0x0e, 0x01, 0x01, 0x1e}, /* '3' */
    {0x02, 0x06, 0x0a, 0x12, 0x1f, 0x02, 0x02}, /* '4' */
    {0x1f, 0x10, 0x1e, 0x01, 0x01, 0x11, 0x0e}, /* '5' */
    {0x06, 0x08, 0x10, 0x1e, 0x11, 0x11, 0x0e}, /* '6' */
    {0x1f, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}, /* '7' */
    {0x0e, 0x11, 0x11, 0x0e, 0x11, 0x11, 0x0e}, /* '8' */
    {0x0e, 0x11, 0x11, 0x0f, 0x01, 0x02, 0x0c}, /* '9' */
    {0x0e, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}, /* 'A' */
    {0x1e, 0x11, 0x11, 0x1e, 0x11, 0x11, 0x1e}, /* 'B' */
    {0x0e, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0e}, /* 'C' */
    {0x1c, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1c}, /* 'D' */
    {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f}, /* 'E' */
    {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10}, /* 'F' */
    {0x0e, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0f}, /* 'G' */
    {0x11, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}, /* 'H' */
    {0x0e, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0e}, /* 'I' */
    {0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0c}, /* 'J' */
    {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}, /* 'K' */
    {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f}, /* 'L' */
    {0x11, 0x1b, 0x15, 0x15, 0x11, 0x11, 0x11}, /* 'M' */
    {0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11}, /* 'N' */
    {0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}, /* 'O' */
    {0x1e, 0x11, 0x11, 0x1e, 0x10, 0x10, 0x10}, /* 'P' */
    {0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d}, /* 'Q' */
    {0x1e, 0x11, 0x11, 0x1e, 0x14, 0x12, 0x11}, /* 'R' */
    {0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e}, /* 'S' */
    {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}, /* 'T' */
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}, /* 'U' */
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04}, /* 'V' */
    {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0a}, /* 'W' */
    {0x11, 0x11, 0x0a, 0x04, 0x0a, 0x11, 0x11}, /* 'X' */
    {0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04}, /* 'Y' */
    {0x1f, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1f}, /* 'Z' */
};

static unsigned glyph_index(char c)
{
    unsigned i;
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    for (i = 0; charset[i]; ++i)
        if (charset[i] == c) return i;
    return 0;
}

/* Is (x, y) lit by glyph cells `g` (n of them) whose top-left is (left, top)? */
static int lit(const unsigned char *g, unsigned n, unsigned x, unsigned y,
               unsigned left, unsigned top, unsigned scale)
{
    unsigned width, cell, column;
    if (!n || y < top || y >= top + 7u * scale || x < left) return 0;
    width = n * 6u * scale - scale;
    if (x >= left + width) return 0;
    cell = (x - left) / scale;
    column = cell % 6u;
    if (column == 5u) return 0;
    return (glyphs[g[cell / 6u]][(y - top) / scale] >> (4u - column)) & 1u;
}

static unsigned to_glyphs(const char *s, unsigned char *g, unsigned limit)
{
    unsigned n = 0;
    while (s && n < limit && s[n]) {
        g[n] = (unsigned char)glyph_index(s[n]);
        ++n;
    }
    return n;
}

unsigned lunar_m6_frame_pixel(unsigned x, unsigned y, const char *build_id)
{
    unsigned char title[8], id[LUNAR_M6_LINE_CHARS];
    unsigned n;
    if (x >= LUNAR_M6_SCREEN_SIZE || y >= LUNAR_M6_SCREEN_SIZE) return 0;
    if (!x || !y || x == LUNAR_M6_SCREEN_SIZE - 1u || y == LUNAR_M6_SCREEN_SIZE - 1u)
        return WHITE;
    to_glyphs("LUNAR M6", title, 8u);
    if (lit(title, 8u, x, y, (LUNAR_M6_SCREEN_SIZE - (8u * 18u - 3u)) / 2u, 10u, 3u))
        return WHITE;
    n = to_glyphs(build_id, id, LUNAR_M6_LINE_CHARS);
    if (n && lit(id, n, x, y, (LUNAR_M6_SCREEN_SIZE - (n * 12u - 2u)) / 2u, 40u, 2u))
        return YELLOW;
    return BACKGROUND;
}

static int command(const struct lunar_panel_transport *bus, unsigned char cmd,
                   const unsigned char *data, unsigned count)
{
    unsigned i;
    int success = bus->begin(bus->context, cmd);
    for (i = 0; success && i < count; ++i) success = bus->write(bus->context, data[i]);
    bus->end(bus->context);
    return success;
}

enum lunar_panel_result lunar_m6_screen_frame(const struct lunar_panel_transport *bus,
                                              const char *build_id)
{
    unsigned x, y;
    int success;
    enum lunar_panel_result result = lunar_panel_setup(bus);
    if (result != LUNAR_PANEL_OK) return result;
    success = bus->begin(bus->context, 0x2c);
    for (y = 0; success && y < LUNAR_M6_SCREEN_SIZE; ++y)
        for (x = 0; success && x < LUNAR_M6_SCREEN_SIZE; ++x) {
            unsigned word = lunar_m6_frame_pixel(x, y, build_id);
            success = bus->write(bus->context, (unsigned char)(word >> 8));
            if (success) success = bus->write(bus->context, (unsigned char)word);
        }
    bus->end(bus->context);
    if (!success || !lunar_panel_command(bus, 0x29)) return LUNAR_PANEL_TRANSFER_FAILED;
    return LUNAR_PANEL_OK;
}

static unsigned put_s(char *out, unsigned n, const char *s)
{
    while (*s && n < LUNAR_M6_LINE_CHARS) out[n++] = *s++;
    return n;
}

static unsigned put_u(char *out, unsigned n, uint32_t value)
{
    return n + lunar_m6_put_u(out + n, LUNAR_M6_LINE_CHARS - n, value);
}

static unsigned put_permille(char *out, unsigned n, uint32_t permille)
{
    n = put_u(out, n, permille / 10u);
    n = put_s(out, n, ".");
    return put_u(out, n, permille % 10u);
}

unsigned lunar_m6_screen_text(const volatile struct lunar_m6_status *s,
                              unsigned line, char *out)
{
    unsigned n = 0;
    switch (line) {
    case 0:
        n = put_u(out, put_s(out, n, "BLK "), s->blocks);
        break;
    case 1: /* mean stopwatch ticks per block over the last window */
        n = put_u(out, put_s(out, n, "TPB "), s->win_interval / LUNAR_M6_WINDOW);
        break;
    case 2: /* fs if the stopwatch oscillator is 24 MHz */
        n = put_u(out, put_s(out, n, "FS24 "),
                  lunar_m6_fs_estimate(s->win_interval, LUNAR_M6_TICK_HZ_24M));
        break;
    case 3: /* fs if it is 40 MHz */
        n = put_u(out, put_s(out, n, "FS40 "),
                  lunar_m6_fs_estimate(s->win_interval, LUNAR_M6_TICK_HZ_40M));
        break;
    case 4:
        n = put_permille(out, put_s(out, n, "LOAD "),
                         lunar_m6_load_permille(s->win_render, s->win_interval));
        n = put_permille(out, put_s(out, n, " MAX "),
                         s->interval_min == 0xffffffffu ? 0u
                         : lunar_m6_load_permille(s->busy_max, s->interval_min));
        break;
    case 5:
        n = put_u(out, put_s(out, n, "LATE "), s->late);
        n = put_u(out, put_s(out, n, " MISS "), s->missed);
        break;
    case 6:
        n = put_s(out, n, "PCM ");
        n += lunar_m6_put_hex(out + n, LUNAR_M6_LINE_CHARS - n, s->pcm_hash);
        break;
    default:
        n = put_u(out, put_s(out, n, "STEP "), s->step);
        n = put_s(out, n, s->alnk0_result < 0 ? " RC -" : " RC ");
        n = put_u(out, n, (uint32_t)(s->alnk0_result < 0 ? -s->alnk0_result : s->alnk0_result));
        n = put_u(out, put_s(out, n, " F "), s->flags);
        break;
    }
    out[n] = 0;
    return n;
}

void lunar_m6_screen_init(struct lunar_m6_screen *screen,
                          const struct lunar_panel_transport *bus,
                          const volatile struct lunar_m6_status *status)
{
    screen->bus = bus;
    screen->status = status;
    screen->line = screen->phase = screen->x = screen->y = 0;
    screen->failed = screen->passes = screen->length = 0;
}

static int window(const struct lunar_panel_transport *bus, unsigned char cmd,
                  unsigned first, unsigned last)
{
    unsigned char data[4];
    data[0] = (unsigned char)(first >> 8);
    data[1] = (unsigned char)first;
    data[2] = (unsigned char)(last >> 8);
    data[3] = (unsigned char)last;
    return command(bus, cmd, data, 4u);
}

int lunar_m6_screen_step(void *context)
{
    struct lunar_m6_screen *screen = context;
    const struct lunar_panel_transport *bus = screen->bus;
    unsigned top = LUNAR_M6_LINE_TOP0 + screen->line * LUNAR_M6_LINE_PITCH;
    int success = 1;
    if (screen->failed) return 0;
    switch (screen->phase) {
    case 0: {
        char text[LUNAR_M6_LINE_CHARS + 1];
        lunar_m6_screen_text(screen->status, screen->line, text);
        screen->length = to_glyphs(text, screen->glyph, LUNAR_M6_LINE_CHARS);
        success = window(bus, 0x2a, 0, LUNAR_M6_SCREEN_SIZE - 1u);
        break;
    }
    case 1:
        success = window(bus, 0x2b, top + LUNAR_M6_ROW_OFFSET,
                         top + LUNAR_M6_ROW_OFFSET + LUNAR_M6_LINE_ROWS - 1u);
        break;
    case 2:
        success = bus->begin(bus->context, 0x2c);
        screen->x = screen->y = 0;
        break;
    default: {
        unsigned word = lit(screen->glyph, screen->length, screen->x, screen->y,
                            LUNAR_M6_LINE_LEFT, 0, 2u) ? WHITE : BACKGROUND;
        if (screen->x == 0 || screen->x == LUNAR_M6_SCREEN_SIZE - 1u) word = WHITE; /* border */
        success = bus->write(bus->context, (unsigned char)(word >> 8));
        if (success) success = bus->write(bus->context, (unsigned char)word);
        if (++screen->x == LUNAR_M6_SCREEN_SIZE) {
            screen->x = 0;
            if (++screen->y == LUNAR_M6_LINE_ROWS) {
                bus->end(bus->context);
                screen->phase = 0;
                if (++screen->line == LUNAR_M6_LINES) {
                    screen->line = 0;
                    ++screen->passes;
                }
                return success ? 1 : (screen->failed = 1, 0);
            }
        }
        return success ? 1 : (bus->end(bus->context), screen->failed = 1, 0);
    }
    }
    if (!success) {
        if (screen->phase == 2) bus->end(bus->context);
        screen->failed = 1;
        return 0;
    }
    ++screen->phase;
    return 1;
}
