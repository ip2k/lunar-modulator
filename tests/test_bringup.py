"""Offline composition: actual panel/SPI1/TIMER4/recovery C, simulated registers."""
from pathlib import Path
import ctypes
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["bringup/bringup", "display/panel_probe", "display/spi1_transport",
           "timing/timer4", "recovery/request"]
SHIM = r'''
#include <string.h>
#include "firmware/bringup/bringup.h"
#include "firmware/display/spi1_transport.h"
#include "firmware/timing/timer4.h"
static struct lunar_bringup controller;
static struct lunar_spi1 spi;
static struct lunar_timer timer;
static struct lunar_recovery recovery;
static struct lunar_panel_transport bus;
static void (*real_end)(void *);
static unsigned sr[6], tr[3], pr[2];
static unsigned char mailbox[16];
static unsigned calls, sequence, last_end, first_recovery, order_errors;
static unsigned spi_bytes, first_pixel, last_command, command_count, pixel_count;
static unsigned spi_mode, spi_target, spi_pending, spi_running;
static unsigned wait_calls, wait_values[3], timer_fail_call, timer_cycles;
static unsigned p33_bytes, p33_values[3], p33_fail_at, p33_running;
static unsigned marker_writes, marker_reads, corrupt, end_calls, running;
static void effect(void) {
    ++calls; ++sequence;
    if (running && !controller.attempted) ++order_errors;
}
static unsigned spi_read(void *ctx, enum lunar_spi1_register reg) {
    (void)ctx; effect();
    if (reg == LUNAR_SPI1_CON) {
        if (spi_running && !(spi_mode == 1 && spi_bytes == spi_target))
            spi_pending = 1;
        if (spi_mode == 2 && spi_bytes + 1 == spi_target) spi_pending = 1;
        return sr[reg] | (spi_pending ? 1u << 15 : 0);
    }
    return sr[reg];
}
static void spi_write(void *ctx, enum lunar_spi1_register reg, unsigned value) {
    (void)ctx; effect(); sr[reg] = value;
    if (reg == LUNAR_SPI1_CON) {
        if (value & (1u << 14)) { spi_pending = 0; spi_running = 0; }
        if (!(value & 1)) spi_running = 0;
    }
    if (reg == LUNAR_SPI1_BUF) {
        if ((sr[LUNAR_PANEL_PORTC_OUT] & (1u << 7)) || spi_pending) ++order_errors;
        ++spi_bytes; spi_running = 1;
        if (!(sr[LUNAR_PANEL_PORTC_OUT] & (1u << 8))) {
            last_command = value; ++command_count;
        } else if (last_command == 0x2c) {
            if (!first_pixel) first_pixel = spi_bytes;
            ++pixel_count;
        }
    }
}
static unsigned timer_read(void *ctx, enum lunar_timer_register reg) {
    (void)ctx; effect();
    if (reg == LUNAR_TIMER_CON && (tr[reg] & 1) && wait_calls != timer_fail_call)
        return tr[reg] | (1u << 15);
    return tr[reg];
}
static void timer_write(void *ctx, enum lunar_timer_register reg, unsigned value) {
    (void)ctx; effect(); tr[reg] = value;
    if (reg == LUNAR_TIMER_CON && (value & 1)) ++timer_cycles;
}
static void timer_sync(void *ctx) { (void)ctx; effect(); }
static int wait_timer(void *ctx, unsigned ms) {
    (void)ctx; effect();
    if (!(sr[LUNAR_PANEL_PORTC_OUT] & (1u << 7)) || spi.active) ++order_errors;
    if (wait_calls < 3) wait_values[wait_calls] = ms;
    ++wait_calls;
    return lunar_timer_delay(&timer, ms);
}
static void traced_end(void *ctx) {
    effect(); ++end_calls; real_end(ctx); last_end = sequence;
}
static void recovery_effect(void) {
    effect();
    if (!first_recovery) {
        first_recovery = sequence;
        if (!last_end || last_end >= sequence || spi.active ||
            !(sr[LUNAR_PANEL_PORTC_OUT] & (1u << 7)) ||
            !controller.recovery_requested || !recovery.attempted) ++order_errors;
    }
}
static unsigned p33_read(void *ctx, enum lunar_recovery_register reg) {
    (void)ctx; recovery_effect();
    if (reg == LUNAR_P33_CON && p33_running && p33_bytes != p33_fail_at) {
        pr[reg] &= ~((1u << 1) | (1u << 4)); p33_running = 0;
    }
    return pr[reg];
}
static void p33_write(void *ctx, enum lunar_recovery_register reg, unsigned value) {
    (void)ctx; recovery_effect(); pr[reg] = value;
    if (reg == LUNAR_P33_DAT) {
        if (!(pr[LUNAR_P33_CON] & 1) || p33_running) ++order_errors;
        if (p33_bytes < 3) p33_values[p33_bytes] = value;
        ++p33_bytes;
    }
    if (reg == LUNAR_P33_CON && (value & (1u << 4))) {
        p33_running = 1; pr[reg] = (value & ~(1u << 4)) | (1u << 1);
    }
}
static void p33_sync(void *ctx) { (void)ctx; recovery_effect(); }
static void put_marker(void *ctx, unsigned offset, unsigned char value) {
    (void)ctx; recovery_effect(); ++marker_writes;
    if (offset >= 16) { ++order_errors; return; }
    mailbox[offset] = value;
}
static unsigned char get_marker(void *ctx, unsigned offset) {
    (void)ctx; recovery_effect(); ++marker_reads;
    if (offset >= 16) { ++order_errors; return 0; }
    return mailbox[offset] ^ ((corrupt && offset == 7) ? 1 : 0);
}
/* Reset only before binding; host simulator initialization is not production. */
int prepare(unsigned dwell, unsigned mode, unsigned target, unsigned timer_fail,
            unsigned mailbox_corrupt, unsigned p33_fail) {
    struct lunar_spi1_io sio = {0, spi_read, spi_write, wait_timer};
    struct lunar_timer_io tio = {0, timer_read, timer_write, timer_sync};
    struct lunar_recovery_io rio = {0, p33_read, p33_write, p33_sync,
                                   put_marker, get_marker};
    memset(&controller, 0, sizeof controller);
    memset(sr, 0, sizeof sr); memset(tr, 0, sizeof tr); memset(pr, 0, sizeof pr);
    memset(mailbox, 0, sizeof mailbox); memset(wait_values, 0, sizeof wait_values);
    memset(p33_values, 0, sizeof p33_values);
    running = spi_mode = spi_target = spi_pending = spi_running = 0;
    calls = sequence = last_end = first_recovery = order_errors = 0;
    spi_bytes = first_pixel = last_command = command_count = pixel_count = 0;
    wait_calls = timer_fail_call = timer_cycles = p33_bytes = p33_running = 0;
    marker_writes = marker_reads = end_calls = 0;
    if (!lunar_timer_bind(&timer, &tio, 24000000u, 3) ||
        !lunar_spi1_bind(&spi, &sio, 3, &bus) || !lunar_spi1_configure(&spi) ||
        !lunar_recovery_bind(&recovery, &rio, 3)) return 0;
    real_end = bus.end; bus.end = traced_end;
    calls = sequence = 0;
    spi_mode = mode; spi_target = target; timer_fail_call = timer_fail;
    corrupt = mailbox_corrupt; p33_fail_at = p33_fail;
    return lunar_bringup_bind(&controller, &bus, &recovery, dwell);
}
int run_controller(void) {
    int result; running = 1; result = lunar_bringup_run(&controller); running = 0;
    return result;
}
int rebind_controller(void) { return lunar_bringup_bind(&controller, &bus, &recovery, 0); }
/* Mutation after bind checks run-time malformed-input suppression. */
void invalidate(unsigned which) {
    switch (which) {
    case 0: bus.begin = 0; break; case 1: bus.write = 0; break;
    case 2: bus.end = 0; break; case 3: bus.wait_ms = 0; break;
    case 4: recovery.io.read = 0; break; case 5: recovery.io.write = 0; break;
    case 6: recovery.io.sync = 0; break; case 7: recovery.io.mailbox_write = 0; break;
    case 8: recovery.io.mailbox_read = 0; break; case 9: recovery.poll_limit = 0; break;
    case 10: recovery.poll_limit = 65537; break; case 11: controller.bus = 0; break;
    case 12: controller.recovery = 0; break; case 13: controller.dwell_ms = 1001; break;
    case 14: recovery.attempted = 1; break; case 15: recovery.failed = 1; break;
    }
}
int invalid_bind(unsigned which) {
    struct lunar_bringup fresh = {0}; invalidate(which);
    return lunar_bringup_bind(&fresh, controller.bus, controller.recovery,
                             controller.dwell_ms);
}
unsigned value(unsigned index) {
    switch (index) {
    case 0: return calls; case 1: return controller.display;
    case 2: return controller.dwell; case 3: return controller.recovery_requested;
    case 4: return controller.request_transmitted; case 5: return controller.attempted;
    case 6: return spi_bytes; case 7: return first_pixel; case 8: return pixel_count;
    case 9: return last_command; case 10: return wait_calls;
    case 11: return wait_values[0]; case 12: return wait_values[1]; case 13: return wait_values[2];
    case 14: return timer_cycles; case 15: return marker_writes; case 16: return marker_reads;
    case 17: return p33_bytes; case 18: return p33_values[0]; case 19: return p33_values[1];
    case 20: return p33_values[2]; case 21: return order_errors; case 22: return end_calls;
    case 23: return last_end; case 24: return first_recovery; case 25: return recovery.attempted;
    case 26: return spi.active; case 27: return sr[LUNAR_PANEL_PORTC_OUT] & (1u << 7);
    case 28: return tr[LUNAR_TIMER_CON]; case 29: return pr[LUNAR_P33_CON] & 1;
    case 30: return controller.bound;
    }
    return 0;
}
unsigned marker(unsigned index) { return index < 16 ? mailbox[index] : 0; }
int null_run(void) { return lunar_bringup_run(0); }
int null_bind(unsigned which) {
    struct lunar_bringup fresh = {0};
    return lunar_bringup_bind(which == 0 ? 0 : &fresh, which == 1 ? 0 : &bus,
                             which == 2 ? 0 : &recovery, 0);
}
int unbound_run(void) { struct lunar_bringup fresh = {0}; return lunar_bringup_run(&fresh); }
'''


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    path = tmp_path_factory.mktemp("bringup")
    shim = path / "shim.c"
    shim.write_text(SHIM)
    output = path / "bringup.so"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared",
                    "-fPIC", "-I", str(ROOT), str(shim),
                    *(str(ROOT / "firmware" / (s + ".c")) for s in SOURCES),
                    "-o", str(output)], check=True)
    dll = ctypes.CDLL(str(output))
    dll.prepare.argtypes = [ctypes.c_uint] * 6
    dll.prepare.restype = ctypes.c_int
    for name in ["value", "marker"]:
        getattr(dll, name).argtypes = [ctypes.c_uint]
        getattr(dll, name).restype = ctypes.c_uint
    return dll


