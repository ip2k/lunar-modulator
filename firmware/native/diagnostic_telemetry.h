/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DIAGNOSTIC_TELEMETRY_H
#define LUNAR_DIAGNOSTIC_TELEMETRY_H
#include <stdint.h>
#include "render_stage_profile.h"

/* Private diagnostic protocol, not a release API. Noncommercial SysEx ID 7D,
 * LUNAR tag, schema 1, fourteen unsigned 32-bit values (five little-endian
 * 7-bit digits each), F7. Each frame fits in the 64-packet USB-MIDI ring.
 * No commands, flash access, allocation or application callbacks. */
#define LUNAR_DIAGNOSTIC_FIELDS 14u
#define LUNAR_DIAGNOSTIC_BYTES (9u + 5u * LUNAR_DIAGNOSTIC_FIELDS)
#define LUNAR_DIAGNOSTIC_PACKETS ((LUNAR_DIAGNOSTIC_BYTES + 2u) / 3u)

/* Schema 2 is opt-in stage profiling. It reports nine independent stage
 * windows; sequence dispatch is inclusive of sound callbacks, so values are
 * observations and must not be summed. */
#define LUNAR_PROFILE_FIELDS (1u + 3u * LUNAR_RENDER_PROFILE_STAGE_COUNT)
#define LUNAR_PROFILE_BYTES (9u + 5u * LUNAR_PROFILE_FIELDS)
#define LUNAR_PROFILE_PACKETS ((LUNAR_PROFILE_BYTES + 2u) / 3u)

static inline void lunar_diagnostic_packets(
    uint32_t packets[LUNAR_DIAGNOSTIC_PACKETS],
    const uint32_t values[LUNAR_DIAGNOSTIC_FIELDS])
{
    uint8_t bytes[LUNAR_DIAGNOSTIC_BYTES] =
        {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 1};
    for (unsigned i = 0; i < LUNAR_DIAGNOSTIC_FIELDS; ++i)
        for (unsigned j = 0; j < 5u; ++j)
            bytes[8u + i * 5u + j] = (uint8_t)((values[i] >> (j * 7u)) & 127u);
    bytes[LUNAR_DIAGNOSTIC_BYTES - 1u] = 0xf7;
    for (unsigned i = 0; i < LUNAR_DIAGNOSTIC_PACKETS; ++i) {
        unsigned at = i * 3u;
        unsigned left = LUNAR_DIAGNOSTIC_BYTES - at;
        unsigned n = left < 3u ? left : 3u;
        uint32_t packet = left > 3u ? 4u : 4u + n;
        for (unsigned j = 0; j < n; ++j)
            packet |= (uint32_t)bytes[at + j] << (8u * (j + 1u));
        packets[i] = packet;
    }
}

static inline uint8_t lunar_profile_wire_byte(
    unsigned at, const uint32_t values[LUNAR_PROFILE_FIELDS])
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 2};
    if (at < sizeof prefix) return prefix[at];
    if (at == LUNAR_PROFILE_BYTES - 1u) return 0xf7;
    unsigned data_at = at - (unsigned)sizeof prefix;
    if (data_at >= 5u * LUNAR_PROFILE_FIELDS) return 0;
    unsigned value = data_at / 5u;
    unsigned digit = data_at % 5u;
    return (uint8_t)((values[value] >> (digit * 7u)) & 127u);
}

static inline uint32_t lunar_profile_packet(
    const uint32_t values[LUNAR_PROFILE_FIELDS], unsigned index)
{
    if (index >= LUNAR_PROFILE_PACKETS) return 0;
    unsigned at = index * 3u;
    unsigned left = LUNAR_PROFILE_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j)
        packet |= (uint32_t)lunar_profile_wire_byte(at + j, values) << (8u * (j + 1u));
    return packet;
}

/* Schema 3: one immutable post-platform-init clock configuration snapshot.
 * Raw values only; no frequency interpretation and no register writes. */
#define LUNAR_CLOCK_FIELDS 4u
#define LUNAR_CLOCK_BYTES (9u + 5u * LUNAR_CLOCK_FIELDS)
#define LUNAR_CLOCK_PACKETS ((LUNAR_CLOCK_BYTES + 2u) / 3u)
#define LUNAR_PLL_FIELDS 4u
#define LUNAR_PLL_BYTES (9u + 5u * LUNAR_PLL_FIELDS)
#define LUNAR_PLL_PACKETS ((LUNAR_PLL_BYTES + 2u) / 3u)
#define LUNAR_PRODUCER_GAP_FIELDS 10u
#define LUNAR_PRODUCER_GAP_BYTES (9u + 5u * LUNAR_PRODUCER_GAP_FIELDS)
#define LUNAR_PRODUCER_GAP_PACKETS ((LUNAR_PRODUCER_GAP_BYTES + 2u) / 3u)
static inline uint32_t lunar_clock_packet(const uint32_t values[LUNAR_CLOCK_FIELDS],
                                         unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 3};
    if (index >= LUNAR_CLOCK_PACKETS) return 0;
    unsigned at = index * 3u;
    unsigned left = LUNAR_CLOCK_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_CLOCK_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

/* Schema 4: supplemental raw PLL configuration inputs. Keep this a separate
 * frame so schema-3 consumers remain byte-compatible and strict. */
static inline uint32_t lunar_pll_packet(const uint32_t values[LUNAR_PLL_FIELDS],
                                       unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 4};
    if (index >= LUNAR_PLL_PACKETS) return 0;
    unsigned at = index * 3u;
    unsigned left = LUNAR_PLL_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_PLL_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

