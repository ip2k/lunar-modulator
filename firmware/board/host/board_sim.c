/* SPDX-License-Identifier: MIT
 * Host-only simulation for tests/test_board_layer.py: a register file behind
 * the board allow-list, a two-595 chain with a key matrix, a polled ADC, a
 * UART1 RX DMA ring, and a panel byte sink. Never built for the target.
 */
#include <string.h>
#include "../board_io.h"
#include "../../display/panel_probe.h"

#define PA(f) (LUNAR_PA + (f))
#define PB(f) (LUNAR_PB + (f))

static unsigned regs[LUNAR_BOARD_REGISTERS];
static unsigned reads, writes, syncs, clock_edges, latch_edges, shift_reg, latched;
static unsigned char pressed_cells[256];
static unsigned adc_value[16], adc_delay, adc_countdown;
static unsigned uart_since_latch;
static unsigned char ring[256] __attribute__((aligned(16)));
static unsigned ring_bytes, ring_head;
static unsigned latched_trace[64], latched_count;

static unsigned selected_column(void)
{
    unsigned c, found = 0xff;
    for (c = 0; c < 11; ++c)
        if (!(latched & (1u << c))) {
            if (found != 0xff) return 0xfe; /* two columns: model error */
            found = c;
        }
    return found;
}

static unsigned input(unsigned reg)
{
    unsigned column = selected_column(), packed = 0x3f, bit;
    if (column < 11)
        for (bit = 0; bit < 6; ++bit)
            if (pressed_cells[(column << 4) | bit]) packed &= ~(1u << bit);
    if (reg == PA(LUNAR_IN))
        return ~0u & ~(((~packed & 1u) ? 1u : 0) | ((~packed & 0x1eu) << 4));
    return ~0u & ~((~packed & 0x20u) << 2);
}

static unsigned sim_read(void *context, enum lunar_board_register reg)
{
    (void)context;
    ++reads;
    if (reg == PA(LUNAR_IN) || reg == PB(LUNAR_IN)) return input(reg);
    if (reg == LUNAR_ADC_CON) {
        if ((regs[reg] & 0x10u) && adc_countdown && !--adc_countdown) regs[reg] |= 0x80u;
        return regs[reg];
    }
    if (reg == LUNAR_ADC_RES) return adc_value[(regs[LUNAR_ADC_CON] >> 8) & 15u];
    return regs[reg];
}

static void sim_write(void *context, enum lunar_board_register reg, unsigned value)
{
    unsigned old = regs[reg];
    (void)context;
    ++writes;
    regs[reg] = value;
    if (reg == PA(LUNAR_OUT)) {
        if (!(old & 8u) && (value & 8u)) {
            ++clock_edges;
            shift_reg = ((shift_reg << 1) | ((value >> 4) & 1u)) & 0xffffu;
        }
        if (!(old & 2u) && (value & 2u)) {
            ++latch_edges;
            latched = shift_reg;
            if (latched_count < 64) latched_trace[latched_count++] = latched;
        }
    }
    if (reg == LUNAR_ADC_CON) {
        if ((value & 0x50u) == 0x50u && !(value & 0x80u)) adc_countdown = adc_delay;
        if (!(value & 0x10u)) regs[reg] &= ~0x80u;
    }
    if (reg == LUNAR_UART1_CON0 && (value & 0x80u)) {
        regs[LUNAR_UART1_HRXCNT] = uart_since_latch;
        uart_since_latch = 0;
    }
    if (reg == LUNAR_UART1_CON0) regs[reg] &= ~0x1480u; /* strobe bits read 0 */
}

static void sim_sync(void *context)
{
    (void)context;
    ++syncs;
}

static struct lunar_board_io io = {0, sim_read, sim_write, sim_sync};

const struct lunar_board_io *sim_io(void) { return &io; }
void sim_reset(void)
{
    memset(regs, 0, sizeof regs);
    memset(pressed_cells, 0, sizeof pressed_cells);
    memset(adc_value, 0, sizeof adc_value);
    memset(ring, 0, sizeof ring);
    reads = writes = syncs = clock_edges = latch_edges = shift_reg = 0;
    latched = 0xffffu;
    adc_delay = 3;
    adc_countdown = uart_since_latch = ring_head = latched_count = 0;
    ring_bytes = sizeof ring;
    regs[PA(LUNAR_DIR)] = regs[PB(LUNAR_DIR)] = regs[LUNAR_PH + LUNAR_DIR] = 0xffffu;
}
void sim_press(unsigned cell, int down) { pressed_cells[cell & 0xffu] = (unsigned char)!!down; }
unsigned sim_reg(unsigned reg) { return reg < LUNAR_BOARD_REGISTERS ? regs[reg] : 0; }
void sim_set_reg(unsigned reg, unsigned v) { if (reg < LUNAR_BOARD_REGISTERS) regs[reg] = v; }
unsigned sim_counter(unsigned which)
{
    const unsigned values[] = {reads, writes, syncs, clock_edges, latch_edges, latched, latched_count};
    return which < 7 ? values[which] : 0;
}
unsigned sim_latched_at(unsigned i) { return i < latched_count ? latched_trace[i] : 0; }
void sim_adc(unsigned channel, unsigned value, unsigned delay)
{
    adc_value[channel & 15u] = value;
    adc_delay = delay;
}
volatile unsigned char *sim_ring(unsigned *bytes) { *bytes = ring_bytes; return ring; }
/* The DMA engine writes n bytes at its own head and counts them. */
void sim_uart_rx(const unsigned char *data, unsigned n)
{
    unsigned i;
    for (i = 0; i < n; ++i) {
        ring[ring_head] = data[i];
        ring_head = (ring_head + 1u) % ring_bytes;
    }
    uart_since_latch += n;
}

/* Panel sink: 0x01 cmd = begin, 0x00 b = data, 0x02 = end, 0x03 lo hi = wait. */
static unsigned char *sink;
static unsigned sink_size, sink_used, sink_overflow;
static void put(unsigned char a)
{
    if (sink_used < sink_size) sink[sink_used++] = a;
    else sink_overflow = 1;
}
static int sink_begin(void *c, unsigned char cmd) { (void)c; put(1); put(cmd); return 1; }
static int sink_write(void *c, unsigned char b) { (void)c; put(0); put(b); return 1; }
static void sink_end(void *c) { (void)c; put(2); }
static int sink_wait(void *c, unsigned ms) { (void)c; put(3); put((unsigned char)ms); put((unsigned char)(ms >> 8)); return 1; }
static struct lunar_panel_transport sink_bus = {0, sink_begin, sink_write, sink_end, sink_wait};
const struct lunar_panel_transport *sim_sink(unsigned char *buffer, unsigned size)
{
    sink = buffer;
    sink_size = size;
    sink_used = sink_overflow = 0;
    return &sink_bus;
}
unsigned sim_sink_used(void) { return sink_overflow ? 0xffffffffu : sink_used; }
