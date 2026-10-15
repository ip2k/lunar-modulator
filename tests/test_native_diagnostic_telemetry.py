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
                    "-I", str(ROOT / "sim/web/src"),
                    str(source), "-o", str(exe)], check=True)
    wire = subprocess.check_output([str(exe)])
    assert wire[:8] == b"\xf0\x7dLUNAR\x01" and wire[-1] == 0xF7
    expected = [0, 1, 127, 128, 16383, 16384, 0x0fffffff, 0x10000000,
                0x7fffffff, 0x80000000, 0xffffffff, 24000, 1, 512]
    assert list(codec.decode_frame(wire).values()) == expected
    assert codec.decode_capture(wire + b"\xf8\xfe" + wire) == [
        {"schema": 1, "values": dict(zip(codec.FIELDS, expected))}
    ] * 2
    # Realtime status can legally interrupt SysEx, including its numeric data.
    interleaved = b"".join(bytes((byte, 0xf8, 0xfe)) for byte in wire)
    assert codec.decode_capture(interleaved) == [
        {"schema": 1, "values": dict(zip(codec.FIELDS, expected))}
    ]


def test_schema2_profile_wire_roundtrip_and_mixed_capture(tmp_path):
    source = tmp_path / "profile.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint32_t values[LUNAR_PROFILE_FIELDS];
    uint32_t before = 123, after = 456;
    for (unsigned i = 0; i < LUNAR_PROFILE_FIELDS; ++i) values[i] = i * 1234567u;
    assert(before == 123 && after == 456);
    assert(LUNAR_PROFILE_PACKETS == 50 && LUNAR_PROFILE_PACKETS <= 64);
    for (unsigned i = 0; i < LUNAR_PROFILE_PACKETS; ++i) {
        uint32_t packet = lunar_profile_packet(values, i);
        unsigned cin = packet & 15u;
        unsigned n = cin == 4u ? 3u : cin - 4u;
        assert(i + 1 == LUNAR_PROFILE_PACKETS ? cin == 6u : cin == 4u);
        for (unsigned j = 0; j < n; ++j) putchar((packet >> (8u * (j + 1u))) & 255u);
    }
    assert(lunar_profile_packet(values, LUNAR_PROFILE_PACKETS) == 0);
}
''')
    exe = tmp_path / "profile"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"),
                    str(source), "-o", str(exe)], check=True)
    profile = subprocess.check_output([str(exe)])
    decoded = codec.decode_profile_frame(profile)
    assert decoded["sound_0_window_ticks"] == 4 * 1_234_567
    assert decoded["display_strip_calls"] == 27 * 1_234_567
    assert decoded == dict(zip(codec.PROFILE_FIELDS,
                               (i * 1_234_567 for i in range(len(codec.PROFILE_FIELDS)))))
    mixed = codec.decode_capture(codec.PREFIX + bytes(70) + b"\xf7" + profile)
    assert [frame["schema"] for frame in mixed] == [1, 2]


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
    end = app.index("\n#ifdef LUNAR_RENDER_STAGE_PROFILE\nstatic void diagnostic_profile_report", start)
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
                    "-I", str(ROOT / "sim/web/src"),
                    str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_schema6_irq_profile_frame_is_canonical_and_mixed_capture_decodes():
    from tools.native.diagnostic_telemetry import (
        IRQ_PROFILE_FIELDS, IRQ_PROFILE_FRAME_BYTES, IRQ_PROFILE_PREFIX,
    )
    assert len(IRQ_PROFILE_FIELDS) == 22
    assert IRQ_PROFILE_FRAME_BYTES == 119
    assert IRQ_PROFILE_PREFIX == bytes((0xF0, 0x7D, *b"LUNAR", 6))

    values = list(range(22))
    values[0] = 0xFFFFFFFF
    frame = bytearray(IRQ_PROFILE_PREFIX)
    for value in values:
        frame.extend((value >> (7 * digit)) & 0x7F for digit in range(5))
    frame.append(0xF7)
    frame = bytes(frame)
    assert len(frame) == IRQ_PROFILE_FRAME_BYTES
    assert codec.decode_any_frame(frame) == (6, dict(zip(IRQ_PROFILE_FIELDS, values)))
    assert codec.decode_capture(frame)[0]["schema"] == 6

    noncanonical = bytearray(frame)
    noncanonical[len(IRQ_PROFILE_PREFIX) + 4] = 16
    with pytest.raises(ValueError, match="noncanonical"):
        codec.decode_any_frame(bytes(noncanonical))


def test_schema7_engine_profile_wire_roundtrip_and_packet_bounds(tmp_path):
    source = tmp_path / "engine_profile.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint32_t values[LUNAR_ENGINE_PROFILE_FIELDS];
    for (unsigned i = 0; i < LUNAR_ENGINE_PROFILE_FIELDS; ++i)
        values[i] = i == 1 ? UINT32_MAX : i * 1234567u;
    assert(LUNAR_ENGINE_PROFILE_BYTES == 54u);
    assert(LUNAR_ENGINE_PROFILE_PACKETS == 18u && LUNAR_ENGINE_PROFILE_PACKETS <= 64u);
    for (unsigned i = 0; i < LUNAR_ENGINE_PROFILE_PACKETS; ++i) {
        uint32_t packet = lunar_engine_profile_packet(values, i);
        unsigned cin = packet & 15u;
        unsigned n = cin == 4u ? 3u : cin - 4u;
        assert(i + 1 == LUNAR_ENGINE_PROFILE_PACKETS ? cin == 7u : cin == 4u);
        for (unsigned j = 0; j < n; ++j) putchar((packet >> (8u * (j + 1u))) & 255u);
    }
    assert(lunar_engine_profile_packet(values, LUNAR_ENGINE_PROFILE_PACKETS) == 0);
}
''')
    exe = tmp_path / "engine_profile"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"), str(source), "-o", str(exe)], check=True)
    frame = subprocess.check_output([str(exe)])
    assert len(frame) == codec.ENGINE_PROFILE_FRAME_BYTES == 54
    values = codec.decode_engine_profile_frame(frame)
    assert values["drums_render_ticks"] == 0xFFFFFFFF
    assert codec.decode_capture(frame)[0]["schema"] == 7
    assert codec.decode_capture(codec.PREFIX + bytes(70) + b"\xf7" + frame)[-1]["schema"] == 7


