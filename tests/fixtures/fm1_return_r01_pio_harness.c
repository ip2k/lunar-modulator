// Verbatim extracted strict host functions from patched src/pio_host.c.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t mounted_addr = 1;
static bool uboot_ready = true;
static bool probe_pending;
static int inquiry_tries;
static uint8_t data_buf[512];
static int bot_count;
static uint32_t inquiry_got = 36;
static bool bad_inquiry;
static bool detach_in_inquiry;

static void dlog(const char *fmt, ...) { (void)fmt; }
static bool fm1_proto_live(void) { return true; }
static bool bot_cmd(uint8_t daddr, const uint8_t *cdb, uint8_t cdb_len, bool in,
                    void *buf, uint16_t len, uint32_t *got) {
    (void)daddr;
    (void)cdb_len;
    bot_count++;
    if (cdb[0] == 0x12) {
        if (!in || len != 36) abort();
        memset(buf, 0, 36);
        memcpy((uint8_t *)buf + 8, "WL82    ", 8);
        memcpy((uint8_t *)buf + 16, "UBOOT1.00       ", 16);
        memcpy((uint8_t *)buf + 32, bad_inquiry ? "2.00" : "1.00", 4);
        if (got) *got = inquiry_got;
        if (detach_in_inquiry) mounted_addr = 0;
    }
    return true;
}

#include "actual_pio_functions.inc"

static void upload_cdb(uint8_t cdb[16]) {
    memset(cdb, 0xff, 16);
    const uint8_t p[9] = {0xFB, 0x06, 0x01, 0xC0, 0x20, 0, 0x02, 0, 0};
    memcpy(cdb, p, 9);
    cdb[9] = 0x60;
    cdb[10] = 0xC3;
}
static void call_cdb(uint8_t cdb[16]) {
    memset(cdb, 0xff, 16);
    const uint8_t p[8] = {0xFB, 0x08, 0x01, 0xC0, 0x20, 0, 0, 1};
    memcpy(cdb, p, 8);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    uint8_t cdb[16], buf[512] = {0};
    r01_phase = R01_PROBED;
    r01_mount_generation = 1;
    if (!strcmp(argv[1], "upload-call")) {
        if (fm1_host_return_ready_generation() != 1 || !fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
        if (!fm1_host_return_upload_complete(1) || !fm1_host_return_claim_call(1)) abort();
        call_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, true, buf, 16, NULL)) abort();
        if (fm1_host_bot(cdb, 16, true, buf, 16, NULL)) abort();
    } else if (!strcmp(argv[1], "bad-upload-cdb")) {
        if (!fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb); cdb[0] = 0xFD;
        if (fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
    } else if (!strcmp(argv[1], "bad-upload-crc")) {
        if (!fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb); cdb[9] ^= 1;
        if (fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
    } else if (!strcmp(argv[1], "bad-call-cdb")) {
        if (!fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
        if (!fm1_host_return_upload_complete(1) || !fm1_host_return_claim_call(1)) abort();
        call_cdb(cdb); cdb[7] = 2;
        if (fm1_host_bot(cdb, 16, true, buf, 16, NULL)) abort();
    } else if (!strcmp(argv[1], "upload-detach")) {
        if (!fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
        fm1_host_return_terminal();
        if (fm1_host_return_upload_complete(1)) abort();
    } else if (!strcmp(argv[1], "call-detach")) {
        if (!fm1_host_return_claim_upload(1)) abort();
        upload_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, false, buf, 512, NULL)) abort();
        if (!fm1_host_return_upload_complete(1) || !fm1_host_return_claim_call(1)) abort();
        call_cdb(cdb);
        if (!fm1_host_bot(cdb, 16, true, buf, 16, NULL)) abort();
        fm1_host_return_terminal();
        if (fm1_host_return_call_complete(1)) abort();
    } else if (!strcmp(argv[1], "wrong-generation")) {
        if (fm1_host_return_claim_upload(2) || fm1_host_return_claim_call(1)) abort();
    } else if (!strcmp(argv[1], "inquiry-ok")) {
        r01_phase = R01_COLD;
        if (!probe_inquiry(1)) abort();
    } else if (!strcmp(argv[1], "inquiry-bad")) {
        r01_phase = R01_COLD;
        bad_inquiry = true;
        if (probe_inquiry(1)) abort();
    } else if (!strcmp(argv[1], "inquiry-short")) {
        r01_phase = R01_COLD;
        inquiry_got = 35;
        if (probe_inquiry(1)) abort();
    } else if (!strcmp(argv[1], "inquiry-detach")) {
        r01_phase = R01_COLD;
        detach_in_inquiry = true;
        if (probe_inquiry(1)) abort();
    } else return 2;
    printf("%d %d %d\n", bot_count, r01_phase == R01_TERMINAL, uboot_ready);
    return 0;
}