def prepare(lib, dwell=0, mode=0, target=0, timer_fail=0, corrupt=0, p33_fail=0):
    assert lib.prepare(dwell, mode, target, timer_fail, corrupt, p33_fail) == 1
    assert lib.value(0) == 0  # bind invokes no callbacks


def nonreplay(lib):
    snapshot = [lib.value(i) for i in range(31)]
    marker = [lib.marker(i) for i in range(16)]
    assert lib.run_controller() == 2
    assert lib.rebind_controller() == 0
    assert lib.run_controller() == 2
    assert [lib.value(i) for i in range(31)] == snapshot
    assert [lib.marker(i) for i in range(16)] == marker


def request_once(lib, transmitted=True):
    assert lib.value(3) == lib.value(5) == lib.value(25) == 1
    assert lib.value(4) == int(transmitted)
    assert lib.value(15) == 16
    assert bytes(lib.marker(i) for i in range(16)) == b"usb_update_mode\0"
    assert lib.value(21) == 0
    assert lib.value(23) < lib.value(24)
    assert lib.value(26) == 0 and lib.value(27) != 0
    assert lib.value(28) == lib.value(29) == 0
    assert lib.value(0) < 1_500_000  # finite simulated callbacks incl full pixels
    if transmitted:
        assert lib.value(16) == 16
        assert lib.value(17) == 3
        assert [lib.value(i) for i in [18, 19, 20]] == [0x20, 0xa0, 0x10]
    nonreplay(lib)


