/* SPDX-License-Identifier: MIT */
#include "boot_command.h"
#include <string.h>

enum lunar_boot_action lunar_boot_command_feed(struct lunar_boot_command *s,
                                              unsigned char byte, uint32_t now)
{
    enum lunar_boot_action action = LUNAR_BOOT_NONE;
    if (s->armed && (uint32_t)(now - s->armed_ms) >= 5000u) s->armed = 0;
    if (byte != '\n') {
        if (s->dropping) return action;
        if (byte == 0 || s->used == sizeof(s->line) - 1) {
            s->dropping = 1;
            s->armed = 0;
        } else s->line[s->used++] = (char)byte;
        return action;
    }
    if (!s->dropping) {
        if (s->used && s->line[s->used - 1] == '\r') --s->used;
        s->line[s->used] = 0;
        if (!strcmp(s->line, "LUNAR ARM UBOOT")) {
            s->armed = 1;
            s->armed_ms = now;
            action = LUNAR_BOOT_ARMED;
        } else {
            if (s->armed && !strcmp(s->line, "LUNAR ENTER UBOOT"))
                action = LUNAR_BOOT_ENTER;
            else if (!strcmp(s->line, "LUNAR PING")) action = LUNAR_BOOT_PONG;
            s->armed = 0;
        }
    }
    s->used = s->dropping = 0;
    return action;
}