def test_profile_report_retains_samples_when_ring_is_full(tmp_path):
    app = (ROOT / "firmware/native/app_probe.c").read_text()
    start = app.index("static void diagnostic_profile_report(void)")
    end = app.index("\n#endif", start)
    function = app[start:end]
    source = tmp_path / "profile_queue.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <string.h>
#define MQ 64u
#define LUNAR_RENDER_STAGE_PROFILE 1
static uint32_t fm1_ms, mo_w, mo_r, sent;
static struct { unsigned config; } usb;
static struct { uint32_t ticks, maximum, calls; } lunar_profile_window[LUNAR_RENDER_PROFILE_STAGE_COUNT];
static void midi_out_event(uint32_t packet) { (void)packet; assert(mo_w - mo_r < MQ); ++mo_w; ++sent; }
''' + function + r'''
int main(void) {
    for (unsigned i = 0; i < LUNAR_RENDER_PROFILE_STAGE_COUNT; ++i) {
        lunar_profile_window[i].ticks = i + 10;
        lunar_profile_window[i].maximum = i + 20;
        lunar_profile_window[i].calls = i + 30;
    }
    fm1_ms = 1000; diagnostic_profile_report();
    assert(sent == 0 && lunar_profile_window[0].ticks == 10);
    usb.config = 1; mo_w = 15; mo_r = 0;
    fm1_ms = 2000; diagnostic_profile_report();
    assert(sent == 0 && lunar_profile_window[0].ticks == 10);
    mo_r = mo_w;
    diagnostic_profile_report();
    assert(sent == LUNAR_PROFILE_PACKETS);
    for (unsigned i = 0; i < LUNAR_RENDER_PROFILE_STAGE_COUNT; ++i)
        assert(!lunar_profile_window[i].ticks && !lunar_profile_window[i].maximum &&
               !lunar_profile_window[i].calls);
}
''')
    exe = tmp_path / "profile_queue"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"),
                    str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_engine_profile_report_reserves_complete_ring_frame_and_keeps_counters(tmp_path):
    import subprocess
    app = (ROOT / "firmware/native/app_probe.c").read_text()
    start = app.index("static void diagnostic_engine_profile_report(void)")
    end = app.index("\n#endif", start)
    function = app[start:end]
    source = tmp_path / "engine_profile_queue.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#define MQ 64u
static uint32_t fm1_ms, mo_w, mo_r, sent;
static struct { unsigned config; } usb;
static volatile uint32_t engine_profile_values[LUNAR_ENGINE_PROFILE_FIELDS];
static void midi_out_event(uint32_t packet) {
    (void)packet; assert(mo_w - mo_r < MQ); ++mo_w; ++sent;
}
''' + function + r'''
int main(void) {
    fm1_ms = 4000; usb.config = 1;
    engine_profile_values[1] = 1234;
    mo_w = 47; mo_r = 0;
    diagnostic_engine_profile_report();
    assert(sent == 0 && engine_profile_values[1] == 1234);
    mo_r = mo_w;
    diagnostic_engine_profile_report();
    assert(sent == LUNAR_ENGINE_PROFILE_PACKETS);
    assert(engine_profile_values[1] == 1234);
    assert(mo_w - mo_r == LUNAR_ENGINE_PROFILE_PACKETS);
}
''')
    exe = tmp_path / "engine_profile_queue"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"),
                    str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_profile_and_compatibility_reports_alternate_on_64_packet_ring(tmp_path):
    app = (ROOT / "firmware/native/app_probe.c").read_text()
    start = app.index("static void diagnostic_report(void)")
    end = app.index("\n#endif\n\nstatic void app_main", start)
    functions = app[start:end]
    source = tmp_path / "alternating_queue.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <string.h>
