// Fake TinyUSB callbacks around verbatim extracted strict pio_host.c functions.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FM1T_RETURN_R01 1
#define FM1_VID 0x4c4a
#define FM1_PID 0x8057
#define FM1_V15_PID 0xc755
#define TUSB_DESC_CONFIGURATION 2
#define TUSB_DESC_INTERFACE 4
#define TUSB_DESC_ENDPOINT 5
#define TUSB_CLASS_MSC 8
#define TUSB_XFER_BULK 2
#define TUSB_DIR_OUT 0
#define TUSB_DIR_IN 1
#define TUSB_DIR_IN_MASK 0x80
#define XFER_TIMEOUT_MS 2000
#define FIRST_CBW_DELAY_MS 1500
#define INQUIRY_RETRY_MS 300
#define ATTACH_STATUS_MS 2000

typedef enum { XFER_RESULT_INVALID, XFER_RESULT_SUCCESS, XFER_RESULT_FAILED } xfer_result_t;
typedef struct xfer_s {
    uint8_t daddr, ep_addr;
    uint16_t buflen;
    void *buffer;
    void (*complete_cb)(struct xfer_s *);
    uint32_t actual_len;
    xfer_result_t result;
} tuh_xfer_t;
typedef struct {
    uint8_t bLength, bDescriptorType;
    uint16_t bcdUSB;
    uint8_t bDeviceClass, bDeviceSubClass, bDeviceProtocol, bMaxPacketSize0;
    uint16_t idVendor, idProduct, bcdDevice;
    uint8_t iManufacturer, iProduct, iSerialNumber, bNumConfigurations;
} tusb_desc_device_t;
typedef struct __attribute__((packed)) {
    uint8_t bLength, bDescriptorType;
    uint16_t wTotalLength;
    uint8_t bNumInterfaces, bConfigurationValue, iConfiguration, bmAttributes, bMaxPower;
} tusb_desc_configuration_t;
typedef struct __attribute__((packed)) {
    uint8_t bLength, bDescriptorType, bInterfaceNumber, bAlternateSetting;
    uint8_t bNumEndpoints, bInterfaceClass, bInterfaceSubClass, bInterfaceProtocol, iInterface;
} tusb_desc_interface_t;
typedef struct __attribute__((packed)) {
    uint8_t bLength, bDescriptorType, bEndpointAddress;
    union { uint8_t value; struct { uint8_t xfer:2, other:6; }; } bmAttributes;
    uint16_t wMaxPacketSize;
    uint8_t bInterval;
} tusb_desc_endpoint_t;
_Static_assert(sizeof(tusb_desc_configuration_t) == 9, "fake config wire size");
_Static_assert(sizeof(tusb_desc_interface_t) == 9, "fake interface wire size");
_Static_assert(sizeof(tusb_desc_endpoint_t) == 7, "fake endpoint wire size");

static uint8_t mounted_addr = 1;
static bool uboot_ready = true, probe_pending, mounted_is_v15, other_bulk_out_open;
static uint32_t r01_mount_count = 1;
static uint64_t mount_us, host_start_us, last_status_us, next_inquiry_us;
static int inquiry_tries;
static uint8_t ep_in, ep_out, msc_itf;
static tusb_desc_endpoint_t other_bulk_out;
static uint8_t cfg_buf[512];
static volatile xfer_result_t xfer_result;
static volatile uint32_t xfer_actual;
static int device_reads, config_reads, endpoint_opens, host_tasks, submissions, probe_calls;
static int terminal_at, terminal_on_poll, terminal_on_host_task, terminal_on_submit;
static uint16_t configured_total = 32;
static bool malformed_tail, malformed_crossing, malformed_short_interface;
static bool malformed_short_endpoint;
static bool malformed_header_len, malformed_header_kind, malformed_second_header;
static tuh_xfer_t *submitted;

