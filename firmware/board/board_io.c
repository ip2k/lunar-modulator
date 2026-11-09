/* SPDX-License-Identifier: MIT
 * Independently authored register allow-list. Addresses: pinned WL82.h
 * (psfr 0x50000, lsfr 0x10000, map_adr(grp, adr) = (64 * grp + adr) * 4).
 */
#include "board_io.h"

#define PORT_A 0x50000u /* map_adr(0x00, 0x00) */
#define PORT_B 0x50040u /* map_adr(0x00, 0x10) */
#define PORT_H 0x501c0u /* map_adr(0x00, 0x70) */
#define IOMAP 0x5101cu  /* map_adr(0x10, 0x07): CON0 */
#define CLOCK 0x10000u  /* lsfr map_adr(0x00, 0x00): PWR_CON */
#define UART1 0x12100u  /* lsfr map_adr(0x21, 0x00) */
#define ADC 0x13100u    /* lsfr map_adr(0x31, 0x00) */
#define ANA 0x11900u    /* lsfr map_adr(0x19, 0x00): WLA_CON0 */

unsigned lunar_board_address(enum lunar_board_register reg)
{
    unsigned r = (unsigned)reg;
    if (r < (unsigned)LUNAR_PB) return PORT_A + 4u * r;
    if (r < (unsigned)LUNAR_PH) return PORT_B + 4u * (r - LUNAR_PB);
    if (r < (unsigned)LUNAR_IOMAP_CON2) return PORT_H + 4u * (r - LUNAR_PH);
    switch (reg) {
    case LUNAR_IOMAP_CON2: return IOMAP + 0x08u;
    case LUNAR_IOMAP_CON3: return IOMAP + 0x0cu;
    case LUNAR_CLOCK_CON1: return CLOCK + 0x10u; /* CLK_CON1, 5th word */
    case LUNAR_UART1_CON0: return UART1 + 0x00u;
    case LUNAR_UART1_CON1: return UART1 + 0x04u;
    case LUNAR_UART1_BAUD: return UART1 + 0x08u;
    case LUNAR_UART1_OTCNT: return UART1 + 0x10u;
    case LUNAR_UART1_RXSADR: return UART1 + 0x1cu;
    case LUNAR_UART1_RXEADR: return UART1 + 0x20u;
    case LUNAR_UART1_RXCNT: return UART1 + 0x24u;
    case LUNAR_UART1_HRXCNT: return UART1 + 0x28u;
    case LUNAR_ADC_CON: return ADC + 0x00u;
    case LUNAR_ADC_RES: return ADC + 0x04u;
    case LUNAR_ANA_WLA_CON0: return ANA + 0x00u;
    case LUNAR_ANA_PLL_CON1: return ANA + 0xa4u; /* after WLA_CON0..39, PLL_CON0 */
    default: return 0;
    }
}

unsigned lunar_board_width(enum lunar_board_register reg)
{
    if (!lunar_board_address(reg)) return 0;
    switch (reg) {
    case LUNAR_UART1_CON0: case LUNAR_UART1_CON1:
    case LUNAR_UART1_BAUD: case LUNAR_UART1_HRXCNT:
        return 2;
    default:
        return 4;
    }
}

int lunar_board_io_valid(const struct lunar_board_io *io)
{
    return io && io->read && io->write && io->sync;
}

void lunar_board_change(const struct lunar_board_io *io,
                        enum lunar_board_register reg, unsigned clear, unsigned set)
{
    unsigned value = io->read(io->context, reg);
    io->write(io->context, reg, (value & ~clear) | set);
}

#ifdef LUNAR_PI32V2
static unsigned native_read(void *context, enum lunar_board_register reg)
{
    unsigned address = lunar_board_address(reg);
    (void)context;
    if (!address) return 0;
    if (lunar_board_width(reg) == 2) return *(volatile unsigned short *)address;
    return *(volatile unsigned *)address;
}
static void native_write(void *context, enum lunar_board_register reg, unsigned value)
{
    unsigned address = lunar_board_address(reg);
    (void)context;
    if (!address) return;
    if (lunar_board_width(reg) == 2) *(volatile unsigned short *)address = (unsigned short)value;
    else *(volatile unsigned *)address = value;
}
static void native_sync(void *context)
{
    (void)context;
    __asm__ volatile("csync;" ::: "memory");
}
void lunar_board_native_io(struct lunar_board_io *io)
{
    if (!io) return;
    io->context = 0;
    io->read = native_read;
    io->write = native_write;
    io->sync = native_sync;
}
#endif