#define MQ 64u
#define LUNAR_STACK_WATERMARK 1
#define LUNAR_RENDER_STAGE_PROFILE 1
static uint32_t fm1_ms, mo_w, mo_r, sent;
static struct { unsigned config; } usb = {1};
static struct { uint32_t underruns, written; } audio_queue;
static uint32_t render_ticks_max, draw_ticks_max, lunar_midi_usb_messages,
    lunar_midi_uart_bytes, lunar_midi_accepted_noteons,
    lunar_midi_rejected_messages, lunar_master_adc_raw,
    initial_engine_result, lunar_stack_user_margin,
    lunar_stack_system_margin, lunar_stack_samples;
static struct { uint32_t ticks, maximum, calls; }
    lunar_profile_window[LUNAR_RENDER_PROFILE_STAGE_COUNT];
static void midi_out_event(uint32_t packet) {
    (void)packet; assert(mo_w - mo_r < MQ); ++mo_w; ++sent;
}
''' + functions + r'''
int main(void) {
    for (unsigned i = 0; i < LUNAR_RENDER_PROFILE_STAGE_COUNT; ++i)
        lunar_profile_window[i].ticks = 9u + i;
    fm1_ms = 1000; diagnostic_reports();
    assert(sent == LUNAR_PROFILE_PACKETS); /* profile first slot */
    assert(lunar_profile_window[0].ticks == 0); /* successful snapshot resets */
    mo_r = mo_w; /* emulate USB draining before the next slot */
    fm1_ms = 2000; diagnostic_reports();
    assert(sent == LUNAR_PROFILE_PACKETS + LUNAR_DIAGNOSTIC_PACKETS);
    mo_r = mo_w;
    fm1_ms = 3000; diagnostic_reports();
    assert(sent == 2u * LUNAR_PROFILE_PACKETS + LUNAR_DIAGNOSTIC_PACKETS);
    mo_r = mo_w;
    fm1_ms = 4000; diagnostic_reports();
    assert(sent == 2u * (LUNAR_PROFILE_PACKETS + LUNAR_DIAGNOSTIC_PACKETS));
    return 0;
}
''')
    exe = tmp_path / "alternating_queue"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"), str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_clock_snapshot_reads_once_and_roundtrips_raw_registers(tmp_path):
    source = tmp_path / "clock.c"
    source.write_text(r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
static unsigned calls;
static uint32_t load(uintptr_t address) {
    const uintptr_t addresses[] = {0x1000cu, 0x10014u, 0x10008u, 0x119a0u, 0x119a8u, 0x119acu};
    const uint32_t values[] = {0xffffffffu, 0x80000000u, 0x12345678u, 0x10203040u, 0x55667788u, 0x99aabbccu};
    assert(calls < 6 && address == addresses[calls]);
    return values[calls++];
}
#define LUNAR_CLOCK_LOAD(address) load(address)
#include "clock_snapshot.h"
#include "diagnostic_telemetry.h"
int main(void) {
    uint32_t values[4];
    uint32_t pll[4];
    lunar_clock_snapshot(values, 1234u);
    assert(calls == 3 && LUNAR_CLOCK_PACKETS == 10);
    assert(lunar_clock_packet(values, LUNAR_CLOCK_PACKETS) == 0);
    for (unsigned i = 0; i < LUNAR_CLOCK_PACKETS; ++i) {
        uint32_t packet = lunar_clock_packet(values, i);
        unsigned cin = packet & 15u;
        assert(cin == (i == 9 ? 6u : 4u));
        unsigned n = cin == 4 ? 3 : cin - 4;
        for (unsigned j = 0; j < n; ++j)
            putchar((packet >> (8u * (j + 1u))) & 255u);
        if (n < 3) assert(packet >> (8u * (n + 1u)) == 0);
    }
    lunar_pll_snapshot(pll, 1234u);
    assert(calls == 6 && LUNAR_PLL_PACKETS == 10);
    for (unsigned i = 0; i < LUNAR_PLL_PACKETS; ++i) {
        uint32_t packet = lunar_pll_packet(pll, i);
        unsigned cin = packet & 15u;
        assert(cin == (i == 9 ? 6u : 4u));
        unsigned n = cin == 4 ? 3 : cin - 4;
        for (unsigned j = 0; j < n; ++j)
            putchar((packet >> (8u * (j + 1u))) & 255u);
        if (n < 3) assert(packet >> (8u * (n + 1u)) == 0);
    }
    assert(calls == 6); /* Reporting never resamples registers. */
}
''')
    exe = tmp_path / "clock"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"), str(source), "-o", str(exe)], check=True)
    frame = subprocess.check_output([str(exe)])
    assert len(frame) == codec.CLOCK_FRAME_BYTES + codec.PLL_FRAME_BYTES
    expected = dict(zip(codec.CLOCK_FIELDS, [1234, 0xffffffff, 0x80000000, 0x12345678]))
    assert codec.decode_any_frame(frame[:codec.CLOCK_FRAME_BYTES]) == (3, expected)
    expected_pll = dict(zip(codec.PLL_FIELDS, [1234, 0x10203040, 0x55667788, 0x99aabbcc]))
    assert codec.decode_any_frame(frame[codec.CLOCK_FRAME_BYTES:]) == (4, expected_pll)
    normal = codec.PREFIX + bytes(5 * len(codec.FIELDS)) + b"\xf7"
    profile = codec.PROFILE_PREFIX + bytes(5 * len(codec.PROFILE_FIELDS)) + b"\xf7"
    assert [item['schema'] for item in codec.decode_capture(normal + frame + profile)] == [1, 3, 4, 2]
    clock_frame = frame[:codec.CLOCK_FRAME_BYTES]
    pll_frame = frame[codec.CLOCK_FRAME_BYTES:]
    for bad in (clock_frame[:-1], clock_frame[:12] + b'\x80' + clock_frame[13:],
                clock_frame[:12] + b'\x10' + clock_frame[13:]):
        with pytest.raises(ValueError):
            codec.decode_any_frame(bad)
    for bad in (pll_frame[:-1], pll_frame[:8] + b'\x80' + pll_frame[9:],
                pll_frame[:12] + b'\x10' + pll_frame[13:]):
        with pytest.raises(ValueError):
            codec.decode_any_frame(bad)


