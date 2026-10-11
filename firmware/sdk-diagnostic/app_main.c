/* SPDX-License-Identifier: MIT */
#include "app_config.h"
#include "system/includes.h"
#include "system/task.h"
#include "system/sys_time.h"
#include "os/os_api.h"
#include "asm/clock.h"
#include "asm/gpio.h"
#include "asm/p33.h"
#include "request.h"
#include "spi1_transport.h"

const struct irq_info irq_info_table[] = {{-1,-1,-1}};
const struct task_info task_info_table[] = {
    {"app_core",15,4096,1024}, {"sys_event",29,512,0},
    {"systimer",14,256,0}, {"sys_timer",9,512,128},
    {"lunar_diag",10,4096,0}, {0,0,0,0,0}
};
/* RAM evidence only: 1 app, 2 worker, 3 display, 4 twenty-second soak,
 * 5 probe complete, 6 acquiring P33, 7 reset transmitted, 8 reset failed. No stage means hardware acceptance. */
volatile unsigned lunar_sdk_stage, lunar_sdk_elapsed_ms, lunar_sdk_heartbeat;
volatile int lunar_sdk_result, lunar_sdk_sys_hz, lunar_sdk_lsb_hz;
volatile int lunar_sdk_recovery_result;
static struct lunar_panel_transport transport;
static struct lunar_spi1 spi;
static int (*raw_write)(void *, unsigned char);
static unsigned bytes_written;

static int delay_ms(void *context, unsigned milliseconds) {
    unsigned before, after;
    (void)context;
    if (milliseconds > 1000u) return 0;
    before = timer_get_ms();
    /* SDK os_api.h specifies a 10 ms tick. Add one tick for phase uncertainty;
     * verify reported elapsed duration rather than guessing a CPU busy loop. */
    os_time_dly((int)((milliseconds + 9u) / 10u + 1u));
    after = timer_get_ms();
    return (unsigned)(after - before) >= milliseconds;
}
static int yielding_write(void *context, unsigned char byte) {
    int ok = raw_write(context, byte);
    if (ok && (++bytes_written & 255u) == 0) {
        ++lunar_sdk_heartbeat;
        os_time_dly(1);
    }
    return ok;
}
static void diagnostic_worker(void *arg) {
    struct lunar_spi1_io io;
    struct lunar_recovery recovery;
    struct lunar_recovery_io recovery_io;
    unsigned start = timer_get_ms(), i;
    (void)arg;
    lunar_sdk_stage = 2;
    lunar_sdk_sys_hz = clk_get("sys");
    lunar_sdk_lsb_hz = clk_get("lsb");
    /* Reported frequencies only, not electrical measurements. No PLL changes.
     * BAUD4 then limits nominal SPI to <=6 MHz at this conservative bus bound. */
    if (lunar_sdk_sys_hz < 24000000 || lunar_sdk_sys_hz > 480000000 ||
        lunar_sdk_lsb_hz <= 0 || lunar_sdk_lsb_hz > 60000000) {
        lunar_sdk_result = -1; goto done;
    }
    /* Stock established PA2 low, without inferring its electrical purpose.
     * SDK owns these GPIOs: empty board devices, no USB/audio/keyscan driver. */
    if (gpio_direction_output(0x02, 0) || gpio_direction_output(0x27, 1) ||
        gpio_set_direction(0x28, 0) || gpio_set_direction(0x29, 0) ||
        gpio_set_direction(0x2a, 0)) {
        lunar_sdk_result = -2; goto done;
    }
    lunar_spi1_native_io(&io, 0, delay_ms);
    if (!lunar_spi1_bind(&spi, &io, 4096u, &transport) ||
        !lunar_spi1_configure(&spi)) {
        lunar_sdk_result = -3; goto done;
    }
    raw_write = transport.write;
    transport.write = yielding_write;
    lunar_sdk_stage = 3;
    lunar_sdk_result = lunar_panel_probe(&transport);
done:
    lunar_sdk_stage = 4;
    /* Finite wait count even if the reported clock stops advancing. app_main
     * has returned, so app_core can dispatch the vendor integrity timer. */
    for (i = 0; i < 2000u; ++i) {
        lunar_sdk_elapsed_ms = (unsigned)(timer_get_ms() - start);
        if (lunar_sdk_elapsed_ms >= 20000u) break;
        ++lunar_sdk_heartbeat;
        os_time_dly(1);
    }
    if (i == 2000u && !lunar_sdk_result) lunar_sdk_result = -4;
    lunar_sdk_stage = lunar_sdk_result ? 0xffu : 5u;
    /* One attempt, including after a failed probe. Native binding has no I/O.
     * SDK p33_lock supplies cross-core TESTSET and nested local IRQ masking.
     * It can wait indefinitely if another core halts while holding P33: this
     * recovery contract requires a healthy SDK runtime, not fault recovery.
     * No scheduler call while locked; bounded transfer, unlock on return. */
    lunar_recovery_native_io(&recovery_io);
    if (lunar_recovery_bind(&recovery, &recovery_io, 4096u)) {
        lunar_sdk_stage = 6;
        p33_lock();
        lunar_sdk_recovery_result = lunar_recovery_request(&recovery);
        p33_unlock();
        lunar_sdk_stage = lunar_sdk_recovery_result ? 7u : 8u;
    } else { lunar_sdk_stage = 8; }
    /* A transmitted reset is not proof that reset or UBOOT happened. */
    for (;;) { ++lunar_sdk_heartbeat; os_time_dly(100); }
}
void app_main(void) {
    lunar_sdk_stage = 1;
    lunar_sdk_result = task_create(diagnostic_worker, NULL, "lunar_diag");
    if (lunar_sdk_result) lunar_sdk_stage = 0xffu;
    /* Return to app_core; never starve SDK timer/event delivery. */
}
