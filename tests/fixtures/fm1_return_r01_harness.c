// Host fake CDC/BOT for the ACTUAL materialized return_r01_proto.c.
// Compile with -I materialized-source -I fake-headers, never with a target SDK.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

#include "src/return_r01_proto.c"

static uint64_t fake_now = 100;
static uint32_t fake_mount = 1;
static bool write_ok = true;
static bool jump_ok = true;
static bool fake_connected = true;
static bool rx_during_cdc_write;
static bool detach_on_write, detach_on_call;
static bool extra_during_write, extra_during_call;
static bool race_during_write, race_during_call;
static pthread_mutex_t race_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t race_cv = PTHREAD_COND_INITIALIZER;
static int race_state;
static int writes, jumps, terminals;
static char output[1024];
static size_t output_len;

uint64_t time_us_64(void) { return fake_now; }
bool tud_cdc_n_connected(uint8_t itf) { return itf == 1 && fake_connected; }
uint32_t tud_cdc_n_write_available(uint8_t itf) { return itf == 1 ? 1024 : 0; }
uint32_t tud_cdc_n_write(uint8_t itf, const void *data, uint32_t n) {
    if (itf != 1 || output_len + n >= sizeof(output)) abort();
    if (rx_during_cdc_write) {
        rx_during_cdc_write = false;
        fm1_proto_rx("rr01-upload\n", 12);
    }
    memcpy(output + output_len, data, n);
    output_len += n;
    output[output_len] = 0;
    return n;
}
void tud_cdc_n_write_flush(uint8_t itf) { if (itf != 1) abort(); }

uint32_t fm1_host_return_ready_generation(void) { return fake_mount; }
bool fm1_host_return_claim_upload(uint32_t generation) {
    if (!pthread_mutex_trylock(&state_lock.mu)) abort(); // claim and terminal check are atomic
    return generation == fake_mount;
}
bool fm1_host_return_upload_complete(uint32_t generation) { return generation == fake_mount; }
bool fm1_host_return_claim_call(uint32_t generation) {
    if (!pthread_mutex_trylock(&state_lock.mu)) abort();
    return generation == fake_mount;
}
bool fm1_host_return_call_complete(uint32_t generation) { return generation == fake_mount; }
void fm1_host_return_terminal(void) { terminals++; }
static void race_point(bool enabled) {
    if (!enabled) return;
    pthread_mutex_lock(&race_mu);
    race_state = 1;
    pthread_cond_broadcast(&race_cv);
    while (race_state != 2) pthread_cond_wait(&race_cv, &race_mu);
    pthread_mutex_unlock(&race_mu);
}
static void *race_extra(void *arg) {
    (void)arg;
    pthread_mutex_lock(&race_mu);
    while (race_state != 1) pthread_cond_wait(&race_cv, &race_mu);
    pthread_mutex_unlock(&race_mu);
    fm1_proto_rx("rr01-call\n", 10);
    pthread_mutex_lock(&race_mu);
    race_state = 2;
    pthread_cond_broadcast(&race_cv);
    pthread_mutex_unlock(&race_mu);
    return NULL;
}
bool jl_rom_mem_write(uint32_t addr, const uint8_t *data, uint16_t len) {
    if (addr != 0x01C02000u || len != 512 || data[0] != 0x80 || data[1] != 0) abort();
    writes++;
    if (detach_on_write) fake_mount = 0;
    if (extra_during_write) fm1_proto_rx("rr01-call\n", 10);
    race_point(race_during_write);
    return write_ok;
}
bool jl_rom_jump(uint32_t addr, uint16_t arg) {
    if (addr != 0x01C02000u || arg != 1) abort();
    jumps++;
    if (detach_on_call) fake_mount = 0;
    if (extra_during_call) fm1_proto_rx("rr01-call\n", 10);
    race_point(race_during_call);
    return jump_ok;
}

