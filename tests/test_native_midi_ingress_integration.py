"""Join the real USB decoder, UART parser and shared native note handler."""
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import ROOT
from tests.native_test_flags import native_no_pie_flags


def _function(source: str, signature: str) -> str:
    """Extract one C function by balanced braces, preserving its source body."""
    start = source.find(signature)
    assert start >= 0, f"function signature changed: {signature}"
    brace = source.find("{", start)
    assert brace >= 0
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"unterminated function: {signature}")


@pytest.fixture(scope="session")
def midi_ingress_check(tmp_path_factory):
    cxx = shutil.which("c++")
    cc = shutil.which("cc")
    if not cxx or not cc:
        pytest.skip("host C and C++ compilers are required")

    app = (ROOT / "firmware/native/app_probe.c").read_text()
    usb = (ROOT / "firmware/third_party/dinghy/src/usb.c").read_text()
    platform = (ROOT / "firmware/third_party/dinghy/src/platform.c").read_text()
    bodies = [
        _function(usb, "static void midi_in_event(uint32_t pkt)"),
        _function(platform, "static int midi_get(uint8_t *st, uint8_t *d1, uint8_t *d2)"),
        _function(app, "static void apply_midi_event(uint8_t st, uint8_t a, uint8_t b, uint8_t channel)"),
        _function(app, "static void uart_midi_event(void *ctx, uint8_t st, uint8_t a, uint8_t b)"),
        _function(app, "static void uart_midi_poll(uint8_t channel)"),
        _function(app, "static void incoming_midi(void)"),
    ]

    out = tmp_path_factory.mktemp("native-midi-ingress")
    harness = out / "check.cpp"
    harness.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include "midi_input.h"
#include "midi_stream.h"
#include "midi_uart_stream.h"

#define LUNAR_OTA 0
#define LUNAR_UART1_MIDI 1
#define MQ 64u
#define RING_PUBLISH() __asm__ volatile("" ::: "memory")
typedef struct { uint8_t sx_on; uint32_t rx_bad; } UsbState;
static UsbState usb;
static uint32_t midi_in_q[MQ];
static volatile uint32_t mi_w, mi_r;
static uint8_t uart_midi_ring[256];
static uint32_t uart_midi_cursor, uart_midi_pending;
static uint32_t uart_received;
static uint32_t fm1_uart1_rx_take(void) { uint32_t n=uart_received; uart_received=0; return n; }
static void sysex_byte(uint8_t) {}

typedef struct { struct { uint8_t midi_in_channel; } settings; } App;
static App app;
struct Event { char kind; uint8_t note, velocity; };
static Event events[16];
static unsigned event_count;
static void record(char kind, uint8_t note, uint8_t velocity) {
    assert(event_count < sizeof events / sizeof events[0]);
    events[event_count++] = {kind, note, velocity};
}
/* Deliberate boundary: ingress and app routing are real; synth/voice state is stubbed. */
static void fm1_app_note_on(App *a, int note, int velocity) {
    assert(a == &app); record('n', (uint8_t)note, (uint8_t)velocity);
}
static void fm1_app_note_off(App *a, int note) {
    assert(a == &app); record('f', (uint8_t)note, 0);
}
static void fm1_app_all_notes_off(App *a) { assert(a == &app); record('x', 0, 0); }
static void fm1_app_pitch_bend(App *, float) {}

volatile uint32_t lunar_midi_usb_messages;
volatile uint32_t lunar_midi_uart_bytes;
volatile uint32_t lunar_midi_accepted_noteons;
volatile uint32_t lunar_midi_rejected_messages;
'''+"\n".join(bodies)+r'''

static uint32_t packet(uint8_t cin, uint8_t status, uint8_t d1, uint8_t d2) {
    return (uint32_t)cin | ((uint32_t)status << 8) |
           ((uint32_t)d1 << 16) | ((uint32_t)d2 << 24);
}
static void check_event(unsigned i, char kind, uint8_t note, uint8_t velocity) {
    assert(i < event_count);
    assert(events[i].kind == kind && events[i].note == note && events[i].velocity == velocity);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    const char *which = argv[1];
    app.settings.midi_in_channel = 3; /* MIDI channel 3 is status low nibble 2. */
    lunar_midi_stream_reset();

    if (which[0] == 'u') {
        /* Real USB-MIDI packet decoder and ring reader; velocity zero means note-off. */
        midi_in_event(packet(9, 0x92, 60, 100));
        midi_in_event(packet(9, 0x92, 60, 0));
        incoming_midi();
        assert(event_count == 2);
        check_event(0, 'n', 60, 100);
        check_event(1, 'f', 60, 0);
        assert(lunar_midi_usb_messages == 2 && lunar_midi_accepted_noteons == 1);
        assert(lunar_midi_rejected_messages == 0 && lunar_midi_uart_bytes == 0);
    } else if (which[0] == 't') {
        /* Real UART-ring adapter and maintained parser; second note uses running status. */
        const uint8_t bytes[] = {0x92, 60, 100, 61, 110, 60, 0};
        for (unsigned i=0; i<sizeof bytes; ++i) uart_midi_ring[i] = bytes[i];
        uart_received = sizeof bytes;
        incoming_midi();
        assert(event_count == 3);
        check_event(0, 'n', 60, 100);
        check_event(1, 'n', 61, 110);
        check_event(2, 'f', 60, 0);
        assert(lunar_midi_uart_bytes == sizeof bytes && lunar_midi_accepted_noteons == 2);
        assert(lunar_midi_usb_messages == 0 && lunar_midi_rejected_messages == 0);
    } else if (which[0] == 'm') {
        /* A selected-channel mismatch is rejected identically at either ingress. */
        midi_in_event(packet(9, 0x90, 60, 100)); /* channel 1, selected channel 3 */
        const uint8_t bytes[] = {0x90, 60, 100};
        for (unsigned i=0; i<sizeof bytes; ++i) uart_midi_ring[i] = bytes[i];
        uart_received = sizeof bytes;
        incoming_midi();
        assert(event_count == 0);
        assert(lunar_midi_usb_messages == 1 && lunar_midi_uart_bytes == sizeof bytes);
        assert(lunar_midi_rejected_messages == 2 && lunar_midi_accepted_noteons == 0);
    } else {
        assert(0 && "unknown scenario");
    }
    return 0;
}
''')

    uart_obj = out / "midi_uart_stream.o"
    subprocess.run([
        cc, "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"), "-c",
        str(ROOT / "firmware/native/midi_uart_stream.c"), "-o", str(uart_obj),
    ], check=True)
    binary = out / "check"
    subprocess.run([
        cxx, "-std=c++11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
        "-fno-exceptions", "-fno-rtti", *native_no_pie_flags(),
        "-I", str(ROOT / "firmware/native"),
        "-I", str(ROOT / "firmware/third_party/arduino-midi/src"),
        str(harness), str(ROOT / "firmware/native/midi_stream.cpp"),
        str(uart_obj), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("scenario", ["usb", "trs", "mismatch"])
def test_joined_midi_ingress_routes_notes_and_channel_filter(midi_ingress_check, scenario):
    subprocess.run([str(midi_ingress_check), scenario], check=True)
