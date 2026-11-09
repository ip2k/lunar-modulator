/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_SPI1_TRANSPORT_H
#define LUNAR_SPI1_TRANSPORT_H
#include "panel_probe.h"

/* Only these six WL82 registers are exposed. Their addresses/pin assignments
 * are verified against primary headers and stock V15 (see display/README.md).
 * Callbacks must finish in bounded time; no concurrent peripheral owner/IRQ. */
enum lunar_spi1_register {
    LUNAR_SPI1_CON, LUNAR_SPI1_BAUD, LUNAR_SPI1_BUF,
    LUNAR_PANEL_PORTC_OUT, LUNAR_PANEL_PORTC_DIR, LUNAR_PANEL_IOMAP_CON1
};
struct lunar_spi1_io {
    void *context;
    unsigned (*read)(void *, enum lunar_spi1_register);
    void (*write)(void *, enum lunar_spi1_register, unsigned);
    int (*wait_ms)(void *, unsigned); /* Calibrated, at least requested duration. */
};
struct lunar_spi1 {
    struct lunar_spi1_io io;
    unsigned poll_limit;
    unsigned configured, active, failed;
};
/* Software-only binding; rejects zero or >65536 polls. No register access. */
int lunar_spi1_bind(struct lunar_spi1 *, const struct lunar_spi1_io *, unsigned,
                    struct lunar_panel_transport *);
/* Explicit MMIO activation. Caller must FIRST establish core/exception,
 * exclusive GPIO/SPI ownership, clock/power and watchdog contracts. No PA2
 * access: its exact electrical role remains unresolved. Not called at boot. */
int lunar_spi1_configure(struct lunar_spi1 *);
/* Direct 32-bit volatile backend. Binding does not read/write hardware. The
 * delay callback/context are supplied by the caller; no guessed busy delay. */
void lunar_spi1_native_io(struct lunar_spi1_io *, void *, int (*)(void *, unsigned));
#endif
