"""Exercise target encoder against the independent host decoder and queue gate."""
from pathlib import Path
import importlib.util
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "diagnostic_telemetry", ROOT / "tools/native/diagnostic_telemetry.py")
codec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codec)


def test_wire_roundtrip_and_packet_termination(tmp_path):
    source = tmp_path / "wire.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    const uint32_t values[LUNAR_DIAGNOSTIC_FIELDS] = {
        0, 1, 127, 128, 16383, 16384, 0x0fffffff, 0x10000000,
        0x7fffffff, 0x80000000, UINT32_MAX, 24000, 1, 512
    };
    struct { uint32_t before, p[LUNAR_DIAGNOSTIC_PACKETS], after; } out;
    out.before = 123; out.after = 456;
    lunar_diagnostic_packets(out.p, values);
    assert(out.before == 123 && out.after == 456);
    assert(LUNAR_DIAGNOSTIC_PACKETS <= 64);
    for (unsigned i = 0; i < LUNAR_DIAGNOSTIC_PACKETS; ++i) {
        unsigned cin = out.p[i] & 15u;
        unsigned n = cin == 4u ? 3u : cin - 4u;
        assert(i + 1 == LUNAR_DIAGNOSTIC_PACKETS ? cin == 5u : cin == 4u);
        for (unsigned j = 0; j < n; ++j) putchar((out.p[i] >> (8u * (j + 1u))) & 255u);
        if (n < 3u) assert((out.p[i] >> (8u * (n + 1u))) == 0);
    }
}
''')
    exe = tmp_path / "wire"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    str(source), "-o", str(exe)], check=True)
    wire = subprocess.check_output([str(exe)])
    assert wire[:8] == b"\xf0\x7dLUNAR\x01" and wire[-1] == 0xF7
    expected = [0, 1, 127, 128, 16383, 16384, 0x0fffffff, 0x10000000,
                0x7fffffff, 0x80000000, 0xffffffff, 24000, 1, 512]
    assert list(codec.decode_frame(wire).values()) == expected
    assert codec.decode_capture(wire + b"\xf8\xfe" + wire) == [dict(zip(codec.FIELDS, expected))] * 2
    # Realtime status can legally interrupt SysEx, including its numeric data.
    interleaved = b"".join(bytes((byte, 0xf8, 0xfe)) for byte in wire)
    assert codec.decode_capture(interleaved) == [dict(zip(codec.FIELDS, expected))]


@pytest.mark.parametrize("mutation", ["short", "long", "version", "high", "overflow", "end"])
def test_invalid_frames_are_not_zero_measurements(mutation):
    wire = bytearray(codec.PREFIX + b"\0" * (5 * len(codec.FIELDS)) + b"\xf7")
    if mutation == "short": wire.pop()
    elif mutation == "long": wire.append(0)
    elif mutation == "version": wire[7] = 2
    elif mutation == "high": wire[8] = 128
    elif mutation == "overflow": wire[12] = 16
    elif mutation == "end": wire[-1] = 0
    with pytest.raises(ValueError): codec.decode_frame(bytes(wire))


def test_empty_or_partial_capture_fails():
    for data in (b"", b"\xf8", codec.PREFIX):
        with pytest.raises(ValueError): codec.decode_capture(data)


def test_report_admits_whole_frame_without_blocking(tmp_path):
    # Compile the actual production report function with a finite output ring.
    # A partial SysEx on a full/disconnected host would poison later captures.
    app = (ROOT / "firmware/native/app_probe.c").read_text()
    start = app.index("static void diagnostic_report(void)")
    end = app.index("\n#endif\n\nstatic void app_main", start)
    function = app[start:end]
    source = tmp_path / "queue.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#define MQ 64u
#define LUNAR_STACK_WATERMARK 1
static uint32_t fm1_ms, mo_w, mo_r, sent;
static struct { unsigned config; } usb;
static struct { uint32_t underruns, written; } audio_queue;
static uint32_t render_ticks_max, draw_ticks_max, lunar_midi_usb_messages,
    lunar_midi_uart_bytes, lunar_midi_accepted_noteons,
    lunar_midi_rejected_messages, lunar_master_adc_raw,
    initial_engine_result, lunar_stack_user_margin,
    lunar_stack_system_margin, lunar_stack_samples;
static void midi_out_event(uint32_t packet) {
    (void)packet; assert(mo_w - mo_r < MQ); ++mo_w; ++sent;
}
''' + function + r'''
int main(void) {
    fm1_ms = 1000; diagnostic_report(); assert(sent == 0); /* unconfigured */
    usb.config = 1;
    fm1_ms = 1999; diagnostic_report(); assert(sent == 0); /* rate limited */
    mo_w = MQ - LUNAR_DIAGNOSTIC_PACKETS + 1;
    fm1_ms = 2000; diagnostic_report(); assert(sent == 0); /* insufficient */
    mo_w = UINT32_MAX - 10u;
    mo_r = mo_w - (MQ - LUNAR_DIAGNOSTIC_PACKETS);
    fm1_ms = 3000; diagnostic_report();
    assert(sent == LUNAR_DIAGNOSTIC_PACKETS && mo_w - mo_r == MQ);
    mo_r = mo_w;
    fm1_ms = 3001; diagnostic_report(); assert(sent == LUNAR_DIAGNOSTIC_PACKETS);
    fm1_ms = UINT32_MAX - 500u; diagnostic_report();
    assert(sent == 2u * LUNAR_DIAGNOSTIC_PACKETS);
    mo_r = mo_w;
    fm1_ms = 500; diagnostic_report(); /* elapsed 1001ms across wrap */
    assert(sent == 3u * LUNAR_DIAGNOSTIC_PACKETS);
    return 0;
}
''')
    exe = tmp_path / "queue"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
