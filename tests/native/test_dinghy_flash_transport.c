#include <assert.h>
#include <setjmp.h>
#include <stddef.h>
#include <stdint.h>

static volatile uint32_t reg_sfc, reg_spi, reg_buf, reg_iomap, reg_out, reg_dir, reg_cache, reg_timer;
static unsigned transfer_index, fail_transfer = (unsigned)-1;
static uint8_t replies[16];
static unsigned reply_count, reply_index;
static uint8_t tx_bytes[300];
static unsigned tx_count;
static int nor_wel, nor_wip, destructive_pending, ready_observed;
static unsigned status_polls_to_clear, sfc_restores;
static int hold_wip, fail_status_forever;
static unsigned status_polls, failstop_limit;
static jmp_buf failstop_env;
static int failstop_armed;

static volatile uint32_t *fl_test_reg(uint32_t address)
{
    switch (address) {
    case 0x40200u: return &reg_sfc;
    case 0x11C00u: return &reg_spi;
    case 0x11C08u: return &reg_buf;
    case 0x5101Cu: return &reg_iomap;
    case 0x500C0u: return &reg_out;
    case 0x500C8u: return &reg_dir;
    case 0x1EEE008u: return &reg_cache;
    case 0x10804u: return &reg_timer;
    default: assert(!"unexpected register"); return &reg_sfc;
    }
}
static void test_cs_level(int high)
{
    reg_dir &= ~1u;
    if (!high) {
        reg_out &= ~1u;
        tx_count = 0;
        return;
    }
    reg_out |= 1u;
    if (!tx_count) return;
    if (tx_bytes[0] == 0x06) {
        nor_wel = 1;
    } else if (tx_bytes[0] == 0x20 || tx_bytes[0] == 0x02) {
        /* Model the conservative case: a timed-out byte may have reached NOR,
         * and raising CS can commit even an incomplete address/data sequence. */
        destructive_pending = 1;
        nor_wip = 1;
        nor_wel = 0;
        status_polls_to_clear = hold_wip ? (unsigned)-1 : 1u;
    }
    if (destructive_pending && tx_bytes[0] == 0x05 && failstop_armed &&
        status_polls >= failstop_limit && (hold_wip || fail_status_forever))
        longjmp(failstop_env, 1);
}
static int test_spi_wait(void)
{
    unsigned current = transfer_index++;
    int receive = (reg_spi & 0x1000u) != 0;
    if (!receive && tx_count < sizeof tx_bytes) tx_bytes[tx_count++] = (uint8_t)reg_buf;
    if (receive && tx_count && tx_bytes[0] == 0x05) {
        ++status_polls;
        if (fail_status_forever && destructive_pending) {
            return -1;
        }
    }
    if (current == fail_transfer) return -1;
    if (receive) {
        if (tx_count && tx_bytes[0] == 0x05) {
            uint8_t status = (nor_wel ? 2u : 0u) | (nor_wip ? 1u : 0u);
            reg_buf = status;
            if (destructive_pending && !nor_wip) ready_observed = 1;
            if (nor_wip && status_polls_to_clear != (unsigned)-1) {
                if (status_polls_to_clear) --status_polls_to_clear;
                else nor_wip = 0;
            }
        } else {
            assert(reply_index < reply_count);
            reg_buf = replies[reply_index++];
        }
    }
    return 0;
}
static void test_sfc_restore(uint32_t value)
{
    ++sfc_restores;
    if (destructive_pending) assert(ready_observed && !nor_wip);
    reg_sfc = value;
}
#define REG32(a) (*fl_test_reg(a))
#define FL_CSYNC() ((void)0)
#define FL_FLUSHINV(a) ((void)(a))
#define FL_SPI_WAIT() test_spi_wait()
#define FL_CS_LEVEL(high) test_cs_level(high)
#define FL_SFC_RESTORE(value) test_sfc_restore(value)
#define FL_IRQ_DISABLE() ((void)0)
#define FL_IRQ_RESTORE_ENABLED() ((void)0)
#include "../../firmware/third_party/dinghy/hal/fm1_flash.h"

