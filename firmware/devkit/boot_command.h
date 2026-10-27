/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_BOOT_COMMAND_H
#define LUNAR_DEVKIT_BOOT_COMMAND_H
#include <stdint.h>

enum lunar_boot_action { LUNAR_BOOT_NONE, LUNAR_BOOT_PONG,
                         LUNAR_BOOT_ARMED, LUNAR_BOOT_ENTER };
struct lunar_boot_command {
    char line[32];
    unsigned used, dropping, armed;
    uint32_t armed_ms;
};
/* Feed from a task, never an audio interrupt. Exact newline-delimited
 * ARM then ENTER commands must arrive within five seconds. Not authentication:
 * this is a private, physically connected diagnostic UART. */
enum lunar_boot_action lunar_boot_command_feed(struct lunar_boot_command *,
                                              unsigned char, uint32_t now_ms);
/* app_main must call this before allocating the workload; zero means ready. */
int lunar_devkit_boot_control_start(void);
#endif
