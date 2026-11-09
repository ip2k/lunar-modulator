/* SPDX-License-Identifier: MIT
 * Independently authored. Register addresses come from the pinned AC79 SDK
 * V1.2.13 header include_lib/driver/cpu/wl82/asm/WL82.h (Apache-2.0, facts
 * only); see firmware/board/README.md for the fact table and its marks.
 */
#ifndef LUNAR_BOARD_IO_H
#define LUNAR_BOARD_IO_H

/* Every WL82 GPIO port has these nine 32-bit fields, in this order. */
enum lunar_port_field {
    LUNAR_OUT, LUNAR_IN, LUNAR_DIR, LUNAR_DIE, LUNAR_PU, LUNAR_PD,
    LUNAR_HD0, LUNAR_HD, LUNAR_DIEH, LUNAR_PORT_FIELDS
};

/* The complete allow-list of board-layer registers. The display transport
 * (display/spi1_transport.c) and the timer (timing/timer4.c) keep their own,
 * smaller allow-lists. Nothing here is in the eFuse range 0x13700-0x1371F. */
enum lunar_board_register {
    LUNAR_PA = 0,                         /* LUNAR_PA + field */
    LUNAR_PB = LUNAR_PORT_FIELDS,         /* LUNAR_PB + field */
    LUNAR_PH = 2 * LUNAR_PORT_FIELDS,     /* LUNAR_PH + field */
    LUNAR_IOMAP_CON2 = 3 * LUNAR_PORT_FIELDS,
    LUNAR_IOMAP_CON3,
    LUNAR_CLOCK_CON1,
    LUNAR_UART1_CON0, LUNAR_UART1_CON1, LUNAR_UART1_BAUD, LUNAR_UART1_OTCNT,
    LUNAR_UART1_RXSADR, LUNAR_UART1_RXEADR, LUNAR_UART1_RXCNT,
    LUNAR_UART1_HRXCNT,
    LUNAR_ADC_CON, LUNAR_ADC_RES,
    LUNAR_ANA_WLA_CON0, LUNAR_ANA_PLL_CON1,
    LUNAR_BOARD_REGISTERS
};

/* read/write must complete in bounded time; sync orders earlier writes
 * (csync on pi32v2). The board layer never touches a register outside the
 * enum above, and every poll it performs has a caller-given limit. */
struct lunar_board_io {
    void *context;
    unsigned (*read)(void *context, enum lunar_board_register reg);
    void (*write)(void *context, enum lunar_board_register reg, unsigned value);
    void (*sync)(void *context);
};

int lunar_board_io_valid(const struct lunar_board_io *io);
/* Physical address of an allowed register, or 0 for anything else. */
unsigned lunar_board_address(enum lunar_board_register reg);
/* Access width in bytes (UART1 CON0/CON1/BAUD/HRXCNT are 16-bit), 0 if unknown. */
unsigned lunar_board_width(enum lunar_board_register reg);
/* Read-modify-write: (value & ~clear) | set. */
void lunar_board_change(const struct lunar_board_io *io,
                        enum lunar_board_register reg, unsigned clear, unsigned set);

#ifdef LUNAR_PI32V2
/* Direct volatile backend over the allow-list. Binding touches no hardware. */
void lunar_board_native_io(struct lunar_board_io *io);
#endif
#endif
