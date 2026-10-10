/* SPDX-License-Identifier: MIT
 * Independently authored protocol emitter. Register values and command data
 * are facts recovered from guarded stock V15, not Felucca implementation.
 * Provenance and activation gates: notes/2026-10-09-lcd-runtime-prerequisites.md.
 */
#include "panel_probe.h"

struct panel_command {
    unsigned char command, count, data[14];
};
static const struct panel_command setup[] = {
    {0x2a, 4, {0, 0, 0, 0xef}},
    {0x2b, 4, {0, 0x28, 1, 0x17}},
    {0xb2, 5, {0x0c, 0x0c, 0x0c, 0, 0x33}},
    {0x20, 0, {0}},
    {0xb7, 1, {0x56}}, {0xbb, 1, {0x18}}, {0xc0, 1, {0x2c}},
    {0xc2, 1, {1}}, {0xc3, 1, {0x1f}}, {0xc4, 1, {0x20}},
    {0xc6, 1, {0x0f}}, {0xd0, 2, {0xa6, 0xa1}},
    {0xe0, 14, {0xd0, 0x0d, 0x14, 0x0b, 0x0b, 7, 0x3a, 0x44,
                0x50, 8, 0x13, 0x13, 0x2d, 0x32}},
    {0xe1, 14, {0xd0, 0x0d, 0x14, 0x0b, 0x0b, 7, 0x3a, 0x44,
                0x50, 8, 0x13, 0x13, 0x2d, 0x32}},
    {0x36, 1, {0}}, {0x3a, 1, {0x55}}, {0xe7, 1, {0}},
    {0x51, 1, {0xff}}, {0x21, 0, {0}}
};

static int command(const struct lunar_panel_transport *bus, unsigned char cmd,
                   const unsigned char *data, unsigned count)
{
    unsigned i;
    int success = bus->begin(bus->context, cmd);
    for (i = 0; success && i < count; ++i)
        success = bus->write(bus->context, data[i]);
    bus->end(bus->context);
    return success;
}

enum lunar_panel_result lunar_panel_probe(const struct lunar_panel_transport *bus)
{
    static const unsigned short bands[] = {0xffff, 0xf800, 0x07e0, 0x001f};
    unsigned i, row, column;
    int success;
    if (!bus || !bus->begin || !bus->write || !bus->end || !bus->wait_ms)
        return LUNAR_PANEL_INVALID;
    if (!bus->wait_ms(bus->context, 100)) return LUNAR_PANEL_DELAY_FAILED;
    if (!command(bus, 0x11, 0, 0)) return LUNAR_PANEL_TRANSFER_FAILED;
    if (!bus->wait_ms(bus->context, 120)) return LUNAR_PANEL_DELAY_FAILED;
    for (i = 0; i < sizeof setup / sizeof setup[0]; ++i)
        if (!command(bus, setup[i].command, setup[i].data, setup[i].count))
            return LUNAR_PANEL_TRANSFER_FAILED;
    success = bus->begin(bus->context, 0x2c);
    for (row = 0; success && row < 240; ++row) {
        unsigned short word = bands[row / 60];
        for (column = 0; success && column < 240; ++column) {
            success = bus->write(bus->context, (unsigned char)(word >> 8));
            if (success) success = bus->write(bus->context, (unsigned char)word);
        }
    }
    bus->end(bus->context);
    if (!success) return LUNAR_PANEL_TRANSFER_FAILED;
    if (!command(bus, 0x29, 0, 0)) return LUNAR_PANEL_TRANSFER_FAILED;
    return LUNAR_PANEL_OK;
}