static uint64_t time_us_64(void) { return 1; }
static void dlog(const char *fmt, ...) { (void)fmt; }
static void rgb(bool r, bool g, bool b) { (void)r; (void)g; (void)b; }
static uint16_t tu_edpt_packet_size(const tusb_desc_endpoint_t *ep) { return ep->wMaxPacketSize; }
static unsigned tu_edpt_dir(uint8_t addr) { return !!(addr & 0x80); }
void fm1_host_return_terminal(void);
static void fm1_proto_poll(void) {
    if (terminal_on_poll) fm1_host_return_terminal();
}
static bool probe_inquiry(uint8_t daddr) { (void)daddr; probe_calls++; return true; }
static void tuh_task(void) {
    host_tasks++;
    if (submitted) {
        submitted->actual_len = submitted->buflen;
        submitted->result = XFER_RESULT_SUCCESS;
        submitted->complete_cb(submitted);
        submitted = NULL;
    }
    if (terminal_on_host_task) fm1_host_return_terminal();
}
static bool tuh_edpt_xfer(tuh_xfer_t *x) {
    submissions++;
    submitted = x;
    if (terminal_on_submit) fm1_host_return_terminal();
    return true;
}
static void tuh_edpt_abort_xfer(uint8_t daddr, uint8_t ep) {
    (void)daddr; (void)ep;
}
static xfer_result_t tuh_descriptor_get_device_sync(uint8_t daddr,
                                                      tusb_desc_device_t *out, uint16_t size) {
    (void)daddr;
    if (size != sizeof(*out)) abort();
    device_reads++;
    *out = (tusb_desc_device_t){.idVendor = FM1_VID, .idProduct = FM1_PID};
    if (terminal_at == device_reads) fm1_host_return_terminal();
    return XFER_RESULT_SUCCESS;
}
static void fill_config(uint8_t *out, uint16_t n) {
    uint8_t bytes[512] = {0};
    bytes[0] = 9; bytes[1] = TUSB_DESC_CONFIGURATION;
    if (malformed_header_len) bytes[0] = 2;
    if (malformed_header_kind) bytes[1] = 0x99;
    bytes[2] = (uint8_t)configured_total;
    bytes[3] = (uint8_t)(configured_total >> 8);
    if (malformed_second_header && n != 9) bytes[2]--;
    bytes[5] = 1;
    if (malformed_tail) {
        bytes[9] = 250; bytes[10] = 0x99;
        bytes[259] = 251; bytes[260] = 0x99;
        bytes[510] = 2; bytes[511] = TUSB_DESC_ENDPOINT;
    } else if (malformed_crossing) {
        bytes[9] = 250; bytes[10] = 0x99;
    } else if (malformed_short_interface) {
        // Old walker read bInterfaceClass from an unrelated descriptor.
        bytes[9] = 2; bytes[10] = TUSB_DESC_INTERFACE;
        bytes[11] = 9; bytes[12] = 0x99; bytes[14] = TUSB_CLASS_MSC;
        bytes[20] = 7; bytes[21] = TUSB_DESC_ENDPOINT;
        bytes[22] = 1; bytes[23] = TUSB_XFER_BULK; bytes[24] = 64;
        bytes[27] = 7; bytes[28] = TUSB_DESC_ENDPOINT;
        bytes[29] = 0x81; bytes[30] = TUSB_XFER_BULK; bytes[31] = 64;
    } else if (malformed_short_endpoint) {
        bytes[9] = 9; bytes[10] = TUSB_DESC_INTERFACE;
        bytes[13] = 2; bytes[14] = TUSB_CLASS_MSC;
        bytes[18] = 2; bytes[19] = TUSB_DESC_ENDPOINT;
        bytes[20] = 7; bytes[21] = 6; // old cast sees addr 7 and bulk attr 6
        bytes[27] = 7; bytes[28] = TUSB_DESC_ENDPOINT;
        bytes[29] = 0x81; bytes[30] = TUSB_XFER_BULK; bytes[31] = 64;
    } else {
        bytes[9] = 9; bytes[10] = TUSB_DESC_INTERFACE;
        bytes[11] = 0; bytes[13] = 2; bytes[14] = TUSB_CLASS_MSC;
        bytes[18] = 7; bytes[19] = TUSB_DESC_ENDPOINT;
        bytes[20] = 1; bytes[21] = TUSB_XFER_BULK; bytes[22] = 64;
        bytes[25] = 7; bytes[26] = TUSB_DESC_ENDPOINT;
        bytes[27] = 0x81; bytes[28] = TUSB_XFER_BULK; bytes[29] = 64;
    }
    memcpy(out, bytes, n);
}
static xfer_result_t tuh_descriptor_get_configuration_sync(uint8_t daddr, uint8_t index,
                                                             void *out, uint16_t n) {
    (void)daddr; (void)index;
    config_reads++;
    if (n != 9 && n != configured_total) abort();
    fill_config(out, n);
    if (terminal_at == 1 + config_reads) fm1_host_return_terminal();
    return XFER_RESULT_SUCCESS;
}
static bool tuh_edpt_open(uint8_t daddr, const tusb_desc_endpoint_t *ep) {
    (void)daddr; (void)ep;
    endpoint_opens++;
    if (terminal_at == 3 + endpoint_opens) fm1_host_return_terminal();
    return true;
}