@pytest.mark.parametrize("dwell", [0, 1, 1000])
def test_complete_real_components(lib, dwell):
    prepare(lib, dwell=dwell)
    assert lib.run_controller() == 1
    assert lib.value(1) == 0
    assert lib.value(2) == (1 if dwell else 0)
    assert lib.value(8) == 240 * 240 * 2
    assert lib.value(9) == 0x29
    assert lib.value(10) == (3 if dwell else 2)
    assert [lib.value(i) for i in [11, 12]] == [100, 120]
    assert lib.value(13) == dwell
    assert lib.value(14) == 220 + dwell
    request_once(lib)


@pytest.mark.parametrize("mode", [1, 2], ids=["lost_completion", "stuck_clear"])
@pytest.mark.parametrize("stage", ["sleep_out", "setup_command", "setup_data", "pixel_first", "pixel_middle"])
def test_spi_failure_still_requests_once(lib, mode, stage):
    prepare(lib)
    assert lib.run_controller() == 1
    first_pixel = lib.value(7)
    targets = {"sleep_out": 1, "setup_command": 2, "setup_data": 3,
               "pixel_first": first_pixel, "pixel_middle": first_pixel + 4096}
    prepare(lib, dwell=1000, mode=mode, target=targets[stage])
    assert lib.run_controller() == 1
    assert lib.value(1) == 2 and lib.value(2) == 0
    assert lib.value(6) == targets[stage] - (mode == 2)
    assert lib.value(10) <= 2  # failed display never dwells
    request_once(lib)


