/* SPDX-License-Identifier: MIT
 * The FM-1 application's USB-MIDI device on the AC79 SDK's low-level USB
 * driver (cpu.a, pinned V1.2.13 libraries, Apache-2.0). Clean room: the
 * SDK's device classes (apps/common/usb/device) are not compiled, because
 * they include the GPL-2.0 uac_audio.h; usb_stack.h is not included,
 * because it pulls the Linux-derived usb/ch9.h. Only JieLi's own asm/usb.h
 * is included, and the few stack entry points used are declared here from
 * their LLVM IR in cpu.a [verified: IR, notes/2026-11-09-usb-midi.md].
 *
 *   control interrupt (IRQ 9, CPU0, priority 1, below ALNK0's 3)
 *       bus reset -> the library's reset dispatch -> endpoint 4 armed
 *       EP0      -> the library's control state machine, which asks the
 *                   overrides below for descriptors
 *   panel task (every pass, never waits)
 *       OUT 0x04 -> read when a packet is ready -> event packets -> emit
 *       IN 0x84  <- the batch, when the endpoint is free
 *
 * Endpoint 4 is not read in the interrupt: an unread OUT packet keeps the
 * endpoint NAKing, so the host waits instead of data being dropped, and the
 * only endpoint-4 traffic outside the task is the reset re-arm.
 *
 * NOTHING HERE HAS RUN ON AN FM-1 OR THE DEV KIT.
 */
#include "app_config.h"
#include "system/includes.h"
#include "asm/usb.h"
#include <string.h>

#include "fm1_usb_midi.h"

#ifndef LUNAR_FM1_USB_MIDI
#error fm1_usb_sdk.c is built only with LUNAR_FM1_USB_MIDI
#endif

/* ---- the library's device stack, declared from cpu.a's IR -------------- */
/* struct usb_device_t is opaque here; struct usb_ctrlrequest is the
 * standard 8-byte SETUP packet (USB 2.0 table 9-2), packed as the IR loads
 * it (align 1). */
struct usb_device_t;
struct lunar_usb_setup {
    u8 bRequestType, bRequest;
    u16 wValue, wIndex, wLength;
} __attribute__((packed));

typedef u32 (*lunar_itf_handler)(struct usb_device_t *, struct lunar_usb_setup *);
typedef void (*lunar_itf_reset)(struct usb_device_t *, u32 itf);
typedef u32 (*lunar_desc_config)(const usb_dev id, u8 *ptr, u32 *cur_itf_num);

extern struct usb_device_t *usb_id2device(const usb_dev id);
extern void usb_setup_init(const usb_dev id, void *setup, u8 *setup_buffer);
extern void usb_add_desc_config(const usb_dev id, u32 index, const lunar_desc_config desc);
extern u32 usb_set_interface_hander(const usb_dev id, u32 itf, lunar_itf_handler handler);
extern u32 usb_set_reset_hander(const usb_dev id, u32 itf, lunar_itf_reset handler);
extern void usb_set_setup_hook(struct usb_device_t *dev, void *hook);
extern void usb_set_setup_phase(struct usb_device_t *dev, u8 phase);
extern u8 *usb_set_data_payload(struct usb_device_t *dev, struct lunar_usb_setup *req,
                                const void *data, u32 len);
extern void usb_control_transfer(struct usb_device_t *dev);
extern void usb_reset_interface(struct usb_device_t *dev);
/* Strong on purpose: a weak reference does not pull vm_sfc.c.o's definition
 * through LTO, and every unit's serial would read sixteen zeros. The UUID is
 * read into flash_info by read_flash_id at flash init [verified: IR]. */
extern u8 *get_norflash_uuid(void);

/* [verified: IR] sizeof(struct usb_setup_t) = 100 (usb_device_t 28, the
 * request 8, two 8-entry handler tables 64); usb_var_init clears 104. */
#define SETUP_T_BYTES 100u
#define EP_ADDR_T_BYTES 104u
/* The library writes the setup buffer only from the descriptor callbacks
 * (at most the 101-byte configuration) and 1-2 byte status replies
 * [verified: IR]; 768 is only set_descriptor's max_len. */
#define SETUP_BUFFER_BYTES 128u
#define IRQ_USB_CONTROL 9u          /* IRQ_USB_CTRL_IDX, asm/hwi.h */
#define USB_PRIORITY 1u             /* 0..7, larger is higher (hwi.h); ALNK0 is 3 */
#define INTRUSB_RESET 0x04u         /* usb_phy.h INTRUSB_RESET_BABBLE */
#define EP0_SETUP 0u                /* usb_phy.h USB_EP0_STAGE_SETUP */
#define EP0_STALL 3u                /* usb_phy.h USB_EP0_SET_STALL */
#define XFER_BULK 2u
#define TXCSR_PKT_READY 0x01u
#define RXCSR_PKT_READY 0x01u
#define REQ_GET_STATUS 0x00u
#define REQ_SET_CONFIGURATION 0x09u
#define REQ_GET_INTERFACE 0x0au
#define REQ_SET_INTERFACE 0x0bu