#include "actual_boundary_functions.inc"

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    r01_phase = R01_COLD;
    if (!strcmp(argv[1], "device-terminal")) terminal_at = 1;
    else if (!strcmp(argv[1], "header-terminal")) terminal_at = 2;
    else if (!strcmp(argv[1], "config-terminal")) terminal_at = 3;
    else if (!strcmp(argv[1], "out-open-terminal")) terminal_at = 4;
    else if (!strcmp(argv[1], "malformed-tail")) {
        configured_total = 512; malformed_tail = true;
    } else if (!strcmp(argv[1], "malformed-crossing")) malformed_crossing = true;
    else if (!strcmp(argv[1], "malformed-small-total")) configured_total = 8;
    else if (!strcmp(argv[1], "malformed-large-total")) configured_total = 513;
    else if (!strcmp(argv[1], "malformed-header-len")) malformed_header_len = true;
    else if (!strcmp(argv[1], "malformed-header-kind")) malformed_header_kind = true;
    else if (!strcmp(argv[1], "malformed-second-header")) malformed_second_header = true;
    else if (!strcmp(argv[1], "malformed-short-interface")) {
        configured_total = 34; malformed_short_interface = true;
    } else if (!strcmp(argv[1], "malformed-short-endpoint")) {
        configured_total = 34; malformed_short_endpoint = true;
    }
    else if (!strcmp(argv[1], "valid")) {}
    else if (!strcmp(argv[1], "endpoint-preterminal")) {
        fm1_host_return_terminal();
        uint8_t buf[8];
        if (edpt_sync(1, 1, buf, sizeof(buf), NULL) || submissions) abort();
        puts("endpoint-preterminal"); return 0;
    } else if (!strcmp(argv[1], "endpoint-submit-terminal")) {
        terminal_on_submit = 1;
        uint8_t buf[8];
        if (edpt_sync(1, 1, buf, sizeof(buf), NULL) || submissions != 1 || host_tasks) abort();
        puts("endpoint-submit-terminal"); return 0;
    } else if (!strcmp(argv[1], "endpoint-task-terminal")) {
        terminal_on_host_task = 1;
        uint8_t buf[8];
        if (edpt_sync(1, 1, buf, sizeof(buf), NULL) || submissions != 1 || host_tasks != 1) abort();
        puts("endpoint-task-terminal"); return 0;
    } else if (!strcmp(argv[1], "endpoint-valid")) {
        uint8_t buf[8]; uint32_t got = 0;
        if (!edpt_sync(1, 1, buf, sizeof(buf), &got) || got != 8) abort();
        puts("endpoint-valid"); return 0;
    } else if (!strcmp(argv[1], "task-preterminal")) {
        terminal_on_poll = 1;
        fm1_pio_host_task();
        if (host_tasks || probe_calls || device_reads) abort();
        puts("task-preterminal"); return 0;
    } else if (!strcmp(argv[1], "task-dispatch-terminal")) {
        terminal_on_host_task = 1;
        probe_pending = true;
        fm1_pio_host_task();
        if (host_tasks != 1 || probe_calls || device_reads) abort();
        puts("task-dispatch-terminal"); return 0;
    } else return 2;

    bool ok = probe_descriptors(1);
    if (!strcmp(argv[1], "valid")) {
        if (!ok || endpoint_opens != 2) abort();
    } else if (ok || endpoint_opens > (terminal_at == 4 ? 1 : 0)) {
        fprintf(stderr, "unexpected descriptor acceptance: ok=%d opens=%d\n",
                ok, endpoint_opens);
        abort();
    }
    printf("%d %d %d %d\n", device_reads, config_reads, endpoint_opens,
           r01_phase == R01_TERMINAL);
    return 0;
}