static void reset_mock(uint32_t iomap)
{
    reg_sfc = 0;
    reg_spi = 0x1255u;
    reg_buf = 0;
    reg_iomap = iomap;
    reg_out = 1u;
    reg_dir = 1;
    reg_cache = 0x4000u;
    reg_timer = 24u;
    transfer_index = 0;
    fail_transfer = (unsigned)-1;
    reply_count = reply_index = 0;
    tx_count = 0;
    nor_wel = nor_wip = destructive_pending = ready_observed = 0;
    status_polls_to_clear = status_polls = sfc_restores = 0;
    hold_wip = fail_status_forever = failstop_armed = 0;
    failstop_limit = 0;
}
static void replies_set(const uint8_t *values, unsigned count)
{
    unsigned i;
    reply_count = count;
    reply_index = 0;
    for (i = 0; i < count; ++i) replies[i] = values[i];
}
static void assert_restored(uint32_t original_iomap, uint32_t original_spi)
{
    assert((reg_out & 1u) != 0u);
    assert(reg_sfc == 0u);
    assert(reg_spi == original_spi);
    assert((reg_iomap & 0x20u) == (original_iomap & 0x20u));
    assert(!destructive_pending || (ready_observed && !nor_wip));
}
static void test_checked_jedec_timeout(void)
{
    static const uint8_t id[] = {0x85, 0x60, 0x14};
    unsigned failure;
    for (failure = 0; failure < 4; ++failure) {
        const uint32_t iomap = (failure & 1u) ? 0x20u : 0xA0u;
        uint32_t id_out = 0x12345678u;
        reset_mock(iomap);
        replies_set(id, 3);
        fail_transfer = failure;
        assert(fl_jedec_checked_ram(&id_out) == -5);
        assert(id_out == 0x12345678u);
        assert_restored(iomap, 0x1255u);
    }
    reset_mock(0x20u);
    replies_set(id, 3);
    {
        uint32_t id_out = 0;
        assert(fl_jedec_checked_ram(&id_out) == 0);
        assert(id_out == 0x856014u);
    }
    assert_restored(0x20u, 0x1255u);
}
static void test_status_timeout_is_not_value(void)
{
    static const uint8_t status[] = {0x55, 0xAA};
    uint32_t result = 0xdeadbeefu;
    reset_mock(0);
    replies_set(status, 2);
    fail_transfer = 3;
    assert(fl_status_checked_ram(&result) == -5);
    assert(result == 0xdeadbeefu);
    assert_restored(0, 0x1255u);
}
static void test_read_transfer_errors_restore_state(void)
{
    static const uint8_t bytes[] = {0x31, 0x32};
    unsigned failure;
    for (failure = 0; failure < 7; ++failure) {
        uint8_t dst[2] = {0, 0};
        reset_mock(0x20u);
        replies_set(bytes, 2);
        fail_transfer = failure;
        assert(fl_read_ram(0x97000u, dst, 2) == -5);
        assert_restored(0x20u, 0x1255u);
    }
    {
        uint8_t dst[2] = {0, 0};
        reset_mock(0);
        replies_set(bytes, 2);
        assert(fl_read_ram(0x97000u, dst, 2) == 0);
        assert(dst[0] == 0x31 && dst[1] == 0x32);
        assert_restored(0, 0x1255u);
    }
}
static void test_erase_transport_errors_wait_for_committed_command(void)
{
    static const uint8_t wel[] = {0x02};
    unsigned failure;
    for (failure = 0; failure < 7; ++failure) {
        uint32_t took = 0;
        reset_mock((failure & 1u) ? 0x20u : 0);
        replies_set(wel, 1);
        fail_transfer = failure;
        assert(fl_erase4k_ram(0x97000u, &took) == -5);
        assert_restored((failure & 1u) ? 0x20u : 0, 0x1255u);
        if (failure >= 3) assert(ready_observed && status_polls >= 2);
        else assert(!destructive_pending);
    }
    reset_mock(0);
    replies_set(wel, 1);
    {
        uint32_t took = 0;
        assert(fl_erase4k_ram(0x97000u, &took) == 0);
        assert(ready_observed && !nor_wip);
        assert_restored(0, 0x1255u);
    }
}
static void test_program_transport_errors_wait_for_committed_command(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    unsigned failure;
    for (failure = 0; failure < 8; ++failure) {
        uint32_t took = 0;
        reset_mock(0x20u);
        replies_set(wel, 1);
        fail_transfer = failure;
        assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == -5);
        assert_restored(0x20u, 0x1255u);
        if (failure >= 3) assert(ready_observed && status_polls >= 2);
        else assert(!destructive_pending);
    }
    reset_mock(0x20u);
    replies_set(wel, 1);
    {
        uint32_t took = 0;
        assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == 0);
        assert(ready_observed && !nor_wip);
        assert_restored(0x20u, 0x1255u);
    }
}
static void test_status_poll_error_retries_until_verified_ready(void)
{
    static const uint8_t wel[] = {0x02};
    unsigned failure;
    for (failure = 7; failure < 9; ++failure) {
        uint32_t took = 0;
        reset_mock(0);
        replies_set(wel, 1);
        fail_transfer = failure;
        assert(fl_erase4k_ram(0x97000u, &took) == -5);
        assert_restored(0, 0x1255u);
        assert(ready_observed && !nor_wip && status_polls >= 3);
    }
}
static void test_unprovable_ready_never_restores_xip(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    reset_mock(0x20u);
    replies_set(wel, 1);
    hold_wip = 1;
    failstop_limit = 8;
    failstop_armed = 1;
    if (setjmp(failstop_env) == 0) {
        uint32_t took = 0;
        (void)fl_prog_ram(0x97000u, payload, sizeof payload, &took);
        assert(!"must remain in RAM until NOR-ready is proven");
    }
    failstop_armed = 0;
    assert(destructive_pending && nor_wip && !ready_observed);
    assert(reg_sfc == 0u && sfc_restores == 0u);
    assert((reg_iomap & 0x20u) == 0u);
    assert((reg_out & 1u) != 0u);
}
static void test_unreadable_status_never_restores_xip(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    reset_mock(0x20u);
    replies_set(wel, 1);
    fail_status_forever = 1;
    failstop_limit = 8;
    failstop_armed = 1;
    if (setjmp(failstop_env) == 0) {
        uint32_t took = 0;
        (void)fl_prog_ram(0x97000u, payload, sizeof payload, &took);
        assert(!"must remain in RAM while status is unreadable");
    }
    failstop_armed = 0;
    assert(destructive_pending && !ready_observed);
    assert(reg_sfc == 0u && sfc_restores == 0u);
    assert((reg_iomap & 0x20u) == 0u);
    assert((reg_out & 1u) != 0u);
}
static void test_exit_preserves_pin_owner_bit(void)
{
    unsigned bit;
    for (bit = 0; bit < 2; ++bit) {
        fl_saved_t saved;
        uint32_t initial = bit ? 0xA0u : 0x80u;
        reset_mock(initial);
        assert(fl_enter(&saved) == 0);
        assert((reg_iomap & 0x20u) == 0);
        fl_exit(&saved);
        assert((reg_iomap & 0x20u) == (initial & 0x20u));
        assert(reg_sfc == 0u);
        assert(reg_spi == 0x1255u);
        assert((reg_iomap & 0x20u) == (initial & 0x20u));
    }
}
int main(void)
{
    test_checked_jedec_timeout();
    test_status_timeout_is_not_value();
    test_read_transfer_errors_restore_state();
    test_erase_transport_errors_wait_for_committed_command();
    test_program_transport_errors_wait_for_committed_command();
    test_status_poll_error_retries_until_verified_ready();
    test_unprovable_ready_never_restores_xip();
    test_unreadable_status_never_restores_xip();
    test_exit_preserves_pin_owner_bit();
    return 0;
}
