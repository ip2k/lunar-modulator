from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_pulse_window_once_missed_window_and_late_noteoff(tmp_path):
    source = tmp_path / "pulse.c"
    source.write_text(r'''#include "trio_diagnostic_pulse.h"
#include <assert.h>
#include <stdint.h>
int main(void) {
    uint8_t state = 0;
    assert(lunar_trio_diagnostic_pulse_poll(12999, 10000, &state) == 0 && state == 0);
    assert(lunar_trio_diagnostic_pulse_poll(13000, 10000, &state) == 1 && state == 1);
    assert(lunar_trio_diagnostic_pulse_poll(14999, 10000, &state) == 0 && state == 1);
    assert(lunar_trio_diagnostic_pulse_poll(15000, 10000, &state) == -1 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(18000, 10000, &state) == 0 && state == 2);
    state = 0;
    assert(lunar_trio_diagnostic_pulse_poll(15000, 10000, &state) == 0 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(16000, 10000, &state) == 0 && state == 2);
    state = 0;
    uint32_t origin = UINT32_MAX - 100u;
    assert(lunar_trio_diagnostic_pulse_poll(origin + 2999u, origin, &state) == 0 && state == 0);
    assert(lunar_trio_diagnostic_pulse_poll(origin + 3000u, origin, &state) == 1 && state == 1);
    assert(lunar_trio_diagnostic_pulse_poll(origin + 5000u, origin, &state) == -1 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(3000, 0, 0) == 0);
    return 0;
}''')
    binary = tmp_path / "pulse"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"), str(source), "-o", str(binary)],
        check=True)
    subprocess.run([str(binary)], check=True)


def test_app_starts_pulse_clock_after_initial_audio_refill():
    source = (ROOT / "firmware/native/app_probe.c").read_text()
    start = source.index("static void app_main(void)")
    end = len(source)
    main = source[start:end]
    ready = main.index("fm1_app_init(&app")
    initial_refill = main.index("    refill_audio();", ready)
    pulse_origin = main.index("pulse_start = fm1_ms;", initial_refill)
    loop = main.index("for (;;) {", pulse_origin)
    watchdog_origin = main.index("uint32_t start = fm1_ms;")
    assert watchdog_origin < ready < initial_refill < pulse_origin < loop
    assert "fm1_ms, pulse_start, &pulse_state" in main
