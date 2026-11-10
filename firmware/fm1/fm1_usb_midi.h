/* SPDX-License-Identifier: MIT
 * USB-MIDI 1.0 device for the FM-1 application: descriptors, string
 * descriptors, the IN batch and the packet encoder. Portable C99 with no SDK
 * header, host-tested byte for byte (tests/test_fm1_usb_midi.py).
 *
 * Written from the USB 2.0 specification (chapter 9), the USB Device Class
 * Definition for MIDI Devices 1.0 and the stock FM-1's own descriptor bytes,
 * read from its V15 app.bin [verified: bytes, notes/2026-11-09-usb-midi.md].
 * No SDK or Linux header is used: the SDK's ch9.h is Linux-derived and its
 * uac_audio*.h are GPL-2.0 (CLAUDE.md).
 *
 * The device is VID:PID 4C4A:C755, product "FM-1", full speed, as stock
 * [verified: bench 2026-09-06, V15 bytes]. Unlike stock it has no USB audio:
 * two interfaces (audio control, MIDIStreaming) where stock has five.
 */
#ifndef LUNAR_FM1_USB_MIDI_H
#define LUNAR_FM1_USB_MIDI_H

#define LUNAR_USB_MIDI_VID 0x4c4au
#define LUNAR_USB_MIDI_PID 0xc755u
#define LUNAR_USB_MIDI_EP 4u                /* 0x84 IN, 0x04 OUT, as stock */
#define LUNAR_USB_MIDI_MAX_PACKET 64u
#define LUNAR_USB_MIDI_INTERFACES 2u
#define LUNAR_USB_MIDI_DEVICE_BYTES 18u
#define LUNAR_USB_MIDI_CONFIG_HEADER_BYTES 9u
#define LUNAR_USB_MIDI_FUNCTION_BYTES 92u   /* AC 18 + MS 74 */
#define LUNAR_USB_MIDI_CONFIG_BYTES (LUNAR_USB_MIDI_CONFIG_HEADER_BYTES + LUNAR_USB_MIDI_FUNCTION_BYTES)
#define LUNAR_USB_MIDI_SERIAL_BYTES 34u     /* 16 UTF-16LE hex digits */

/* The 18-byte device descriptor. */
const unsigned char *lunar_usb_midi_device_descriptor(void);

/* The configuration descriptor's first 9 bytes, with wTotalLength and
 * bNumInterfaces zero: the SDK's set_descriptor fills both. */
const unsigned char *lunar_usb_midi_config_header(void);

/* The audio-control and MIDIStreaming interfaces, numbered `first` and
 * `first + 1`, into `out` (LUNAR_USB_MIDI_FUNCTION_BYTES). Returns the
 * length, or 0 when `first` leaves no room for both below 8. */
unsigned lunar_usb_midi_function(unsigned char *out, unsigned first);

/* The whole configuration descriptor, interfaces 0 and 1, into `out`
 * (LUNAR_USB_MIDI_CONFIG_BYTES): what a host reads. Returns the length. */
unsigned lunar_usb_midi_config(unsigned char *out);

/* String descriptors. Index 0 is the language list (US English), 2 the
 * product "FM-1", 3 the serial number: the first 8 bytes of `id` (the
 * flash UUID, as the SDK and stock derive it) as 16 upper-case hex digits,
 * or "0000000000000000" when `id` is null. Any other index is an empty
 * string. Returns the length written (out[0]). */
unsigned lunar_usb_midi_string(unsigned index, const unsigned char *id, unsigned char *out);

/* One MIDI message as a USB-MIDI 1.0 event packet on cable 0. Channel voice
 * messages and single-byte system real-time messages; returns 0 for
 * anything else (SysEx and system common are not sent). */
int lunar_usb_midi_encode(unsigned status, unsigned data1, unsigned data2,
                          unsigned char packet[4]);

/* Event packets waiting for the IN endpoint: up to one full-speed bulk
 * packet. Filled by the panel task, sent when the endpoint is free; a packet
 * that finds the batch full is dropped and counted (never wait in a task
 * that feeds the audio path). */
struct lunar_usb_midi_batch {
    unsigned char data[LUNAR_USB_MIDI_MAX_PACKET];
    unsigned length, dropped;
};

void lunar_usb_midi_batch_reset(struct lunar_usb_midi_batch *b);
int lunar_usb_midi_batch_add(struct lunar_usb_midi_batch *b, const unsigned char packet[4]);

/* Calls `emit` for each event packet in a received OUT transfer of
 * `length` bytes, skipping CIN 0 and 1 (reserved; zero padding) and a
 * trailing partial packet. Returns the packets passed on. */
unsigned lunar_usb_midi_split(const unsigned char *data, unsigned length,
                              void (*emit)(void *ctx, const unsigned char packet[4]), void *ctx);

/* ---- the SDK glue (fm1_usb_sdk.c; pi32v2 builds with LUNAR_FM1_USB_MIDI) */
struct lunar_usb_midi_stats {
    unsigned started, online;         /* online: configured by the host now */
    unsigned configurations, resets;  /* SET_CONFIGURATION(1) and bus resets seen */
    unsigned received, sent;          /* event packets */
    unsigned dropped, busy;           /* IN batch full; IN endpoint still busy */
};

/* Brings the device controller up, attaches to the bus and installs the
 * control interrupt below ALNK0's priority. Returns 1 on success. */
int lunar_usb_midi_start(void);

/* One pass from the panel task: take a received OUT transfer, if any,
 * through `emit`, and send the IN batch when the endpoint is free. Never
 * waits. Returns the event packets received. */
unsigned lunar_usb_midi_poll(void (*emit)(void *ctx, const unsigned char packet[4]), void *ctx);

/* Queues one event packet for the host; 0 when not configured or full. */
int lunar_usb_midi_send(const unsigned char packet[4]);

void lunar_usb_midi_stats(struct lunar_usb_midi_stats *s);
#endif