/* Schema 5: main-loop refill/publication cadence and split display wait/work.
 * All values are raw uint32 ticks/counters; host timing calibration is separate. */
static inline uint8_t lunar_producer_gap_wire_byte(
    unsigned at, const uint32_t values[LUNAR_PRODUCER_GAP_FIELDS])
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 5};
    if (at < sizeof prefix) return prefix[at];
    if (at == LUNAR_PRODUCER_GAP_BYTES - 1u) return 0xf7;
    unsigned data_at = at - (unsigned)sizeof prefix;
    if (data_at >= 5u * LUNAR_PRODUCER_GAP_FIELDS) return 0;
    unsigned value = data_at / 5u;
    unsigned digit = data_at % 5u;
    return (uint8_t)((values[value] >> (digit * 7u)) & 127u);
}

static inline uint32_t lunar_producer_gap_packet(
    const uint32_t values[LUNAR_PRODUCER_GAP_FIELDS], unsigned index)
{
    if (index >= LUNAR_PRODUCER_GAP_PACKETS) return 0;
    unsigned at = index * 3u;
    unsigned left = LUNAR_PRODUCER_GAP_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j)
        packet |= (uint32_t)lunar_producer_gap_wire_byte(at + j, values)
                  << (8u * (j + 1u));
    return packet;
}

/* Schema 6: cumulative IRQ occupancy and render elapsed/IRQ ticks. Per-source
 * times are inclusive; busy_ticks is the nesting union. Counters wrap uint32. */
#define LUNAR_IRQ_FIELDS 22u
#define LUNAR_IRQ_BYTES (9u + 5u * LUNAR_IRQ_FIELDS)
#define LUNAR_IRQ_PACKETS ((LUNAR_IRQ_BYTES + 2u) / 3u)
#define LUNAR_ENGINE_PROFILE_FIELDS 9u
#define LUNAR_ENGINE_PROFILE_BYTES (9u + 5u * LUNAR_ENGINE_PROFILE_FIELDS)
#define LUNAR_ENGINE_PROFILE_PACKETS ((LUNAR_ENGINE_PROFILE_BYTES + 2u) / 3u)
#define LUNAR_CPU_RATE_FIELDS 8u
#define LUNAR_CPU_RATE_BYTES (9u + 5u * LUNAR_CPU_RATE_FIELDS)
#define LUNAR_CPU_RATE_PACKETS ((LUNAR_CPU_RATE_BYTES + 2u) / 3u)
static inline uint32_t lunar_irq_packet(
    const uint32_t values[LUNAR_IRQ_FIELDS], unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 6};
    if (index >= LUNAR_IRQ_PACKETS) return 0;
    unsigned at = index * 3u, left = LUNAR_IRQ_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_IRQ_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

/* Schema 7: cumulative outer Render and internal RenderBlock ticks/calls for
 * Drums and SixOp. Outer time includes blocks; subtraction yields wrapper,
 * resampler and copy/loop remainder, not an isolated FIR measurement. */
static inline uint32_t lunar_engine_profile_packet(
    const uint32_t values[LUNAR_ENGINE_PROFILE_FIELDS], unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 7};
    if (index >= LUNAR_ENGINE_PROFILE_PACKETS) return 0;
    unsigned at = index * 3u, left = LUNAR_ENGINE_PROFILE_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_ENGINE_PROFILE_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

/* Schema 9: 4 globals and 16 cumulative counters per engine. Each stage
 * carries wall TIMER4 ticks plus tracked IRQ-union ticks, never CPU cycles. */
#define LUNAR_RESAMPLER_STAGE_FIELDS 36u
#define LUNAR_RESAMPLER_STAGE_BYTES (9u + 5u * LUNAR_RESAMPLER_STAGE_FIELDS)
#define LUNAR_RESAMPLER_STAGE_PACKETS ((LUNAR_RESAMPLER_STAGE_BYTES + 2u) / 3u)
static inline uint32_t lunar_resampler_stage_packet(
    const uint32_t values[LUNAR_RESAMPLER_STAGE_FIELDS], unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 9};
    if (index >= LUNAR_RESAMPLER_STAGE_PACKETS) return 0;
    unsigned at = index * 3u, left = LUNAR_RESAMPLER_STAGE_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_RESAMPLER_STAGE_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

/* Schema 8: fixed-work integer kernel elapsed raw TIMER4 ticks in XIP and
 * ordinary SRAM. This is not a CPU-frequency or instruction-cycle claim. */
static inline uint32_t lunar_cpu_rate_packet(
    const uint32_t values[LUNAR_CPU_RATE_FIELDS], unsigned index)
{
    static const uint8_t prefix[] = {0xf0, 0x7d, 'L', 'U', 'N', 'A', 'R', 8};
    if (index >= LUNAR_CPU_RATE_PACKETS) return 0;
    unsigned at = index * 3u, left = LUNAR_CPU_RATE_BYTES - at;
    unsigned n = left < 3u ? left : 3u;
    uint32_t packet = left > 3u ? 4u : 4u + n;
    for (unsigned j = 0; j < n; ++j) {
        unsigned pos = at + j;
        uint8_t byte;
        if (pos < sizeof prefix) byte = prefix[pos];
        else if (pos == LUNAR_CPU_RATE_BYTES - 1u) byte = 0xf7;
        else {
            unsigned data = pos - (unsigned)sizeof prefix;
            byte = (uint8_t)((values[data / 5u] >> (7u * (data % 5u))) & 127u);
        }
        packet |= (uint32_t)byte << (8u * (j + 1u));
    }
    return packet;
}

#endif
