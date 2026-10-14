from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_fixed_diagnostic_fields_saturate_and_fit_footer(tmp_path):
    source = tmp_path / "readout.c"
    source.write_text(r'''#include "midi_diagnostic_readout.h"
#include <assert.h>
#include <stdint.h>
#include <string.h>
int main(void) {
    struct { char before; char line[27]; char after; } s;
    s.before='A'; s.after='Z';
    lunar_midi_diagnostic_readout(s.line, 3, 42, 7, 1023);
    assert(!strcmp(s.line, "U00003 B00042 N00007 A1023"));
    assert(strlen(s.line) == 26);
    lunar_midi_diagnostic_readout(s.line, UINT32_MAX, UINT32_MAX, 100000, 4095);
    assert(!strcmp(s.line, "U99999 B99999 N99999 A4095"));
    assert(s.before=='A' && s.after=='Z');
    return 0;
}''')
    binary = tmp_path / "readout"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"), str(source), "-o", str(binary)],
        check=True)
    subprocess.run([str(binary)], check=True)


def test_generated_platform_captures_direct_adc_without_changing_gain_path():
    source = (ROOT / "tools/native/build_application_probe.py").read_text()
    assert "'lunar_master_raw = (int32_t)k10;'" in source or (
        "'master_q12 = 4096; lunar_master_raw = (int32_t)k10; "
        "lunar_master_adc_raw = (uint32_t)a;'" in source)
    assert "lunar_master_adc_raw = (uint32_t)a;" in source
    assert "master_q12 = 4096;" in source
