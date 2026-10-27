/* SPDX-License-Identifier: MIT. Private AC79 dev-kit diagnostic only. */
#include "app_config.h"
#include "system/includes.h"
#include "device/includes.h"
#include "device/uart.h"
#include "asm/includes.h"
#include "boot_command.h"

/* Deliberately no weak fallback. The pinned cpu.a implementation writes the
 * RAM USB-download marker and invokes P33 reset itself. Inspect its actual
 * linked machine code before admitting any image for physical use. */
extern void nvram_set_boot_state(u32 state);

static void __attribute__((section(".volatile_ram_code"), noinline)) enter_rom(void)
{
    CPU_CRITICAL_ENTER();
    nvram_set_boot_state(2);
    for (;;) {}
}

/* The finite scheduling comparison keeps recovery above both render tasks. */
#if defined(LUNAR_DEVKIT_SCHEDULING_PROBE) || defined(LUNAR_DEVKIT_ENGINE_QUEUE) || defined(LUNAR_DEVKIT_RENDERER_PIPELINE)
#define CONTROL_PRIORITY 18
#else
#define CONTROL_PRIORITY 8
#endif

static void boot_control(void *unused)
{
    struct lunar_boot_command parser = {0};
    unsigned char input[32];
    void *uart = unused;
    puts("LUNAR_CONTROL ready=1 rx=PA5 baud=1000000 protocol=1\n");
    for (;;) {
        int i, n = dev_read(uart, input, sizeof(input));
        if (n < 0) {
            memset(&parser, 0, sizeof(parser));
            dev_ioctl(uart, UART_FLUSH, 0);
        } else for (i = 0; i < n; ++i) {
            enum lunar_boot_action action = lunar_boot_command_feed(
                &parser, input[i], sys_timer_get_ms());
            if (action == LUNAR_BOOT_PONG) puts("LUNAR_CONTROL pong=1\n");
            if (action == LUNAR_BOOT_ARMED) puts("LUNAR_CONTROL armed=1\n");
            if (action == LUNAR_BOOT_ENTER) {
                puts("LUNAR_CONTROL entering=uboot\n");
                enter_rom();
            }
        }
        os_time_dly(1);
    }
}

int lunar_devkit_boot_control_start(void)
{
    /* Reserve and configure recovery before app_main allocates the worker.
     * A receiver task failure must never start the diagnostic workload. */
    static unsigned char ring[128] __attribute__((aligned(32)));
    void *uart = dev_open("uart1", NULL);
    int status;
    if (!uart) { puts("LUNAR_CONTROL error=uart_open\n"); return -1; }
    if (dev_ioctl(uart, UART_SET_CIRCULAR_BUFF_ADDR, (u32)ring) ||
        dev_ioctl(uart, UART_SET_CIRCULAR_BUFF_LENTH, sizeof(ring)) ||
        dev_ioctl(uart, UART_SET_RECV_BLOCK, 0) ||
        dev_ioctl(uart, UART_START, 0)) {
        puts("LUNAR_CONTROL error=uart_start\n");
        dev_close(uart);
        return -1;
    }
    status = os_task_create(boot_control, uart, CONTROL_PRIORITY, 1024, 0, "lunar_control");
    if (status) {
        printf("LUNAR_CONTROL error=task_create status=%d\n", status);
        dev_close(uart);
    }
    return status;
}
