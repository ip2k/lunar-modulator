#include <assert.h>
#include <setjmp.h>
#include <stddef.h>
#include <stdint.h>

static volatile uint32_t reg_sfc, reg_spi, reg_buf, reg_iomap, reg_out, reg_dir, reg_cache, reg_timer, reg_icfg;
static unsigned transfer_index, fail_transfer = (unsigned)-1;
static uint8_t replies[16];
static unsigned reply_count, reply_index;
static uint8_t tx_bytes[300];
static unsigned tx_count;
static uint8_t programmed_payload[300];
static unsigned programmed_count;
static const uint8_t *programmed_sources[4];
static uint32_t programmed_sizes[4];
static unsigned program_calls;
static int nor_wel, nor_wip, destructive_pending, ready_observed;
static unsigned status_polls_to_clear, sfc_restores;
static int hold_wip, fail_status_forever;
static unsigned status_polls, failstop_limit, timer_step_ticks;
static int timer_wrap_on_commit;
static jmp_buf failstop_env;
static int failstop_armed;
static volatile uint32_t reg_p33_con, reg_p33_dat;
static uint8_t p33_wdt = 0x1Du, p33_vld = 0x17u;
static uint8_t p33_frame[3];
static unsigned p33_frame_count, p33_transfer_index;
static unsigned p33_fail_transfer = (unsigned)-1;
static unsigned p33_wdt_off_verified, p33_wdt_rearmed;

