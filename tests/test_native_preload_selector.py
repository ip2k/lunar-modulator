import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_preload_selector_state_machine(tmp_path):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("host C compiler unavailable")
    source = tmp_path / "selector.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include "preload_selector.h"
int main(void) {
    lunar_preload_selector_t s;
    const uint8_t kinds[] = {1, 7, 1, 1, 7};
    assert(lunar_preload_init(&s, kinds, 5, 2, 1) == LUNAR_PRELOAD_ACTIVE);
    assert(s.count == 3 && s.cursor == 1);
    assert(lunar_preload_timeout(&s) == 2);
    assert(lunar_preload_confirm(&s, 0u) == UINT32_MAX);
    assert(lunar_preload_confirm(&s, 1u) == 2);
    lunar_preload_move(&s, 1);
    assert(s.projects[s.cursor] == 3);
    lunar_preload_move(&s, 1);
    assert(s.projects[s.cursor] == 0);
    lunar_preload_move(&s, -1);
    assert(s.projects[s.cursor] == 3);
    assert(lunar_preload_init(&s, kinds, 5, 0, 1) == LUNAR_PRELOAD_ACTIVE);
    assert(lunar_preload_init(&s, kinds, 5, 1, 1) == LUNAR_PRELOAD_INVALID);
    { const uint8_t one[] = {7, 1};
      assert(lunar_preload_init(&s, one, 2, 1, 1) == LUNAR_PRELOAD_BYPASS);
      assert(lunar_preload_timeout(&s) == 1); }
    assert(lunar_preload_init(&s, kinds, 65, 2, 1) == LUNAR_PRELOAD_INVALID);
    assert(lunar_preload_init(&s, kinds, 5, 4, 1) == LUNAR_PRELOAD_INVALID);
    return 0;
}
''' )
    binary = tmp_path / "selector"
    subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-Ifirmware/native", str(source), "-o", str(binary)],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run([str(binary)], check=True)


def test_platform_selector_uses_debounced_edges_before_audio():
    platform = (ROOT / "firmware/native/preload_selector_platform.h").read_text()
    source = (ROOT / "tools/native/build_application_probe.py").read_text()
    assert "fm1_input_scan();" in platform
    assert "fm1_input_edges(0)" in platform and "BTN_SEL" in platform
    assert "fm1_enc_take(ENC_SELECT)" in platform
    assert "fm1_wdt_feed();" in platform
    assert source.rindex("lunar_preload_choose(lunar_selected_startup_project_index)") < source.rindex(
        "fm1_audio_init(abuf, HALF_WORDS, isr_alnk0, 3)")
