from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
import build_application_probe as builder


def test_only_prepared_instrumented_song_diagnostic_can_autoplay():
    receipt = builder.validate_diagnostic_song_play(True, 'song-diagnostic', 0, True, False)
    assert receipt == dict(enabled=True, compile_definition='LUNAR_DIAGNOSTIC_SONG_PLAY=1',
                          start_ms=2000, once=True, hardware_tested=False)
    for args in [('continuous', 0, True, False), ('diagnostic', 0, True, False),
                 ('song-diagnostic', None, True, False), ('song-diagnostic', 0, False, False),
                 ('song-diagnostic', 0, True, True)]:
        with pytest.raises(ValueError):
            builder.validate_diagnostic_song_play(True, *args)
    assert not builder.validate_diagnostic_song_play(False, 'continuous', None, False, False)['enabled']


def test_one_shot_wrap_and_no_restart_after_stop(tmp_path):
    source = tmp_path / 'play.c'
    source.write_text('''#include "diagnostic_song_play.h"
#include <assert.h>
int main(void) {
    uint8_t done = 0;
    uint32_t origin = UINT32_MAX - 100;
    assert(!lunar_diagnostic_song_play_poll(origin + 1999u, origin, &done));
    assert(lunar_diagnostic_song_play_poll(origin + 2000u, origin, &done));
    assert(done == 1);
    assert(!lunar_diagnostic_song_play_poll(origin + 6000u, origin, &done));
    assert(!lunar_diagnostic_song_play_poll(2000, 0, 0));
    return 0;
}''')
    binary = tmp_path / 'play'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I',
                    str(ROOT / 'firmware/native'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_readiness_does_not_reset_recovery_deadline():
    source = (ROOT / 'firmware/native/app_probe.c').read_text()
    main = source[source.index('static void app_main(void)'):]
    assert main.index('uint32_t start = fm1_ms;') < main.index('fm1_app_init(&app')
    assert main.index('    refill_audio();') < main.index('song_ready_ms = fm1_ms;')
    assert 'lunar_runtime_expired(fm1_ms, start)' in main
    assert '&song_play_attempted) && !app.ui.playing)' in main