static void test_p33_start(void)
{
    unsigned current = p33_transfer_index++;
    reg_p33_con &= ~(1u << 1);
    p33_frame[p33_frame_count++] = (uint8_t)reg_p33_dat;
    if (p33_frame_count == 3u) {
        uint8_t command = p33_frame[0], value = p33_frame[2];
        uint32_t address = ((uint32_t)(command & 3u) << 8) | p33_frame[1];
        uint8_t *reg = address == 0x80u ? &p33_wdt :
                       address == 0x17u ? &p33_vld : NULL;
        if (command & 0x80u) {
            reg_p33_dat = reg ? *reg : 0xFFu;
            if (address == 0x80u && !(*reg & 0x10u)) ++p33_wdt_off_verified;
            if (address == 0x80u && (*reg & 0x10u)) ++p33_wdt_rearmed;
        } else if (reg) {
            switch ((command >> 5) & 3u) {
            case 0: *reg = value; break;
            case 1: *reg |= value; break;
            case 2: *reg &= value; break;
            case 3: *reg ^= value; break;
            }
            /* WDT_CON bit 6 is the write-one-to-clear feed command. */
            if (address == 0x80u) *reg &= (uint8_t)~0x40u;
            reg_p33_dat = *reg;
        }
        p33_frame_count = 0;
    }
    if (current == p33_fail_transfer) reg_p33_con |= 1u << 1;
}

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
    } else if (tx_bytes[0] == 0x02) {
        unsigned i;
        if (tx_count >= 4u)
            for (i = 4; i < tx_count; ++i) programmed_payload[programmed_count++] = tx_bytes[i];
        destructive_pending = 1;
        nor_wip = 1;
        nor_wel = 0;
        status_polls_to_clear = hold_wip ? (unsigned)-1 : 1u;
    } else if (tx_bytes[0] == 0x20) {
        /* Model the conservative case: a timed-out byte may have reached NOR,
         * and raising CS can commit even an incomplete address/data sequence. */
        destructive_pending = 1;
        nor_wip = 1;
        nor_wel = 0;
        status_polls_to_clear = hold_wip ? (unsigned)-1 : 1u;
        if (timer_wrap_on_commit) reg_timer = UINT32_MAX - 24000u;
    }
    if (destructive_pending && tx_bytes[0] == 0x05 && failstop_armed &&
        status_polls >= failstop_limit && (hold_wip || fail_status_forever))
        longjmp(failstop_env, 1);
}
static int test_spi_wait(void)
{
    unsigned current = transfer_index++;
    int receive = (reg_spi & 0x1000u) != 0;
    reg_timer += timer_step_ticks;
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
    assert((reg_icfg & 0x100u) == 0u);
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
#define FL_IRQ_SAVE(flags) do { (flags) = reg_icfg; reg_icfg &= ~0x100u; } while (0)
#define FL_IRQ_RESTORE(flags) (reg_icfg = (flags))
static int test_source_span_ok(const uint8_t *src, uint32_t n, uint32_t off);
static int test_program_page(uint32_t off, const uint8_t *page, uint32_t n, uint32_t *took);
#define FL_PROGRAM_PAGE(off, page, n, took) test_program_page((off), (page), (n), (took))
#define FL_SOURCE_SPAN_OK(src, n, off) test_source_span_ok((src), (n), (off))
#define FM1_P33_CON reg_p33_con
#define FM1_P33_DAT reg_p33_dat
#define FM1_P33_XFER_LIMIT 4u
#define FM1_P33_START() test_p33_start()
#define FM1_P33_DESELECT() do { reg_p33_con &= ~((1u << 0) | (1u << 8)); p33_frame_count = 0; } while (0)
/* Host mocks test control flow; target link checks separately prove RAM
 * placement. Avoid ELF-only section syntax in the Mach-O host harness. */
#define RAMFN __attribute__((noinline, used))
#include "../../firmware/third_party/dinghy/hal/fm1_flash.h"

/* Host integration seam accepts ordinary process pointers for fl_write. The
 * production numeric-address policy is tested directly below. */
static int test_source_span_ok(const uint8_t *src, uint32_t n, uint32_t off)
{
    return src != NULL && n <= 300u && off <= UINT32_MAX - n;
}

static int test_program_page(uint32_t off, const uint8_t *page, uint32_t n, uint32_t *took)
{
    assert(program_calls < sizeof programmed_sources / sizeof programmed_sources[0]);
    programmed_sources[program_calls] = page;
    programmed_sizes[program_calls++] = n;
    return FL_FAR(fl_prog_ram)(off, page, n, took);
}

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
    reg_icfg = 0;
    transfer_index = 0;
    fail_transfer = (unsigned)-1;
    reply_count = reply_index = 0;
    tx_count = 0;
    programmed_count = 0;
    program_calls = 0;
    nor_wel = nor_wip = destructive_pending = ready_observed = 0;
    status_polls_to_clear = status_polls = sfc_restores = 0;
    hold_wip = fail_status_forever = failstop_armed = 0;
    failstop_limit = 0;
    timer_step_ticks = 0;
    timer_wrap_on_commit = 0;
    reg_p33_con = reg_p33_dat = 0;
    p33_wdt = 0x1Du;
    p33_vld = 0x17u;
    p33_frame_count = p33_transfer_index = 0;
    p33_fail_transfer = (unsigned)-1;
    p33_wdt_off_verified = p33_wdt_rearmed = 0;
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

static void test_source_span_policy(void)
{
    assert(fl_source_span_ok((const uint8_t *)(uintptr_t)0x01C00000u, 1u, 0x97000u));
    assert(fl_source_span_ok((const uint8_t *)(uintptr_t)0x01C7FFFFu, 1u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x01C80000u, 1u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x01C7FFFFu, 2u, 0x97000u));
    assert(fl_source_span_ok((const uint8_t *)(uintptr_t)0x02000000u, 1u, 0x97000u));
    assert(fl_source_span_ok((const uint8_t *)(uintptr_t)0x020FBFFFu, 1u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x020FC000u, 1u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x020FBFFFu, 2u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x00040200u, 1u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)(UINTPTR_MAX - 1u), 4u, 0x97000u));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x01C00000u, 1u, UINT32_MAX));
    assert(!fl_source_span_ok((const uint8_t *)(uintptr_t)0x02005700u, 16u, 0x9700u));
    assert(fl_source_span_ok((const uint8_t *)(uintptr_t)0x02005700u, 16u, 0x98000u));
    assert(fl_source_span_ok(NULL, 0u, 0xFFFFFFFFu));
}

