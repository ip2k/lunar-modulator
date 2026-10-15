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

#endif
