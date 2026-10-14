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
    assert(lunar_trio_diagnostic_pulse_poll(2999, &state) == 0 && state == 0);
    assert(lunar_trio_diagnostic_pulse_poll(3000, &state) == 1 && state == 1);
    assert(lunar_trio_diagnostic_pulse_poll(4999, &state) == 0 && state == 1);
    assert(lunar_trio_diagnostic_pulse_poll(5000, &state) == -1 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(8000, &state) == 0 && state == 2);
    state = 0;
    assert(lunar_trio_diagnostic_pulse_poll(5000, &state) == 0 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(6000, &state) == 0 && state == 2);
    state = 0;
    assert(lunar_trio_diagnostic_pulse_poll(UINT32_MAX - 100u, &state) == 0);
    assert(lunar_trio_diagnostic_pulse_poll(3000, &state) == 0 && state == 2);
    assert(lunar_trio_diagnostic_pulse_poll(3000, 0) == 0);
    return 0;
}''')
    binary = tmp_path / "pulse"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"), str(source), "-o", str(binary)],
        check=True)
    subprocess.run([str(binary)], check=True)
