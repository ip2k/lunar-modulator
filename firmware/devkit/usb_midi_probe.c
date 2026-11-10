/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic.
 *
 * The kit run of the FM-1's USB-MIDI device (notes/2026-11-09-usb-midi.md
 * section 8): the same descriptors and glue as the FM-1 application, polled
 * from this task instead of the panel task.
 *
 * The OUT endpoint is read only every POLL_TICKS (500 ms), so a short packet
 * and a full one sent back to back both wait in the endpoint's two buffers
 * before the next read. Review finding R1: the reader must take one packet a
 * pass, by its own length (usb_read_rxcount), not 64 B across both. Each pass
 * logs the waiting packet's length before the read and the events it gave,
 * so the UART shows `rx=4 events=1` then `rx=64 events=16`, not one read of
 * 64 B that loses the second packet's tail.
 *
 * Events are echoed IN, so the host can also check the IN path. The worker
 * runs after the boot-control recovery window, so UART ARM/ENTER still
 * returns the kit to its ROM while this runs. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/usb.h"

#include "fm1_usb_midi.h"
#include "usb_midi_probe.h"

#ifndef LUNAR_FM1_USB_MIDI
#error usb_midi_probe.c is built only with LUNAR_FM1_USB_MIDI
#endif

#define POLL_TICKS 50u      /* SDK ticks are 10 ms */
#define REPORT_PASSES 20u   /* a stats line every 10 s */

static unsigned pass_events;

static void emit(void *context, const unsigned char packet[4])
{
    (void)context;
    ++pass_events;
    printf("LUNAR_USB event=%02x%02x%02x%02x echo=%d\n", packet[0], packet[1], packet[2],
           packet[3], lunar_usb_midi_send(packet));
}

static void report(unsigned passes)
{
    struct lunar_usb_midi_stats s;
    lunar_usb_midi_stats(&s);
    printf("LUNAR_USB stats passes=%u started=%u online=%u configurations=%u resets=%u "
           "received=%u sent=%u dropped=%u busy=%u power=0x%02x\n", passes, s.started, s.online,
           s.configurations, s.resets, s.received, s.sent, s.dropped, s.busy,
           (unsigned)usb_read_power(0));   /* musb POWER: bit 4 set would be high speed */
}

void lunar_devkit_usb_midi_probe(void)
{
    unsigned passes = 0;
    int started = lunar_usb_midi_start();
    printf("LUNAR_USB start=%d poll_ticks=%u\n", started, POLL_TICKS);
    if (!started) for (;;) os_time_dly(100);
    for (;;) {
        unsigned waiting = usb_read_rxcount(0, LUNAR_USB_MIDI_EP);
        unsigned got;
        pass_events = 0;
        got = lunar_usb_midi_poll(emit, 0);
        if (waiting || got)
            printf("LUNAR_USB pass=%u rx=%u events=%u\n", passes, waiting, got);
        if (++passes % REPORT_PASSES == 0u) report(passes);
        os_time_dly(POLL_TICKS);
    }
}