static void test_fl_write_stages_caller_pages_before_ram_program(void)
{
    uint8_t input[300];
    unsigned i;
    reset_mock(0x20u);
    for (i = 0; i < sizeof input; ++i) input[i] = (uint8_t)(i ^ 0xA7u);
    assert(fl_write(0x970F0u, input, sizeof input) == 0);
    assert(programmed_count == sizeof input);
    assert(program_calls == 3u);
    assert(programmed_sizes[0] == 16u && programmed_sizes[1] == 256u && programmed_sizes[2] == 28u);
    for (i = 0; i < program_calls; ++i) {
        assert(programmed_sources[i] != input);
        assert(((uintptr_t)programmed_sources[i] & 3u) == 0u);
    }
    for (i = 0; i < sizeof input; ++i) assert(programmed_payload[i] == input[i]);
    assert(ready_observed && !nor_wip);
    assert_restored(0x20u, 0x1255u);
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
static void test_ready_deadline_uses_post_transaction_time(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    uint32_t took = 0;

    /* Each status transaction takes 5 ms. The ready observation occurs after
     * the 10 ms budget, but XIP must stay off until that observation. */
    reset_mock(0x20u);
    replies_set(wel, 1);
    timer_step_ticks = 60000u;
    assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == -4);
    assert(took == 15000u);
    assert(ready_observed && !nor_wip && status_polls == 4u);
    assert_restored(0x20u, 0x1255u);

    /* A normal completion inside the deadline remains success. */
    reset_mock(0);
    replies_set(wel, 1);
    timer_step_ticks = 10000u;
    took = 0;
    assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == 0);
    assert(took == 2500u);
    assert(ready_observed && !nor_wip && status_polls == 4u);
    assert_restored(0, 0x1255u);
}

static void test_unreadable_late_status_preserves_transport_error(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    uint32_t took = 0;

    reset_mock(0x20u);
    replies_set(wel, 1);
    timer_step_ticks = 50000u;
    fail_transfer = 9u; /* first readiness status receive, after program opcode */
    assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == -5);
    assert(took == 16666u);
    assert(ready_observed && !nor_wip && status_polls == 5u);
    assert_restored(0x20u, 0x1255u);
}

static void test_ready_deadline_elapsed_time_survives_timer_wrap(void)
{
    static const uint8_t wel[] = {0x02};
    static const uint8_t payload[] = {0xA5};
    uint32_t took = 0;

    reset_mock(0);
    replies_set(wel, 1);
    timer_step_ticks = 24000u;
    timer_wrap_on_commit = 1;
    assert(fl_prog_ram(0x97000u, payload, sizeof payload, &took) == 0);
    assert(took == 6000u);
    assert(ready_observed && !nor_wip && status_polls == 4u);
    assert_restored(0, 0x1255u);
}

static void test_irq_save_restore_preserves_prior_state_and_nesting(void)
{
    uint32_t outer, inner;
    reset_mock(0);
    reg_icfg = 0x5A5u; /* global enable plus unrelated ICFG bits */
    outer = irq_save();
    assert(outer == 0x5A5u);
    assert(reg_icfg == (0x5A5u & ~0x100u));

    inner = irq_save(); /* already disabled: nested save must retain that */
    assert(inner == (0x5A5u & ~0x100u));
    assert(reg_icfg == inner);
    irq_restore(inner);
    assert(reg_icfg == (0x5A5u & ~0x100u));
    irq_restore(outer);
    assert(reg_icfg == 0x5A5u);

    reg_icfg = 0x45u; /* caller entered with global interrupts disabled */
    outer = irq_save();
    assert(outer == 0x45u && reg_icfg == 0x45u);
    irq_restore(outer);
    assert(reg_icfg == 0x45u);
}

static void test_flash_wrapper_restores_prior_irq_enable(void)
{
    static const uint8_t wel[] = {0x02};
    unsigned initial;
    for (initial = 0; initial < 2; ++initial) {
        uint32_t took = 0;
        reset_mock(0x20u);
        replies_set(wel, 1);
        reg_icfg = initial ? 0x1A5u : 0xA5u;
        assert(fl_erase4k(0x97000u, &took) == 0);
        assert(ready_observed && !nor_wip);
        assert(reg_icfg == (initial ? 0x1A5u : 0xA5u));
    }
}



static void test_checked_p33_timeout_is_not_returned_as_data(void)
{
    uint8_t value = 0xA5u;
    reset_mock(0);
    p33_fail_transfer = 1u;
    assert(fm1_p33_read_checked(FM1_P3_WDT_CON, &value) == -1);
    assert(value == 0xA5u);
    assert(p33_transfer_index == 2u); /* no third byte after timed-out transfer */
    assert((reg_p33_con & ((1u << 0) | (1u << 8))) == 0u);
}

