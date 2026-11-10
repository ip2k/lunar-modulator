/* SPDX-License-Identifier: MIT
 * USB-MIDI 1.0 descriptors and packets for the FM-1 application; see
 * fm1_usb_midi.h. Every value below is from the USB 2.0 specification, the
 * MIDI 1.0 device class definition, or the stock FM-1's V15 descriptor
 * bytes [verified: bytes]; notes/2026-11-09-usb-midi.md has the comparison.
 */
#include "fm1_usb_midi.h"

#define LO(x) ((unsigned char)((x) & 0xffu))
#define HI(x) ((unsigned char)(((x) >> 8) & 0xffu))

static const unsigned char device[LUNAR_USB_MIDI_DEVICE_BYTES] = {
    18, 0x01,                     /* bLength, DEVICE */
    0x00, 0x02,                   /* bcdUSB 2.00, as stock */
    0x00, 0x00, 0x00,             /* class per interface */
    64,                           /* bMaxPacketSize0 */
    LO(LUNAR_USB_MIDI_VID), HI(LUNAR_USB_MIDI_VID),
    LO(LUNAR_USB_MIDI_PID), HI(LUNAR_USB_MIDI_PID),
    0x00, 0x01,                   /* bcdDevice 1.00, as stock */
    0,                            /* iManufacturer: none, as stock */
    2,                            /* iProduct "FM-1" */
    3,                            /* iSerialNumber */
    1                             /* bNumConfigurations */
};

/* bmAttributes 0x80 (bus powered), bMaxPower 0x32 (100 mA): stock's
 * template [verified: V15 bytes], not the SDK default's 0xC8. */
static const unsigned char config_header[LUNAR_USB_MIDI_CONFIG_HEADER_BYTES] = {
    9, 0x02, 0, 0, 0, 1, 0, 0x80, 0x32
};

/* Interface numbers sit at offsets 2 (AC), 17 (baInterfaceNr) and 20 (MS). */
#define AC_ITF 2u
#define AC_COLLECTION 17u
#define MS_ITF 20u
static const unsigned char function[LUNAR_USB_MIDI_FUNCTION_BYTES] = {
    /* Audio control interface, no endpoints. */
    9, 0x04, 0, 0, 0, 0x01, 0x01, 0x00, 0,
    /* Class-specific AC header: ADC 1.00, wTotalLength 9, one streaming
     * interface (patched to the MS interface's number). */
    9, 0x24, 0x01, 0x00, 0x01, 9, 0, 1, 1,
    /* MIDIStreaming interface, two endpoints. */
    9, 0x04, 1, 0, 2, 0x01, 0x03, 0x00, 0,
    /* MS header: MSC 1.00, wTotalLength 65 (header, jacks, endpoints). */
    7, 0x24, 0x01, 0x00, 0x01, 65, 0,
    /* Jacks in stock's order: embedded IN 1, external OUT 2 (from 1),
     * embedded OUT 8 (from external IN 7), external IN 7. */
    6, 0x24, 0x02, 0x01, 1, 0,
    9, 0x24, 0x03, 0x02, 2, 1, 1, 1, 0,
    9, 0x24, 0x03, 0x01, 8, 1, 7, 1, 0,
    6, 0x24, 0x02, 0x02, 7, 0,
    /* Bulk IN 0x84, 64 bytes, audio-class 9-byte form; carries jack 8. */
    9, 0x05, 0x80 | LUNAR_USB_MIDI_EP, 0x02, 64, 0, 0, 0, 0,
    5, 0x25, 0x01, 1, 8,
    /* Bulk OUT 0x04, 64 bytes; feeds jack 1. */
    9, 0x05, LUNAR_USB_MIDI_EP, 0x02, 64, 0, 0, 0, 0,
    5, 0x25, 0x01, 1, 1
};

const unsigned char *lunar_usb_midi_device_descriptor(void) { return device; }
const unsigned char *lunar_usb_midi_config_header(void) { return config_header; }

