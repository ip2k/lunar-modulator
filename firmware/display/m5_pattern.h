/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_M5_PATTERN_H
#define LUNAR_M5_PATTERN_H
#include "panel_probe.h"

#define LUNAR_M5_WIDTH 240u
#define LUNAR_M5_HEIGHT 240u
#define LUNAR_M5_ID_MAX 19u /* build-id characters shown; longer ids are cut */

/* RGB565 value of pixel (x, y) of the M5 test pattern: a one-pixel white
 * border, "LUNAR M5", the build id, "TEST PATTERN" on dark blue, and eight
 * colour bars (white, yellow, cyan, green, magenta, red, blue, black).
 * Characters outside space - . : 0-9 A-Z (lower case is folded) draw blank. */
unsigned lunar_m5_pixel(unsigned x, unsigned y, const char *build_id);

/* lunar_panel_setup, then 0x2c with the 240x240 pattern rendered row by row
 * (no framebuffer), then 0x29. Offline/host-testable like lunar_panel_probe;
 * on the device it is only as good as the transport and delays behind `bus`. */
enum lunar_panel_result lunar_panel_m5_pattern(const struct lunar_panel_transport *bus,
                                               const char *build_id);
#endif