static u32 setup_store[SETUP_T_BYTES / 4u];
static u32 ep_addr_store[EP_ADDR_T_BYTES / 4u];
static u8 setup_buffer[SETUP_BUFFER_BYTES] __attribute__((aligned(4)));
/* DMA: EP0 64 + 4 as the SDK's; bulk OUT is double-buffered by the
 * library (usb_g_ep_config type 2 sets the dual address, and
 * usb_get_dma_raddr alternates ptr and ptr + 4 + size [verified: IR]). */
static u8 ep0_dma[64u + 4u] __attribute__((aligned(4)));
static u8 rx_dma[2u * (LUNAR_USB_MIDI_MAX_PACKET + 4u)] __attribute__((aligned(4)));
static u8 tx_dma[LUNAR_USB_MIDI_MAX_PACKET] __attribute__((aligned(4)));
static u8 serial[LUNAR_USB_MIDI_SERIAL_BYTES];
static struct lunar_usb_midi_batch batch;
static struct usb_device_t *device;
static volatile u32 configured;
static struct lunar_usb_midi_stats stats;

/* ---- descriptor overrides (weak in cpu.a's descriptor.c.o) ------------- */
void get_device_descriptor(u8 *ptr, const usb_dev id)
{
    (void)id;
    memcpy(ptr, lunar_usb_midi_device_descriptor(), LUNAR_USB_MIDI_DEVICE_BYTES);
}

const u8 *usb_get_config_desc(void) { return lunar_usb_midi_config_header(); }
void get_language_str(u8 *ptr) { lunar_usb_midi_string(0, 0, ptr); }
void get_manufacture_str(u8 *ptr) { lunar_usb_midi_string(1, 0, ptr); }   /* empty */
void get_product_str(u8 *ptr) { lunar_usb_midi_string(2, 0, ptr); }
void get_iserialnumber_str(u8 *ptr) { memcpy(ptr, serial, sizeof serial); }
void get_string_ee(u8 *ptr) { lunar_usb_midi_string(0xee, 0, ptr); }       /* empty */

/* ---- endpoints ------------------------------------------------------------ */
static void endpoints_arm(void)
{
    usb_g_ep_config(0, LUNAR_USB_MIDI_EP | USB_DIR_IN, XFER_BULK, 0, tx_dma, LUNAR_USB_MIDI_MAX_PACKET);
    usb_g_ep_config(0, LUNAR_USB_MIDI_EP, XFER_BULK, 0, rx_dma, LUNAR_USB_MIDI_MAX_PACKET);
    usb_enable_ep(0, LUNAR_USB_MIDI_EP);
}

/* ---- control requests ----------------------------------------------------- */
/* Standard requests to either interface; there are no class requests. */
static u32 interface_request(struct usb_device_t *dev, struct lunar_usb_setup *req)
{
    static const u8 zero[2] = {0, 0};
    u32 to_host = req->bRequestType & 0x80u;
    if ((req->bRequestType & 0x60u) == 0) {
        if (req->bRequest == REQ_GET_STATUS && to_host) {
            usb_set_data_payload(dev, req, zero, req->wLength < 2u ? req->wLength : 2u);
            return 0;
        }
        if (req->bRequest == REQ_GET_INTERFACE && to_host) {
            usb_set_data_payload(dev, req, zero, req->wLength < 1u ? req->wLength : 1u);
            return 0;
        }
        if (req->bRequest == REQ_SET_INTERFACE && !to_host && req->wValue == 0) {
            usb_set_setup_phase(dev, EP0_SETUP);
            return 0;
        }
    }
    usb_set_setup_phase(dev, EP0_STALL);
    return 0;
}

static void bus_reset(struct usb_device_t *dev, u32 itf)
{
    (void)dev; (void)itf;
    configured = 0;
    ++stats.resets;
    endpoints_arm();
}

/* Sees every SETUP before the library; 0 lets the library handle it. Only
 * SET_CONFIGURATION is watched: 0 disables endpoints 1-4 in the library,
 * so 1 re-arms endpoint 4 and opens the IN path. */