unsigned lunar_usb_midi_function(unsigned char *out, unsigned first)
{
    unsigned i;
    if (!out || first + LUNAR_USB_MIDI_INTERFACES > 8u) return 0;
    for (i = 0; i < LUNAR_USB_MIDI_FUNCTION_BYTES; ++i) out[i] = function[i];
    out[AC_ITF] = (unsigned char)first;
    out[AC_COLLECTION] = (unsigned char)(first + 1u);
    out[MS_ITF] = (unsigned char)(first + 1u);
    return LUNAR_USB_MIDI_FUNCTION_BYTES;
}

unsigned lunar_usb_midi_config(unsigned char *out)
{
    unsigned i;
    if (!out) return 0;
    for (i = 0; i < LUNAR_USB_MIDI_CONFIG_HEADER_BYTES; ++i) out[i] = config_header[i];
    lunar_usb_midi_function(out + LUNAR_USB_MIDI_CONFIG_HEADER_BYTES, 0);
    out[2] = LO(LUNAR_USB_MIDI_CONFIG_BYTES);
    out[3] = HI(LUNAR_USB_MIDI_CONFIG_BYTES);
    out[4] = LUNAR_USB_MIDI_INTERFACES;
    return LUNAR_USB_MIDI_CONFIG_BYTES;
}

static unsigned ascii_string(const char *s, unsigned char *out)
{
    unsigned n = 2;
    while (*s) {
        out[n++] = (unsigned char)*s++;
        out[n++] = 0;
    }
    out[0] = (unsigned char)n;
    out[1] = 0x03;
    return n;
}

unsigned lunar_usb_midi_string(unsigned index, const unsigned char *id, unsigned char *out)
{
    static const char hex[] = "0123456789ABCDEF";
    char serial[17];
    unsigned i;
    if (!out) return 0;
    switch (index) {
    case 0:
        out[0] = 4; out[1] = 0x03; out[2] = 0x09; out[3] = 0x04;   /* US English */
        return 4;
    case 2:
        return ascii_string("FM-1", out);
    case 3:
        for (i = 0; i < 8u; ++i) {
            unsigned byte = id ? id[i] : 0u;
            serial[2u * i] = hex[byte >> 4];
            serial[2u * i + 1u] = hex[byte & 15u];
        }
        serial[16] = 0;
        return ascii_string(serial, out);
    default:
        return ascii_string("", out);
    }
}

int lunar_usb_midi_encode(unsigned status, unsigned data1, unsigned data2,
                          unsigned char packet[4])
{
    unsigned kind = (status >> 4) & 15u;
    if (!packet || !(status & 0x80u) || status > 0xffu) return 0;
    if (kind >= 0x8u && kind <= 0xeu) {
        int two = kind == 0xcu || kind == 0xdu;
        packet[0] = (unsigned char)kind;           /* cable 0, CIN = status high nibble */
        packet[1] = (unsigned char)status;
        packet[2] = (unsigned char)(data1 & 0x7fu);
        packet[3] = two ? 0 : (unsigned char)(data2 & 0x7fu);
        return 1;
    }
    if (status >= 0xf8u) {                         /* real time: CIN 0xF, one byte */
        packet[0] = 0x0fu;
        packet[1] = (unsigned char)status;
        packet[2] = packet[3] = 0;
        return 1;
    }
    return 0;
}

void lunar_usb_midi_batch_reset(struct lunar_usb_midi_batch *b)
{
    if (b) b->length = 0;
}

int lunar_usb_midi_batch_add(struct lunar_usb_midi_batch *b, const unsigned char packet[4])
{
    unsigned i;
    if (!b || !packet) return 0;
    if (b->length + 4u > LUNAR_USB_MIDI_MAX_PACKET) {
        ++b->dropped;
        return 0;
    }
    for (i = 0; i < 4u; ++i) b->data[b->length + i] = packet[i];
    b->length += 4u;
    return 1;
}

unsigned lunar_usb_midi_split(const unsigned char *data, unsigned length,
                              void (*emit)(void *ctx, const unsigned char packet[4]), void *ctx)
{
    unsigned i, n = 0;
    if (!data || !emit) return 0;
    for (i = 0; i + 4u <= length; i += 4u) {
        if ((data[i] & 0x0fu) < 2u) continue;
        emit(ctx, data + i);
        ++n;
    }
    return n;
}
