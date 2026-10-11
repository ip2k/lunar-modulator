/* SPDX-License-Identifier: MIT. Offline proposal; never boot-installed. */
#include "../recovery/request.h"
extern unsigned char __bss_begin[], __bss_end[];
struct probe_state {
    unsigned magic, incoming_r0, status, core, reset_requested;
    struct lunar_recovery recovery;
};
volatile struct probe_state lunar_ram_probe;
void lunar_ram_recovery_start(unsigned incoming_r0)
{
    unsigned char *p;
    unsigned core;
    struct lunar_recovery_io io;
    for (p = __bss_begin; p < __bss_end; ++p) *p = 0;
    __asm__ volatile("%0 = cnum;" : "=r"(core));
    lunar_ram_probe.magic = 0x4c525250u; /* LRRP */
    lunar_ram_probe.incoming_r0 = incoming_r0;
    lunar_ram_probe.core = core;
    lunar_ram_probe.status = 1;
    /* No core release, routing, clock, pad or write-guard changes. */
    if (core != 0) {
        lunar_ram_probe.status = 2;
        goto stop;
    }
    lunar_recovery_native_io(&io);
    if (!lunar_recovery_bind((struct lunar_recovery *)&lunar_ram_probe.recovery,
                             &io, 65536u)) {
        lunar_ram_probe.status = 3;
        goto stop;
    }
    lunar_ram_probe.status = 4;
    lunar_ram_probe.reset_requested = lunar_recovery_request(
        (struct lunar_recovery *)&lunar_ram_probe.recovery);
    lunar_ram_probe.status = lunar_ram_probe.reset_requested ? 5u : 6u;
stop:
    /* This deliberately never returns through an unproven ROM call ABI.
     * If reset fails, stop; stock flash is intact for the owner's power-cycle. */
    for (;;) __asm__ volatile("nop;" ::: "memory");
}
