/* SPDX-License-Identifier: MIT
 * Independent bounded implementation of the stock V15 recovery contract.
 * Provenance/limits: notes/2026-10-05-softkey-efuse.md and recovery/README.md. */
#include "request.h"

static const unsigned char marker[16] = "usb_update_mode";
#define SELECT 1u
#define BUSY 2u
#define RTC (1u << 8)
#define START (1u << 4)

static int idle(struct lunar_recovery *s)
{
    unsigned n;
    for (n = 0; n < s->poll_limit; ++n)
        if (!(s->io.read(s->io.context, LUNAR_P33_CON) & BUSY)) return 1;
    return 0;
}
static void select_bus(struct lunar_recovery *s, unsigned selected)
{
    unsigned con = s->io.read(s->io.context, LUNAR_P33_CON);
    /* Never replay a transfer-start strobe while changing chip select. */
    s->io.write(s->io.context, LUNAR_P33_CON, (con & ~(SELECT | START)) | selected);
    s->io.sync(s->io.context);
}
static int send(struct lunar_recovery *s, unsigned byte)
{
    unsigned con;
    s->io.write(s->io.context, LUNAR_P33_DAT, byte);
    con = s->io.read(s->io.context, LUNAR_P33_CON);
    s->io.write(s->io.context, LUNAR_P33_CON, con | START);
    s->io.sync(s->io.context);
    return idle(s);
}
int lunar_recovery_bind(struct lunar_recovery *s, const struct lunar_recovery_io *io,
                        unsigned limit)
{
    if (!s || !io || !io->read || !io->write || !io->sync ||
        !io->mailbox_write || !io->mailbox_read || !limit || limit > 65536u) return 0;
    /* Explicit fields avoid a target compiler-generated libc memcpy. */
    s->io.context = io->context;
    s->io.read = io->read;
    s->io.write = io->write;
    s->io.sync = io->sync;
    s->io.mailbox_write = io->mailbox_write;
    s->io.mailbox_read = io->mailbox_read;
    s->poll_limit = limit;
    s->attempted = s->failed = 0;
    return 1;
}
int lunar_recovery_request(struct lunar_recovery *s)
{
    unsigned i;
    if (!s || s->attempted || !s->poll_limit || s->poll_limit > 65536u ||
        !s->io.read || !s->io.write || !s->io.sync ||
        !s->io.mailbox_write || !s->io.mailbox_read) return 0;
    s->attempted = 1;
    /* Refuse an existing selection; never deassert somebody else's transaction. */
    if (s->io.read(s->io.context, LUNAR_P33_CON) & (SELECT | RTC)) goto failure;
    if (!idle(s)) goto failure;
    for (i = 0; i < sizeof marker; ++i)
        s->io.mailbox_write(s->io.context, i, marker[i]);
    s->io.sync(s->io.context);
    for (i = 0; i < sizeof marker; ++i)
        if (s->io.mailbox_read(s->io.context, i) != marker[i]) goto failure;
    /* P33 OR opcode 0x20, P3_PR_PWR address 0xa0, chip-reset bit 4.
     * Only this operation is exposed; no generic address/value API. */
    select_bus(s, SELECT);
    if (!send(s, 0x20u) || !send(s, 0xa0u) || !send(s, 0x10u)) {
        select_bus(s, 0);
        goto failure;
    }
    select_bus(s, 0);
    return 1;
failure:
    s->failed = 1;
    return 0;
}

#ifdef LUNAR_PI32V2
static unsigned native_read(void *context, enum lunar_recovery_register reg)
{
    (void)context;
    if (reg == LUNAR_P33_CON) return *(volatile unsigned *)0x13e08u;
    if (reg == LUNAR_P33_DAT) return *(volatile unsigned *)0x13e0cu;
    return 0;
}
static void native_write(void *context, enum lunar_recovery_register reg, unsigned value)
{
    (void)context;
    if (reg == LUNAR_P33_CON) *(volatile unsigned *)0x13e08u = value;
    if (reg == LUNAR_P33_DAT) *(volatile unsigned *)0x13e0cu = value;
}
static void native_sync(void *context)
{
    (void)context;
    __asm__ volatile("csync;" ::: "memory");
}
static void native_mailbox_write(void *context, unsigned offset, unsigned char value)
{
    (void)context;
    if (offset < 16u) ((volatile unsigned char *)0x01c7fd80u)[offset] = value;
}
static unsigned char native_mailbox_read(void *context, unsigned offset)
{
    (void)context;
    return offset < 16u ? ((volatile unsigned char *)0x01c7fd80u)[offset] : 0;
}
void lunar_recovery_native_io(struct lunar_recovery_io *io)
{
    if (!io) return;
    io->context = 0;
    io->read = native_read;
    io->write = native_write;
    io->sync = native_sync;
    io->mailbox_write = native_mailbox_write;
    io->mailbox_read = native_mailbox_read;
}
#endif