static void feed(const void *bytes, unsigned n) {
    fm1_proto_rx(bytes, n);
    fm1_proto_poll();
    fm1_proto_drain();
}
static void ready(void) { feed("rr01-ready\n", 11); }
static void upload(bool corrupt, bool extra) {
    uint8_t input[12 + 512 + 1];
    memcpy(input, "rr01-upload\n", 12);
    memset(input + 12, 0, 512);
    input[12] = 0x80;
    if (corrupt) input[13] = 1;
    if (extra) input[524] = 'x';
    feed(input, (unsigned)(524 + extra));
}
static void call(void) { feed("rr01-call\n", 10); }

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    fm1_proto_init();
    const char *kind = argv[1];
    if (!strcmp(kind, "success")) { ready(); upload(false, false); call(); call(); }
    else if (!strcmp(kind, "bad-payload")) { ready(); upload(true, false); call(); }
    else if (!strcmp(kind, "extra-payload")) { ready(); upload(false, true); call(); }
    else if (!strcmp(kind, "upload-fail")) { ready(); write_ok = false; upload(false, false); call(); }
    else if (!strcmp(kind, "upload-detach")) { ready(); detach_on_write = true; upload(false, false); call(); }
    else if (!strcmp(kind, "upload-extra-inflight")) { ready(); extra_during_write = true; upload(false, false); call(); }
    else if (!strcmp(kind, "concurrent-upload-extra")) {
        pthread_t worker; ready(); race_during_write = true;
        if (pthread_create(&worker, NULL, race_extra, NULL)) abort();
        upload(false, false); pthread_join(worker, NULL); call();
    }
    else if (!strcmp(kind, "call-fail")) { ready(); upload(false, false); jump_ok = false; call(); call(); }
    else if (!strcmp(kind, "call-detach")) { ready(); upload(false, false); detach_on_call = true; call(); call(); }
    else if (!strcmp(kind, "call-extra-inflight")) { ready(); upload(false, false); extra_during_call = true; call(); call(); }
    else if (!strcmp(kind, "concurrent-call-extra")) {
        pthread_t worker; ready(); upload(false, false); race_during_call = true;
        if (pthread_create(&worker, NULL, race_extra, NULL)) abort();
        call(); pthread_join(worker, NULL); call();
    }
    else if (!strcmp(kind, "no-mount")) {
        fake_mount = 0; ready(); fake_now += 10000000;
        fm1_proto_poll(); fm1_proto_drain(); upload(false, false);
    }
    else if (!strcmp(kind, "generic")) { feed("info\n", 5); ready(); }
    else if (!strcmp(kind, "pipelined-ready")) { feed("rr01-ready\nrr01-upload\n", 23); }
    else if (!strcmp(kind, "premature-next-before-ready-reply")) {
        fm1_proto_rx("rr01-ready\n", 11); fm1_proto_poll();
        fm1_proto_rx("rr01-upload\n", 12); fm1_proto_poll(); fm1_proto_drain();
    }
    else if (!strcmp(kind, "split-next-before-ready-reply")) {
        fm1_proto_rx("rr01-ready\n", 11); fm1_proto_poll();
        fm1_proto_rx("rr01-up", 7);
        if (phase != TERMINAL) abort();
        fm1_proto_poll(); fm1_proto_drain();
        fm1_proto_rx("load\n", 5); fm1_proto_poll(); fm1_proto_drain();
    }
    else if (!strcmp(kind, "pipelined-call")) {
        ready(); upload(false, false); feed("rr01-call\nrr01-call\n", 20);
    }
    else if (!strcmp(kind, "premature-call-before-upload-reply")) {
        ready();
        uint8_t input[524] = {0}; memcpy(input, "rr01-upload\n", 12); input[12] = 0x80;
        fm1_proto_rx((const char *)input, sizeof(input)); fm1_proto_poll();
        fm1_proto_rx("rr01-call\n", 10); fm1_proto_poll(); fm1_proto_drain();
    }
    else if (!strcmp(kind, "split-call-before-upload-reply")) {
        ready();
        uint8_t input[524] = {0}; memcpy(input, "rr01-upload\n", 12); input[12] = 0x80;
        fm1_proto_rx((const char *)input, sizeof(input)); fm1_proto_poll();
        fm1_proto_rx("rr01-ca", 7);
        if (phase != TERMINAL) abort();
        fm1_proto_poll(); fm1_proto_drain();
        fm1_proto_rx("ll\n", 3); fm1_proto_poll(); fm1_proto_drain();
    }
    else if (!strcmp(kind, "partial-timeout")) {
        ready(); feed("rr01-upload\n\x80\0", 14); fake_now += 6000000;
        fm1_proto_poll(); fm1_proto_drain(); call();
    }
    else if (!strcmp(kind, "cdc-disconnect")) {
        ready(); fake_connected = false; fm1_proto_drain(); fm1_proto_poll();
        fake_connected = true; upload(false, false); call();
    }
    else if (!strcmp(kind, "rx-during-cdc-write")) {
        rx_during_cdc_write = true;
        fm1_proto_rx("rr01-ready\n", 11); fm1_proto_poll(); fm1_proto_drain();
        if (tx_tail != tx_head) abort(); // terminal discard beats stale write completion
        fm1_proto_poll(); fm1_proto_drain(); upload(false, false); call();
    }
    else if (!strcmp(kind, "cr")) { feed("rr01-ready\r\n", 12); }
    else return 2;
    printf("%d %d %d %s", writes, jumps, phase == TERMINAL, output);
    return 0;
}