def test_diagnostic_reports_observe_pll_deadline_and_defer_full_frame(tmp_path):
    app = (ROOT / "firmware/native/app_probe.c").read_text()
    marker = "static void diagnostic_reports(void)"
    start = app.index(marker)
    brace = app.index("{", start)
    depth = 0
    end = None
    for index in range(brace, len(app)):
        if app[index] == "{":
            depth += 1
        elif app[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    assert end is not None
    function = app[start:end]
    source = tmp_path / "report_schedule.c"
    source.write_text(r'''
#include <stdint.h>
#include <assert.h>
#include "diagnostic_telemetry.h"
static uint32_t fm1_ms, mo_w, mo_r;
#define MQ 64u
static struct { unsigned config; } usb = {1};
static uint32_t clock_snapshot_values[LUNAR_CLOCK_FIELDS];
static uint32_t pll_snapshot_values[LUNAR_PLL_FIELDS];
static uint32_t sent[128];
static unsigned sent_count, ordinary_reports;
static void midi_out_event(uint32_t packet) { sent[sent_count++] = packet; ++mo_w; }
static void diagnostic_report(void) { ++ordinary_reports; }
'''+function+r'''
static unsigned schema_at(unsigned offset) { return (sent[offset + 2] >> 16) & 255u; }
int main(void) {
    fm1_ms = 0; diagnostic_reports(); assert(sent_count == 0);
    fm1_ms = 4999; diagnostic_reports(); assert(sent_count == 0);
    fm1_ms = 5000; mo_w = MQ; mo_r = 0; diagnostic_reports();
    assert(sent_count == 0); /* full queue defers rather than consuming deadline */
    mo_w = mo_r = 0; diagnostic_reports();
    assert(sent_count == LUNAR_PLL_PACKETS && schema_at(0) == 4);
    mo_w = mo_r = 0; fm1_ms = 10000; diagnostic_reports();
    assert(sent_count == 2 * LUNAR_PLL_PACKETS && schema_at(LUNAR_PLL_PACKETS) == 3);
    mo_w = mo_r = 0; fm1_ms = 14999; diagnostic_reports();
    assert(sent_count == 2 * LUNAR_PLL_PACKETS);
    fm1_ms = 15000; diagnostic_reports();
    assert(sent_count == 3 * LUNAR_PLL_PACKETS && schema_at(2 * LUNAR_PLL_PACKETS) == 4);
    assert(ordinary_reports == 4);
}
''')
    source.write_text(source.read_text().replace(
        "static void diagnostic_reports(void)",
        "#define LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT 1\n" +
        "#include \"clock_snapshot.h\"\n#include \"diagnostic_telemetry.h\"\n" +
        "static void diagnostic_reports(void)", 1))
    exe = tmp_path / "report_schedule"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "firmware/native"),
                    "-I", str(ROOT / "sim/web/src"), str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