@pytest.mark.parametrize("failure_call", [1, 2, 3])
def test_timer_failure_before_display_or_dwell(lib, failure_call):
    prepare(lib, dwell=1000, timer_fail=failure_call)
    assert lib.run_controller() == 1
    assert lib.value(10) == failure_call
    assert lib.value(1) == (0 if failure_call == 3 else 3)
    assert lib.value(2) == (2 if failure_call == 3 else 0)
    if failure_call == 1:
        assert lib.value(6) == 0
    if failure_call == 3:
        assert lib.value(8) == 115200 and lib.value(9) == 0x29
    request_once(lib)


def test_corrupt_marker_never_sends_reset_or_replays(lib):
    prepare(lib, corrupt=1)
    assert lib.run_controller() == 1
    assert lib.value(1) == 0
    assert lib.value(16) == 8 and lib.value(17) == 0
    request_once(lib, transmitted=False)


@pytest.mark.parametrize("failure_byte", [1, 2, 3])
def test_p33_timeout_does_not_replay_or_erase(lib, failure_byte):
    prepare(lib, p33_fail=failure_byte)
    assert lib.run_controller() == 1
    assert lib.value(17) == failure_byte
    assert lib.value(16) == 16
    request_once(lib, transmitted=False)


@pytest.mark.parametrize("which", range(16))
def test_invalid_bind_has_no_callbacks_or_marker(lib, which):
    prepare(lib)
    assert lib.invalid_bind(which) == 0
    assert lib.value(0) == lib.value(15) == 0
    assert bytes(lib.marker(i) for i in range(16)) == bytes(16)


@pytest.mark.parametrize("which", range(16))
def test_mutated_input_latches_without_effects(lib, which):
    prepare(lib)
    lib.invalidate(which)
    assert lib.run_controller() == 0
    assert lib.value(5) == 1 and lib.value(3) == lib.value(4) == 0
    assert lib.value(0) == lib.value(15) == 0
    nonreplay(lib)


@pytest.mark.parametrize("dwell", [1001, 0xffffffff])
def test_out_of_range_dwell_bind_has_no_effects(lib, dwell):
    assert lib.prepare(dwell, 0, 0, 0, 0, 0) == 0
    assert lib.value(0) == 0 and lib.value(30) == 0
    assert lib.run_controller() == 0 and lib.value(0) == 0


def test_null_and_unbound_have_no_effects(lib):
    prepare(lib)
    for which in range(3):
        assert lib.null_bind(which) == 0
    assert lib.null_run() == lib.unbound_run() == 0
    assert lib.value(0) == lib.value(15) == 0