static void test_wrong_watchdog_mode_refuses_before_nor_io(void)
{
    uint32_t took = 0;
    reset_mock(0x20u);
    p33_vld |= 0x40u;
    assert(fl_erase4k(0x97000u, &took) == -6);
    assert(transfer_index == 0u && tx_count == 0u);
    assert(reg_sfc == 0u && sfc_restores == 0u);
    assert((p33_wdt & 0x10u) != 0u);
}

static void test_flash_wrapper_gates_nor_on_verified_watchdog_stop(void)
{
    static const uint8_t wel[] = {0x02};
    uint32_t took = 0;
    reset_mock(0x20u);
    replies_set(wel, 1);
    reg_icfg = 0x1A5u;
    assert(fl_erase4k(0x97000u, &took) == 0);
    assert(p33_wdt_off_verified >= 1u);
    assert(p33_wdt_rearmed >= 1u);
    assert((p33_wdt & 0x1Fu) == 0x1Du);
    assert(ready_observed && !nor_wip);
    assert(reg_icfg == 0x1A5u);
}

static void test_failed_watchdog_stop_sends_no_nor_spi_bytes(void)
{
    uint32_t took = 0;
    reset_mock(0x20u);
    p33_fail_transfer = 0u; /* first watchdog read cannot complete */
    reg_icfg = 0x145u;
    assert(fl_erase4k(0x97000u, &took) == -6);
    assert(transfer_index == 0u && tx_count == 0u);
    assert(p33_transfer_index == 1u);
    assert(reg_sfc == 0u && sfc_restores == 0u);
    assert(reg_icfg == 0x145u);
}

static void test_failed_watchdog_disable_readback_sends_no_nor_spi_bytes(void)
{
    uint32_t took = 0;
    reset_mock(0x20u);
    /* The stop write completes, but the first post-write verification times out. */
    p33_fail_transfer = 9u;
    assert(fl_erase4k(0x97000u, &took) == -6);
    assert(transfer_index == 0u && tx_count == 0u);
    assert(reg_sfc == 0u && sfc_restores == 0u);
    assert(reg_icfg == 0u);
}


static void test_rearm_failure_is_reported_only_after_ready_and_xip_restore(void)
{
    static const uint8_t wel[] = {0x02};
    uint32_t took = 0;
    reset_mock(0x20u);
    replies_set(wel, 1);
    p33_fail_transfer = 12u; /* first P33 byte after the 12-transfer stop/readback */
    assert(fl_erase4k(0x97000u, &took) == -7);
    assert(destructive_pending && ready_observed && !nor_wip);
    assert(reg_sfc == 0u && sfc_restores == 1u);
    assert(reg_icfg == 0u);
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
    test_source_span_policy();
    test_fl_write_stages_caller_pages_before_ram_program();
    test_checked_jedec_timeout();
    test_status_timeout_is_not_value();
    test_read_transfer_errors_restore_state();
    test_erase_transport_errors_wait_for_committed_command();
    test_program_transport_errors_wait_for_committed_command();
    test_status_poll_error_retries_until_verified_ready();
    test_unprovable_ready_never_restores_xip();
    test_unreadable_status_never_restores_xip();
    test_ready_deadline_uses_post_transaction_time();
    test_unreadable_late_status_preserves_transport_error();
    test_ready_deadline_elapsed_time_survives_timer_wrap();
    test_irq_save_restore_preserves_prior_state_and_nesting();
    test_flash_wrapper_restores_prior_irq_enable();
    test_checked_p33_timeout_is_not_returned_as_data();
    test_wrong_watchdog_mode_refuses_before_nor_io();
    test_flash_wrapper_gates_nor_on_verified_watchdog_stop();
    test_failed_watchdog_stop_sends_no_nor_spi_bytes();
    test_failed_watchdog_disable_readback_sends_no_nor_spi_bytes();
    test_rearm_failure_is_reported_only_after_ready_and_xip_restore();
    test_exit_preserves_pin_owner_bit();
    return 0;
}
