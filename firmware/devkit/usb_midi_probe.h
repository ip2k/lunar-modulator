/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic. */
#ifndef LUNAR_DEVKIT_USB_MIDI_PROBE_H
#define LUNAR_DEVKIT_USB_MIDI_PROBE_H

/* Starts the FM-1's USB-MIDI device (firmware/fm1/fm1_usb_sdk.c) on the kit's
 * USB0 port and never returns: every POLL_TICKS it takes at most one OUT
 * packet, logs its length and events on the debug UART, and echoes the
 * events back IN. Built only by prepare-devkit.py --usb-midi --boot-control. */
void lunar_devkit_usb_midi_probe(void);

#endif