static u32 setup_hook(struct usb_device_t *dev, struct lunar_usb_setup *req)
{
    (void)dev;
    if (req->bRequestType == 0x00u && req->bRequest == REQ_SET_CONFIGURATION) {
        if (req->wValue == 1u) {
            endpoints_arm();
            configured = 1;
            ++stats.configurations;
        } else {
            configured = 0;
        }
    }
    return 0;
}

/* set_descriptor's callback: our two interfaces after any before them. The
 * handlers are (re)registered here, as the SDK's classes do. */
static u32 function_config(const usb_dev id, u8 *ptr, u32 *cur_itf_num)
{
    u32 first = *cur_itf_num, n = lunar_usb_midi_function(ptr, first);
    if (!n) return 0;
    usb_set_interface_hander(id, first, interface_request);
    usb_set_interface_hander(id, first + 1u, interface_request);
    usb_set_reset_hander(id, first, bus_reset);
    *cur_itf_num = first + LUNAR_USB_MIDI_INTERFACES;
    return n;
}

static ___interrupt void usb_control_irq(void)
{
    u32 usb, tx, rx, usbe, txe, rxe;
    __asm__ volatile("ssync");
    usb_read_intr(0, &usb, &tx, &rx);
    usb_read_intre(0, &usbe, &txe, &rxe);
    if (usb & usbe & INTRUSB_RESET) usb_reset_interface(device);
    if (tx & txe & 1u) usb_control_transfer(device);
    __asm__ volatile("csync");
}

int lunar_usb_midi_start(void)
{
    const u8 *uuid = get_norflash_uuid();
    u32 ep;
    if (stats.started) return 1;
    lunar_usb_midi_string(3, uuid, serial);
    lunar_usb_midi_batch_reset(&batch);
    configured = 0;

    memset(setup_store, 0, sizeof setup_store);
    usb_add_desc_config(0, 8, 0);                     /* clears every slot */
    usb_add_desc_config(0, 0, function_config);
    usb_var_init(0, ep_addr_store);
    usb_setup_init(0, setup_store, setup_buffer);     /* builds the descriptor once */
    device = usb_id2device(0);
    if (!device) return 0;
    usb_set_setup_hook(device, setup_hook);

    /* The SDK's usb_device_init for full speed, its usb_slave_init inlined
     * (usb_phy.c.o is not linked) [verified: IR]. */
    usb_g_sie_init(0);                                /* PHY, D+ pull-up: attach */
    usb_write_power(0, 0x60);
    usb_write_intr_usbe(0, 0);
    usb_clr_intr_txe(0, -1);
    usb_clr_intr_rxe(0, -1);
    usb_sie_enable(0);
    for (ep = 0; ep < 5u; ++ep) usb_set_dma_raddr(0, ep, ep0_dma);
    usb_write_intr_usbe(0, INTRUSB_RESET);
    usb_clr_intr_txe(0, -1);
    usb_clr_intr_rxe(0, -1);
    usb_set_intr_txe(0, 0);
    usb_set_intr_rxe(0, 0);
    request_irq(IRQ_USB_CONTROL, USB_PRIORITY, usb_control_irq, 0);
    stats.started = 1;
    return 1;
}

unsigned lunar_usb_midi_poll(void (*emit)(void *ctx, const unsigned char packet[4]), void *ctx)
{
    unsigned got = 0;
    if (!stats.started || !configured) return 0;
    if (usb_read_rxcsr(0, LUNAR_USB_MIDI_EP) & RXCSR_PKT_READY) {
        u8 data[LUNAR_USB_MIDI_MAX_PACKET];
        u32 n = usb_g_ep_read(0, LUNAR_USB_MIDI_EP, data, sizeof data, 0);
        got = lunar_usb_midi_split(data, n > sizeof data ? sizeof data : n, emit, ctx);
        stats.received += got;
    }
    if (batch.length) {
        /* usb_g_ep_write spins while TxPktRdy is set; never call it then. */
        if (usb_read_txcsr(0, LUNAR_USB_MIDI_EP) & TXCSR_PKT_READY) {
            ++stats.busy;
        } else {
            usb_g_ep_write(0, LUNAR_USB_MIDI_EP, batch.data, batch.length);
            stats.sent += batch.length / 4u;
            lunar_usb_midi_batch_reset(&batch);
        }
    }
    return got;
}

int lunar_usb_midi_send(const unsigned char packet[4])
{
    if (!stats.started || !configured) return 0;
    return lunar_usb_midi_batch_add(&batch, packet);
}

void lunar_usb_midi_stats(struct lunar_usb_midi_stats *s)
{
    if (!s) return;
    *s = stats;
    s->online = configured;
    s->dropped = batch.dropped;
}
