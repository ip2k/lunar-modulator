/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PANEL_PROBE_H
#define LUNAR_PANEL_PROBE_H

/* No MMIO implementation is provided. The optional panel-protocol link calls
 * this with a RAM-only offline sink, not a usable hardware backend. The eventual backend
 * must establish current-core/exception, power, clock and watchdog contracts;
 * each callback must complete in bounded time. A successful begin holds CS
 * until end. write transmits one data byte. end must release CS, including
 * after a failed begin/write. wait_ms must wait at least the requested time. */
struct lunar_panel_transport {
    void *context;
    int (*begin)(void *context, unsigned char command);
    int (*write)(void *context, unsigned char data);
    void (*end)(void *context);
    int (*wait_ms)(void *context, unsigned milliseconds);
};

enum lunar_panel_result {
    LUNAR_PANEL_OK = 0,
    LUNAR_PANEL_INVALID = 1,
    LUNAR_PANEL_TRANSFER_FAILED = 2,
    LUNAR_PANEL_DELAY_FAILED = 3
};

/* Emit the verified V15 panel setup and a 240x240 four-band RGB565 word probe.
 * A complete transport trace is offline evidence, not successful panel output.
 * No framebuffer, allocator, SDK, ROM, GPIO, SPI, IRQ or flash access. */
enum lunar_panel_result lunar_panel_probe(const struct lunar_panel_transport *);

/* The probe's first part, shared with the M5 pattern (m5_pattern.c): a 100 ms
 * wait, sleep-out 0x11, a 120 ms wait and the 21-record V15 setup. */
enum lunar_panel_result lunar_panel_setup(const struct lunar_panel_transport *);
/* One command with no data bytes (for example 0x29, display on). */
int lunar_panel_command(const struct lunar_panel_transport *, unsigned char command);
#endif
