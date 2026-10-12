"""Native editor transport: locate bounds, frozen pause and rewind semantics."""
from tests.seq_helpers import Script, seq_tools  # noqa: F401


def test_pause_freezes_and_resume_continues_native_position(seq_tools, tmp_path):
    s = Script(tracks=8, rate=44118, block=64)
    s.cmd('loop 0 0 64; tog 0 3 60 100').play().blocks(300).snap('before').cmd('pause').snap('paused')
    s.blocks(1000).snap('held').cmd('resume').blocks(100).snap('resumed')
    r = s.run(seq_tools, tmp_path, compat=False)
    before, held, resumed = (r.state(n) for n in ('before', 'held', 'resumed'))
    assert held['paused'] == 1 and held['playing'] == 0
    assert held['master_tick'] == before['master_tick']
    assert held['playback_frames'] == before['playback_frames']
    assert held['tracks'][0]['pos'] == before['tracks'][0]['pos']
    assert resumed['master_tick'] > held['master_tick']
    assert resumed['playback_frames'] == before['playback_frames'] + 6400
    assert any(e['kind'] == 'continue' for e in r.events)
    assert not [e for e in r.between('paused', 'held') if e['kind'] == 'on']
    assert any(e['kind'] == 'off' for e in r.between('before', 'held'))


def test_rewind_zeroes_position_time_and_clip_phase(seq_tools, tmp_path):
    s = Script(tracks=8).cmd('loop 0 16 32; tog 0 16 60 100').play().blocks(500).cmd('pause').cmd('rewind').snap('stop')
    r = s.run(seq_tools, tmp_path, compat=False); end = r.state('stop')
    assert end['playing'] == end['paused'] == end['master_tick'] == end['playback_frames'] == 0
    assert end['tracks'][0]['pos'] == 16 * 24


def test_seek_bounds_and_arrangement_entry(seq_tools, tmp_path):
    s = Script(tracks=8).cmd('loop 0 0 32; clipsel 0 1; loop 0 0 16; sgins 0 0 2; sgins 1 1 1')
    s.play().cmd('pause').cmd('seekbar 3').snap('located').cmd('seekbar 999').snap('high').cmd('seekbar -8').snap('low')
    r = s.run(seq_tools, tmp_path, compat=False)
    assert r.state('located')['master_tick'] == 3 * 384
    assert r.state('located')['tracks'][0]['playing'] == 0
    assert r.state('high')['master_tick'] == 4 * 384
    assert r.state('high')['tracks'][0]['playing'] == 1
    assert r.state('low')['master_tick'] == 0
    assert r.state('low')['paused'] == 1
