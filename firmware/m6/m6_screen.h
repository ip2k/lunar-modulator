/* SPDX-License-Identifier: MIT
 * M6 panel: a static frame (title and build id) drawn once before audio
 * starts, then eight status lines redrawn round robin in small steps, so the
 * panel never holds up an audio block. Host-testable: everything goes
 * through `struct lunar_panel_transport` (display/panel_probe.h).
 */
#ifndef LUNAR_M6_SCREEN_H
#define LUNAR_M6_SCREEN_H

#include "../display/panel_probe.h"
#include "m6_core.h"

#define LUNAR_M6_SCREEN_SIZE 240u
#define LUNAR_M6_LINES 8u
#define LUNAR_M6_LINE_CHARS 19u
#define LUNAR_M6_LINE_LEFT 6u
#define LUNAR_M6_LINE_TOP0 64u
#define LUNAR_M6_LINE_PITCH 20u
#define LUNAR_M6_LINE_ROWS 14u   /* 7 glyph rows at scale 2 */
/* The V15 setup's RASET is rows 40..279 (panel_probe.c, 0x2b 00 28 01 17)
 * and CASET columns 0..239; a partial window adds 40 to its rows. */
#define LUNAR_M6_ROW_OFFSET 40u

struct lunar_m6_screen {
    const struct lunar_panel_transport *bus;
    const volatile struct lunar_m6_status *status;
    unsigned line, phase, x, y, failed, passes;
    unsigned char glyph[LUNAR_M6_LINE_CHARS];
    unsigned length;
};

/* RGB565 of the static frame at (x, y): border, "LUNAR M6", the build id. */
unsigned lunar_m6_frame_pixel(unsigned x, unsigned y, const char *build_id);
/* lunar_panel_setup, the full frame, display on (0x29). Blocking. */
enum lunar_panel_result lunar_m6_screen_frame(const struct lunar_panel_transport *bus,
                                              const char *build_id);

/* Text of status line `line` (0..7), at most LUNAR_M6_LINE_CHARS characters,
 * NUL-terminated; returns its length. Characters: space - . : 0-9 A-Z. */
unsigned lunar_m6_screen_text(const volatile struct lunar_m6_status *status,
                              unsigned line, char *out);

void lunar_m6_screen_init(struct lunar_m6_screen *screen,
                          const struct lunar_panel_transport *bus,
                          const volatile struct lunar_m6_status *status);
/* One step of at most five bytes on the bus: a window command, the memory
 * write command, or one pixel. Returns 1 while working, 0 once failed. Fits
 * lunar_m6_platform.report (context = the screen). */
int lunar_m6_screen_step(void *screen);

#endif
