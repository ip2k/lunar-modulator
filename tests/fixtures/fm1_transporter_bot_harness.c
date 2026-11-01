// Host-only fake TinyUSB endpoint for the actual patched upstream functions.
// actual_functions.inc is extracted verbatim from materialized pinned sources.
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define JL_IO_SIZE 512
#define JL_SECTOR_SIZE 4096
#define CMD_WRITE_MEMORY 0xFB06
#define MSC_CBW_SIGNATURE 0x43425355u
#define MSC_CSW_SIGNATURE 0x53425355u
#define TUSB_DIR_IN_MASK 0x80u

typedef struct __attribute__((packed)) {
    uint32_t signature, tag, total_bytes;
    uint8_t dir, lun, cmd_len, command[16];
} msc_cbw_t;
typedef struct __attribute__((packed)) {
    uint32_t signature, tag, data_residue;
    uint8_t status;
} msc_csw_t;

static uint8_t ep_in = 0x81, ep_out = 0x02;
static msc_cbw_t cbw;
static msc_csw_t csw;
static uint32_t cbw_tag = 1;
static uint8_t resp[16];
static uint8_t block[JL_IO_SIZE];
static uint8_t sector[JL_SECTOR_SIZE];
static uint64_t last_cmd_us;
static bool loader_running;
static char last_line[128];
static uint16_t seen_commands[4];
static int command_count, transfer_count;
static bool direct_bot;
static uint32_t direct_got;
static uint16_t direct_echo;
static struct { bool success; uint32_t actual; } steps[3];
static uint32_t csw_signature, csw_tag_offset, csw_residue;
static uint8_t csw_status;

static uint64_t time_us_64(void) { return 1; }
static void dlog(const char *fmt, ...) { (void)fmt; }
static bool jl_loader_running(void) { return false; }
static void tx_line(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_line, sizeof(last_line), fmt, ap);
    va_end(ap);
}
static bool edpt_sync(uint8_t daddr, uint8_t ep, void *buf, uint16_t len, uint32_t *actual) {
    (void)daddr;
    if (transfer_count >= 3) abort();
    int stage = transfer_count++;
    if (stage == 0) {
        if (ep != ep_out || len != 31) abort();
        msc_cbw_t *sent = buf;
        seen_commands[command_count++] = (uint16_t)(sent->command[0] << 8 | sent->command[1]);
    } else if (stage == 1) {
        if (ep != ep_out || len != 512) abort();
    } else {
        if (ep != ep_in || len != 13) abort();
        msc_csw_t *reply = buf;
        reply->signature = csw_signature;
        reply->tag = cbw.tag + csw_tag_offset;
        reply->data_residue = csw_residue;
        reply->status = csw_status;
    }
    if (actual) *actual = steps[stage].actual;
    return steps[stage].success;
}

static bool fm1_host_bot(const uint8_t *cdb, uint8_t cdb_len, bool in,
                         void *buf, uint16_t len, uint32_t *got);
#include "actual_functions.inc"
static bool fm1_host_bot(const uint8_t *cdb, uint8_t cdb_len, bool in,
                         void *buf, uint16_t len, uint32_t *got) {
    if (direct_bot) {
        ((uint8_t *)buf)[0] = (uint8_t)(direct_echo >> 8);
        ((uint8_t *)buf)[1] = (uint8_t)direct_echo;
        *got = direct_got;
        return true;
    }
    return bot_cmd(1, cdb, cdb_len, in, buf, len, got);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    for (int i = 0; i < 3; ++i) {
        steps[i].success = true;
        steps[i].actual = (uint32_t[]){31, 512, 13}[i];
    }
    csw_signature = MSC_CSW_SIGNATURE;
    if (!strcmp(argv[1], "cbw30")) steps[0].actual = 30;
    else if (!strcmp(argv[1], "data511")) steps[1].actual = 511;
    else if (!strcmp(argv[1], "csw12")) steps[2].actual = 12;
    else if (!strcmp(argv[1], "residue")) csw_residue = 1;
    else if (!strcmp(argv[1], "tag")) csw_tag_offset = 1;
    else if (!strcmp(argv[1], "signature")) csw_signature = 0;
    else if (!strcmp(argv[1], "status")) csw_status = 1;
    else if (!strcmp(argv[1], "timeout")) steps[1].success = false;
    else if (!strcmp(argv[1], "disconnect")) steps[0].success = false;
    else if (!strcmp(argv[1], "csw_timeout")) steps[2].success = false;
    else if (!strcmp(argv[1], "data513")) steps[1].actual = 513;
    else if (!strcmp(argv[1], "caller_cbw")) steps[0].actual = 30;
    else if (!strcmp(argv[1], "caller_data")) steps[1].actual = 511;
    else if (!strcmp(argv[1], "caller_csw")) csw_status = 1;
    else if (!strcmp(argv[1], "caller_ok")) {}
    else if (!strcmp(argv[1], "got15")) { direct_bot = true; direct_got = 15; direct_echo = 0xFB08; }
    else if (!strcmp(argv[1], "got16")) { direct_bot = true; direct_got = 16; direct_echo = 0xFB08; }
    else if (!strcmp(argv[1], "echo")) { direct_bot = true; direct_got = 16; direct_echo = 0xFB06; }
    else if (strcmp(argv[1], "ok")) return 2;

    if (!strncmp(argv[1], "caller_", 7)) {
        uint8_t cdb[16] = {0xFB, 0x06};
        uint32_t got = 0xDEADBEEFu;
        bool ok = bot_cmd(1, cdb, 16, false, block, 512, &got);
        printf("%d %08X %d\n", ok, (unsigned)got, transfer_count);
    } else if (direct_bot) {
        uint8_t args[6] = {0};
        bool ok = cmd_exec(0xFB08, args, sizeof(args));
        printf("%d %d %d\n", ok, command_count, transfer_count);
    } else {
        memset(sector, 0, 512);
        do_memw(0x1c02000u, 512, crc32_update(0, sector, 512));
        printf("%s %d %d %04X\n", last_line, command_count, transfer_count,
               command_count ? seen_commands[0] : 0);
    }
    return 0;
}
