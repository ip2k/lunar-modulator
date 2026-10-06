"""Movy's seq-core tests, transcribed for the C core in compat mode.

Each test names its source: a #[test] in Movy's engine/crates/seq-core/src/
at commit 9190e79 (github.com/DimaDake/schwung-movy, MIT, Copyright (c) 2026
megadake), with the line it starts on. Movy's tests call engine methods and
set fields directly; here the same steps are Movy `cmd` verbs in a timed
script (tests/seq_helpers.py), and fields are read back from fm1-seq's state
dumps. Where a test needed a field no verb sets, the nearest verb route is
used and the docstring says so. Movy's tests run 16 tracks at 44.1 kHz in
128-frame blocks; so do these. Skipped: the Move link and inject tests, the
status-string tests and undo (not in this stage).
"""
import json

import pytest

from tests.seq_helpers import (TPB, TPS, Script, ccs, clip, kinds, notes,
                               offs, ons, run_script, seq_tools, track)  # noqa: F401


def S(**kw):
    return Script(**kw)


# ---- clock.rs -----------------------------------------------------------------

def test_tick_rate_exact_over_one_minute_120bpm(seq_tools, tmp_path):
    """clock.rs tick_rate_exact_over_one_minute_120bpm (92)."""
    s = S().play()
    s.blocks(44100 * 60 // 128)
    r = s.run(seq_tools, tmp_path)
    assert abs(r.end["master_tick"] - 120 * 96) <= 1


def test_no_drift_over_an_hour_fractional_bpm(seq_tools, tmp_path):
    """clock.rs no_drift_over_an_hour_fractional_bpm (107): exact integer tick
    count after an hour at 133.33 BPM."""
    blocks = 44100 * 3600 // 128
    frames = blocks * 128
    path = tmp_path / "h.txt"
    path.write_text("#! rate=44100 block=128 tracks=1\n@0 bpm 13333\n@0 play\n")
    out = tmp_path / "h.json"
    import subprocess
    subprocess.run([str(seq_tools), "--cmd", str(path), "--compat", "--end", str(frames),
                    "--state", str(out)], check=True)
    end = json.loads(out.read_text())["end"]
    assert end["master_tick"] == frames * 13333 * 96 // (44100 * 60 * 100)


def test_ticks_per_block_at_most_needed(seq_tools, tmp_path):
    """clock.rs ticks_per_block_at_most_needed (122): at 300 BPM a 128-frame
    block carries at most two ticks, and the count stays the exact integer
    quotient. A 1-step clip with a note gives every 24th tick an event; the
    count check covers the rest."""
    s = S(tracks=1).cmd("bpm 30000").cmd("loop 0 0 16;clen 0 1").cmd("tog 0 0 60 100")
    s.cmd("cscl 0 24 1").play().blocks(2000)
    r = s.run(seq_tools, tmp_path)
    per_block = {}
    for e in r.events:
        if e["kind"] == "on":
            per_block.setdefault(e["block"], set()).add(e["tick"])
    assert per_block and max(len(v) for v in per_block.values()) <= 2
    assert r.end["master_tick"] == 2000 * 128 * 30000 * 96 // (44100 * 6000)


def test_bpm_clamped(seq_tools, tmp_path):
    """clock.rs bpm_clamped (138), through the `bpm` verb."""
    _, a = run_script(seq_tools, tmp_path, "@0 bpm 1\n", compat=True, name="lo")
    _, b = run_script(seq_tools, tmp_path, "@0 bpm 999999\n", compat=True, name="hi")
    assert (a["bpm_x100"], b["bpm_x100"]) == (2000, 30000)


# ---- engine.rs: transport and clock out -----------------------------------------

def test_clock_emits_start_then_24ppqn_ticks(seq_tools, tmp_path):
    """engine.rs clock_emits_start_then_24ppqn_ticks (3203)."""
    s = S().cmd("tog 0 0 60 100").play().run_ticks(96)
    ev = s.run(seq_tools, tmp_path).events
    assert len(kinds(ev, "start")) == 1
    assert len(kinds(ev, "clock")) == 24
    first_clock = next(i for i, e in enumerate(ev) if e["kind"] == "clock")
    first_note = next(i for i, e in enumerate(ev) if e["kind"] == "on")
    assert first_clock < first_note


def test_clock_stop_emits_stop_once_and_goes_silent(seq_tools, tmp_path):
    """engine.rs clock_stop_emits_stop_once_and_goes_silent (3223)."""
    s = S().play().run_ticks(8).mark("stop").cmd("stop").blocks(1).mark("after")
    s.blocks(50)
    r = s.run(seq_tools, tmp_path)
    assert len(kinds(r.between("stop", "after"), "stop")) == 1
    later = r.between("after", 10 ** 12)
    assert not [e for e in later if e["kind"] in ("clock", "start")]


def test_clock_exact_count_across_many_blocks(seq_tools, tmp_path):
    """engine.rs clock_exact_count_across_many_blocks (3241)."""
    ev = S().play().run_ticks(384).run(seq_tools, tmp_path).events
    assert len(kinds(ev, "clock")) == 96


@pytest.mark.parametrize("num,den,want", [(1, 1, 48), (2, 1, 96), (1, 2, 24), (3, 4, 36)])
def test_scale_changes_playhead_rate(seq_tools, tmp_path, num, den, want):
    """engine.rs scale_changes_playhead_rate (3276), pos_after (3253)."""
    s = S().cmd("loop 0 0 32").cmd(f"cscl 0 {num} {den}").play().run_ticks(48)
    assert track(s.run(seq_tools, tmp_path).end, 0)["pos"] == want


@pytest.mark.parametrize("num,den,want", [(1, 1, 24), (2, 1, 12)])
def test_note_gate_scales_with_clip_scale(seq_tools, tmp_path, num, den, want):
    """engine.rs note_gate_scales_with_clip_scale (3341): the master tick of the
    note-off of a one-step note."""
    s = S().cmd("loop 0 0 16").cmd("tog 0 0 60 100").cmd(f"cscl 0 {num} {den}").play()
    s.run_ticks(40)
    off = offs(s.run(seq_tools, tmp_path).events, 0, 60)
    assert off[0]["tick"] == want


def test_stopped_track_flushes_hanging_notes(seq_tools, tmp_path):
    """engine.rs stopped_track_flushes_hanging_notes (3323). Movy clears
    playing_slot by hand; here `stoptrk` does it at the bar, and the gate still
    open there is flushed by service_tick on that same tick."""
    s = S().cmd("loop 0 0 32").cmd("tog 0 0 60 100").cmd("slen 0 0 0 -1 600").play()
    s.run_ticks(48).cmd("stoptrk 0").run_ticks(400)
    ev = s.run(seq_tools, tmp_path).events
    off = offs(ev, 0, 60)
    assert [e["tick"] for e in off] == [384]
    assert len(ons(ev, 0, 60)) == 1


def test_transpose_shifts_emitted_pitch_only(seq_tools, tmp_path):
    """engine.rs transpose_shifts_emitted_pitch_only (3349)."""
    s = S().cmd("loop 0 0 16").cmd("tog 0 0 60 100").cmd("ctr 0 12").play().run_ticks(4)
    r = s.run(seq_tools, tmp_path)
    assert ons(r.events)[0]["a"] == 72
    assert notes(r.end, 0)[0]["pitch"] == 60


def test_drum_track_ignores_clip_transpose_on_emit_and_off(seq_tools, tmp_path):
    """engine.rs drum_track_ignores_clip_transpose_on_emit (3368) and
    drum_track_gate_matches_untransposed_pitch (3384)."""
    s = S().cmd("tdrum 0 1").cmd("loop 0 0 16").cmd("tog 0 0 36 100").cmd("ctr 0 -12").play()
    ev = s.run_ticks(4 + 2 * TPS).run(seq_tools, tmp_path).events
    assert ons(ev)[0]["a"] == 36
    assert offs(ev)[0]["a"] == 36


def test_melodic_track_still_transposes_after_drum_guard(seq_tools, tmp_path):
    """engine.rs melodic_track_still_transposes_after_drum_guard (3416)."""
    s = S().cmd("tdrum 0 1").cmd("tdrum 0 0").cmd("loop 0 0 16").cmd("tog 0 0 60 100")
    s.cmd("ctr 0 12").play().run_ticks(4)
    assert ons(s.run(seq_tools, tmp_path).events)[0]["a"] == 72


@pytest.mark.parametrize("drum,want", [(0, 62), (1, 38)])
def test_recording_stores_untransposed_pitch(seq_tools, tmp_path, drum, want):
    """engine.rs recording_stores_untransposed_pitch (3451) and
    drum_track_records_pad_pitch_verbatim (3400). Movy moves pos_tick by hand
    between note-on and note-off; here four ticks run."""
    pitch = 67 if not drum else 38
    s = S().cmd(f"tdrum 0 {drum}").cmd("loop 0 0 16").cmd("ctr 0 5").play().cmd("rec 0")
    s.run_ticks(1).cmd(f"non 0 {pitch} 100").run_ticks(4).cmd(f"nof 0 {pitch}").snap("x")
    r = s.run(seq_tools, tmp_path)
    assert notes(r.state("x"), 0)[-1]["pitch"] == want


def test_live_record_captures_at_scaled_position(seq_tools, tmp_path):
    """engine.rs live_record_captures_at_scaled_position (3433)."""
    s = S().cmd("loop 0 0 16").cmd("cscl 0 2 1").play().cmd("rec 0").run_ticks(3)
    s.peek("before").cmd("non 0 64 100").cmd("nof 0 64").snap("x")
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("before"), 0)["pos"] == 6
    n = [n for n in notes(r.state("x"), 0) if n["pitch"] == 64][0]
    assert n["tick"] == 6


# ---- engine.rs: trig conditions and probability --------------------------------

def test_condition_skips_trig_on_off_cycle(seq_tools, tmp_path):
    """engine.rs condition_skips_trig_on_off_cycle (3466)."""
    s = S().cmd("tog 0 0 60 100").cmd("loop 0 0 16").cmd("econd 0 0 0 -1 2 2").play()
    s.run_ticks(16 * TPS).mark("cycle2").run_ticks(16 * TPS)
    r = s.run(seq_tools, tmp_path)
    assert not ons(r.between(0, "cycle2"), pitch=60)
    assert ons(r.between("cycle2", 10 ** 12), pitch=60)


def test_probability_zero_never_plays(seq_tools, tmp_path):
    """engine.rs probability_zero_never_plays (3481)."""
    s = S().cmd("tog 0 0 60 100").cmd("loop 0 0 16").cmd("eprob 0 0 0 -1 0").play()
    assert not ons(s.run_ticks(16 * TPS * 4).run(seq_tools, tmp_path).events)


def test_chord_shares_one_probability_decision(seq_tools, tmp_path):
    """engine.rs chord_shares_one_probability_decision (3492)."""
    s = S().cmd("tog 0 0 60 100 64 100").cmd("loop 0 0 16").cmd("eprob 0 0 0 -1 50").play()
    ev = s.run_ticks(16 * TPS * 8).run(seq_tools, tmp_path).events
    a, b = ons(ev, pitch=60), ons(ev, pitch=64)
    assert len(a) == len(b)
    assert [e["tick"] for e in a] == [e["tick"] for e in b]


@pytest.mark.parametrize("a,b,inv,plays", [
    (1, 2, 0, [1, 3, 5]), (2, 2, 0, [2, 4, 6]), (4, 7, 0, [4, 11, 18]), (1, 2, 1, [2, 4, 6]),
])
def test_condition_truth_table(seq_tools, tmp_path, a, b, inv, plays):
    """clip.rs condition_truth_table (743), played: the passes on which A:B
    sounds, docs/13 §7's worked vectors (1:2 -> 1, 3, 5; 4:7 -> 4, 11, 18)."""
    s = S(tracks=1).cmd("loop 0 0 16;clen 0 1").cmd("tog 0 0 60 100").cmd(f"econd 0 0 0 -1 {a} {b}")
    s.cmd(f"einv 0 0 0 -1 {inv}").play().run_ticks(24 * 20)
    ev = ons(s.run(seq_tools, tmp_path).events)
    passes = [e["tick"] // 24 + 1 for e in ev]
    assert passes[:3] == plays


# ---- engine.rs: playback -------------------------------------------------------------

def test_plays_note_at_step_and_releases(seq_tools, tmp_path):
    """engine.rs plays_note_at_step_and_releases (3520)."""
    ev = S().cmd("tog 0 0 60 100").play().run_ticks(TPS + 2).run(seq_tools, tmp_path).events
    on = [i for i, e in enumerate(ev) if e["kind"] == "on"]
    off = [i for i, e in enumerate(ev) if e["kind"] == "off"]
    assert ev[on[0]]["a"] == 60 and ev[on[0]]["b"] == 100 and ev[off[0]]["a"] == 60
    assert on[0] < off[0]


def test_note_join_is_phase_locked_to_a_playing_clip(seq_tools, tmp_path):
    """engine.rs note_join_is_phase_locked_to_a_playing_clip (3562)."""
    s = S().cmd("tog 1 0 62 100").play().run_ticks(5 * TPS).cmd("tog 0 0 60 100")
    ev = s.run_ticks(3 * TPB).run(seq_tools, tmp_path).events
    t0 = {e["tick"] for e in ons(ev, 0)}
    t1 = {e["tick"] for e in ons(ev, 1)}
    assert t0 and t0 <= t1


def test_four_tracks_play_simultaneously(seq_tools, tmp_path):
    """engine.rs four_tracks_play_simultaneously (3703)."""
    s = S()
    for t in range(4):
        s.cmd(f"tog {t} 0 {60 + t} 100")
    ev = s.play().run_ticks(4).run(seq_tools, tmp_path).events
    for t in range(4):
        assert [(e["a"], e["b"]) for e in ons(ev, t)] == [(60 + t, 100)]


def test_loop_wraps_and_replays(seq_tools, tmp_path):
    """engine.rs loop_wraps_and_replays (3756)."""
    ev = S().cmd("tog 0 0 60 100").play().run_ticks(16 * TPS + 4).run(seq_tools, tmp_path).events
    assert len(ons(ev)) == 2


def test_muted_track_is_silent_but_advances(seq_tools, tmp_path):
    """engine.rs muted_track_is_silent_but_advances (3770)."""
    r = S().cmd("tog 0 0 60 100").cmd("mute 0 1").play().run_ticks(8).run(seq_tools, tmp_path)
    assert not ons(r.events) and not offs(r.events)
    assert track(r.end, 0)["pos"] > 0


def test_mute_flushes_that_tracks_gates(seq_tools, tmp_path):
    """engine.rs mute_flushes_that_tracks_gates (3786)."""
    s = S().cmd("tog 0 0 60 100").cmd("tog 1 0 64 100").play().run_ticks(2).mark("m")
    s.cmd("mute 0 1").blocks(1).mark("after").run_ticks(48)
    r = s.run(seq_tools, tmp_path)
    assert ons(r.between(0, "m"), 0) and ons(r.between(0, "m"), 1)
    assert [(e["track"], e["a"]) for e in offs(r.between("m", "after"))] == [(0, 60)]
    assert len(offs(r.events, 0, 60)) == 1, "flushed gate does not fire a duplicate note-off"


def test_unmute_emits_nothing(seq_tools, tmp_path):
    """engine.rs unmute_emits_nothing (3823)."""
    s = S().cmd("tog 0 0 60 100").play().run_ticks(2).cmd("mute 0 1").blocks(1).mark("u")
    s.cmd("mute 0 0").blocks(1).mark("v")
    r = s.run(seq_tools, tmp_path)
    assert not offs(r.between("u", "v"))
    assert len(offs(r.events)) == 1


@pytest.mark.parametrize("setup,sounds,silent", [
    ("pmute 0 36 1", [38], [36]),
    ("psolo 0 36", [36], [38]),
])
def test_pad_mute_and_solo(seq_tools, tmp_path, setup, sounds, silent):
    """engine.rs pad_mute_silences_only_that_voice (3843),
    pad_solo_silences_the_other_pads (3860)."""
    s = S().cmd("tog 0 0 36 100 38 100").cmd(setup).play().run_ticks(8)
    ev = s.run(seq_tools, tmp_path).events
    for p in sounds:
        assert ons(ev, pitch=p)
    for p in silent:
        assert not ons(ev, pitch=p)


def test_pad_solo_overrides_that_voice_mute(seq_tools, tmp_path):
    """engine.rs pad_solo_overrides_that_voice_mute (3881)."""
    s = S().cmd("tog 0 0 36 100").cmd("pmute 0 36 1").cmd("psolo 0 36").play().run_ticks(8)
    assert ons(s.run(seq_tools, tmp_path).events, pitch=36)


def test_pmute_and_psolo_flush_the_gates_they_silence(seq_tools, tmp_path):
    """engine.rs pmute_flushes_that_voices_gate (3898) and
    psolo_flushes_the_gates_it_silences (3922)."""
    s = S().cmd("tog 0 0 36 100 38 100").cmd("tog 1 0 40 100").play().run_ticks(2)
    s.mark("m").cmd("psolo 0 36").blocks(1).mark("n")
    r = s.run(seq_tools, tmp_path)
    flushed = [(e["track"], e["a"]) for e in offs(r.between("m", "n"))]
    assert flushed == [(0, 38)]
    s2 = S().cmd("tog 0 0 36 100 38 100").play().run_ticks(2).mark("m").cmd("pmute 0 36 1")
    s2.blocks(1).mark("n")
    r2 = s2.run(seq_tools, tmp_path, name="b")
    assert [(e["track"], e["a"]) for e in offs(r2.between("m", "n"))] == [(0, 36)]


def test_stop_releases_held_gates(seq_tools, tmp_path):
    """engine.rs stop_releases_held_gates (3945)."""
    s = S().cmd("tog 0 0 60 100").play().run_ticks(2).mark("s").cmd("stop").run_ticks(50)
    r = s.run(seq_tools, tmp_path)
    after = r.between("s", 10 ** 12)
    assert [(e["kind"], e["a"]) for e in after if e["kind"] in ("on", "off")] == [("off", 60)]


def test_play_restarts_from_clip_start(seq_tools, tmp_path):
    """engine.rs play_restarts_from_clip_start (3963)."""
    s = S().cmd("tog 0 0 60 100").play().run_ticks(30).cmd("stop").play().snap("p")
    s.mark("m").run_ticks(2)
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("p"), 0)["pos"] == 0
    assert [(e["a"], e["b"]) for e in ons(r.between("m", 10 ** 12))] == [(60, 100)]


def test_playback_wraps_inside_loop_window(seq_tools, tmp_path):
    """engine.rs playback_wraps_inside_loop_window (3977)."""
    s = S().cmd("tog 0 0 60 100").cmd("tog 0 16 64 100").cmd("loop 0 16 16").play().snap("p")
    r = s.run_ticks(16 * TPS + 4).run(seq_tools, tmp_path)
    assert track(r.state("p"), 0)["pos"] == 16 * TPS
    assert ons(r.events, pitch=64) and not ons(r.events, pitch=60)


def test_empty_clip_does_not_advance_position(seq_tools, tmp_path):
    """engine.rs empty_clip_does_not_advance_position (4783)."""
    assert track(S().play().run_ticks(10).run(seq_tools, tmp_path).end, 0)["pos"] == 0


# ---- engine.rs: swing and quantise (R5, R6) ----------------------------------------------

def fire_tick(tool, tmp_path, step, nudge=0, quant=None, swing=50, name="q"):
    s = S(tracks=1).cmd(f"swing {swing}").cmd(f"tog 0 {step} 60 100")
    if nudge:
        s.cmd(f"enudge 0 {step} {step} -1 {nudge}")
    if quant is not None:
        s.cmd(f"cq 0 {quant}")
    s.play().run_ticks(TPB)
    return ons(s.run(tool, tmp_path, name=name).events)[0]["tick"]


@pytest.mark.parametrize("step,nudge,quant,swing,want", [
    (2, 7, 100, 50, 48),          # quant_100_snaps_to_grid (5200)
    (2, 7, 0, 50, 55),            # quant_0_plays_raw_timing (5205)
    (1, 5, 0, 66, 24 + 5 + 6),    # quant_scales_deviation_and_leaves_swing_alone (5210)
    (1, 5, 100, 66, 24 + 6),
    (1, 5, 60, 66, 24 + 2 + 6),
    (2, 8, 50, 50, 52),           # quant_50_lands_midway_toward_grid (5221)
    (2, -8, 50, 50, 44),          # quant_pulls_early_note_forward (5226)
    (0, 0, None, 50, 0),          # swing_delays_offbeat_steps_only (5256)
    (1, 0, None, 50, 24),
    (0, 0, None, 80, 0),
    (1, 0, None, 80, 36),
])
def test_quantise_and_swing_fire_ticks(seq_tools, tmp_path, step, nudge, quant, swing, want):
    """engine.rs quant_fire_tick (5050) and swing_delays_offbeat_steps_only'
    fire_tick (5262): the clip tick a note fires on, one bar from Play."""
    assert fire_tick(seq_tools, tmp_path, step, nudge, quant, swing) == want


def test_quant_change_mid_pass_does_not_double_trigger(seq_tools, tmp_path):
    """engine.rs quant_change_mid_pass_does_not_double_trigger (5233)."""
    s = S(tracks=1).cmd("tog 0 2 60 100").cmd("enudge 0 2 2 -1 9").cmd("cq 0 100").play()
    s.run_ticks(2 * TPS + 4).cmd("cq 0 0").run_ticks(TPS)
    assert len(ons(s.run(seq_tools, tmp_path).events, pitch=60)) == 1


# ---- engine.rs: automation (R8) ------------------------------------------------------------

def lane0(s, base=40):
    """Lane 0 assigned with base `base`, no CC (Movy sets the fields directly)."""
    return s.cmd("alabel 0 0 synth:x").cmd(f"abaseq 0 0 {base}")


def test_automation_latches_forward_emitting_on_change_only(seq_tools, tmp_path):
    """engine.rs automation_latches_forward_emitting_on_change_only (3617)."""
    s = lane0(S()).cmd("tog 0 0 60 100").cmd("aset 0 0 2 100 1").play()
    ev = s.run_ticks(16 * TPS + 2).run(seq_tools, tmp_path).events
    assert ccs(ev) == [(0, 40), (0, 100), (0, 40)]


def test_automation_reverts_to_base_on_note_at_other_step(seq_tools, tmp_path):
    """engine.rs automation_reverts_to_base_on_note_at_other_step (3635)."""
    s = lane0(S()).cmd("tog 0 0 60 100").cmd("tog 0 8 62 100").cmd("aset 0 0 2 100 1").play()
    ev = s.run_ticks(16 * TPS + 2).run(seq_tools, tmp_path).events
    assert ccs(ev) == [(0, 40), (0, 100), (0, 40)]


def test_automation_carries_across_loop_boundary(seq_tools, tmp_path):
    """engine.rs automation_carries_across_loop_boundary (3650)."""
    s = lane0(S()).cmd("aset 0 0 14 77 1").cmd("loop 0 0 16").play()
    ev = s.run_ticks(32 * TPS + 2).run(seq_tools, tmp_path).events
    assert ccs(ev) == [(0, 40), (0, 77)]


def effective_at(locks, note_steps, length, start, lane, step, base):
    """clip.rs effective_at (218), in Python, for the oracle test."""
    rel = (step - start) & 0xFFFF
    for d in range(length):
        s = start + (rel - d) % length
        if (lane, s) in locks:
            return locks[(lane, s)]
        if s in note_steps:
            return base
    return base


def test_automation_matches_effective_at_oracle_in_steady_state(seq_tools, tmp_path):
    """engine.rs automation_matches_effective_at_oracle_in_steady_state (3669):
    in the second bar the applied value at every tick is effective_at's."""
    s = lane0(S()).cmd("tog 0 0 60 100").cmd("tog 0 8 62 100").cmd("aset 0 0 2 100 1")
    s.cmd("aset 0 0 10 55 1").play().run_ticks(16 * TPS).run_ticks(16 * TPS)
    r = s.run(seq_tools, tmp_path)
    locks = {(0, 2): 100, (0, 10): 55}
    want = [effective_at(locks, {0, 8}, 16, 0, 0, st, 40) for st in range(16)]
    assert track(r.end, 0)["lanes"][0]["eff"] == want, "the core's effective_at"
    value = None
    by_tick = {}
    for e in r.events:
        if e["kind"] == "cc":
            by_tick[e["tick"]] = e["b"]
    for m in range(2 * TPB):
        value = by_tick.get(m, value)
        if m >= TPB:
            step = ((m + 1) % TPB) // TPS          # pos after servicing tick m
            assert value == want[step], f"tick {m} step {step}"


def test_no_cc_for_unassigned_lane(seq_tools, tmp_path):
    """engine.rs no_cc_for_unassigned_lane (3693)."""
    s = S().cmd("tog 0 0 60 100").cmd("aset 0 0 0 50").play().run_ticks(TPS + 2)
    assert not kinds(s.run(seq_tools, tmp_path).events, "cc")


# ---- engine.rs, command.rs: clip and step editing ------------------------------------

def locks_of(state, t=0, slot=0):
    out = {}
    for line in state["movy1"].splitlines():
        p = line.split()
        if p[:1] == ["lk"] and int(p[1]) == t and int(p[2]) == slot:
            for item in p[3].split(";"):
                lane, step, val = map(int, item.split(":"))
                out[(lane, step)] = val
    return out


def trigs_of(state, t=0, slot=0):
    for line in state["movy1"].splitlines():
        p = line.split()
        if p[:1] == ["tg"] and int(p[1]) == t and int(p[2]) == slot:
            return [tuple(map(int, item.split(":"))) for item in p[3].split(";")]
    return []


def test_copy_paste_carries_locks_even_without_notes(seq_tools, tmp_path):
    """engine.rs copy_paste_carries_locks_even_without_notes (3719)."""
    s = S().cmd("tog 0 0 60 100").cmd("aset 0 2 1 77 1").cmd("cpy 0 0 3").cmd("pst 0 8")
    r = s.run(seq_tools, tmp_path, end=0)
    assert locks_of(r.end)[(2, 9)] == 77
    assert any(n["step"] == 8 for n in notes(r.end, 0))


def test_paste_steps_replaces_destination(seq_tools, tmp_path):
    """engine.rs paste_steps_replaces_destination (3733) and
    paste_steps_empty_source_clears_destination (3747)."""
    s = S().cmd("tog 0 0 60 100").cmd("tog 0 4 62 100").cmd("cpy 0 0 0").cmd("pst 0 4")
    r = s.run(seq_tools, tmp_path, end=0)
    assert [n["pitch"] for n in notes(r.end, 0) if n["step"] == 4] == [60]
    s = S().cmd("tog 0 2 62 100").cmd("cpy 0 0 0").cmd("pst 0 2")
    r = s.run(seq_tools, tmp_path, end=0, name="b")
    assert not [n for n in notes(r.end, 0) if n["step"] == 2]


def test_copy_paste_steps_command(seq_tools, tmp_path):
    """command.rs copy_paste_steps (1000)."""
    s = S().cmd("tog 0 0 60 100;tog 0 2 64 110").cmd("cpy 0 0 3").cmd("pst 0 8").snap("a")
    s.cmd("pst 1 0").snap("b").cmd("cpyclr;pst 1 4")
    r = s.run(seq_tools, tmp_path, end=0)
    a = notes(r.state("a"), 0)
    assert {n["step"] for n in a} >= {8, 10}
    n10 = [n for n in a if n["step"] == 10][0]
    assert (n10["pitch"], n10["vel"]) == (64, 110)
    assert any(n["step"] == 0 for n in notes(r.state("b"), 1))
    assert not any(n["step"] == 4 for n in notes(r.end, 1))


def test_ltog_inherits_the_step_span_in_melodic_view_only(seq_tools, tmp_path):
    """engine.rs ltog_inherits_the_step_span_in_melodic_view_only (4655). Movy
    adds the (tick 100, gate 60) note raw; here tog, enudge and slen make it."""
    for wlane, want in (("-1", (100, 60)), ("36", (4 * TPS, TPS))):
        s = S().cmd("loop 0 0 16").cmd("tog 0 4 60 100").cmd("enudge 0 4 4 -1 4")
        s.cmd("slen 0 4 4 -1 60").cmd(f"wlane {wlane};ltog 0 4 67 110")
        r = s.run(seq_tools, tmp_path, end=0, name=f"w{wlane}")
        n = [n for n in notes(r.end, 0) if n["pitch"] == 67][0]
        assert (n["tick"], n["gate"]) == want


def test_trig_property_commands(seq_tools, tmp_path):
    """command.rs trig_property_commands (1974)."""
    s = S().cmd("tog 0 2 60 100").cmd("eprob 0 2 2 -1 40;econd 0 2 2 -1 2 3;einv 0 2 2 -1 1")
    assert trigs_of(s.run(seq_tools, tmp_path, end=0).end) == [(2, -1, 40, 2, 3, 1)]


def test_trig_pruned_when_back_to_defaults(seq_tools, tmp_path):
    """clip.rs trig_pruned_when_back_to_defaults (720) and
    drum_lane_trig_is_pitch_specific (703)."""
    s = S().cmd("eprob 0 3 3 -1 50").cmd("eprob 0 4 4 36 30").snap("a").cmd("eprob 0 3 3 -1 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert trigs_of(r.state("a")) == [(3, -1, 50, 1, 1, 0), (4, 36, 30, 1, 1, 0)]
    assert trigs_of(r.end) == [(4, 36, 30, 1, 1, 0)], "swap_remove moved the last row up"


def test_malformed_and_unknown_ops_ignored(seq_tools, tmp_path):
    """command.rs malformed_and_unknown_ops_ignored (2123)."""
    s = S().cmd("tog 0;;frobnicate 1 2 3; ;tog 9 0 60 100;tog 0 0 999 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert notes(r.end, 0) == [] and not r.end["playing"]
    assert len(notes(r.end, 9)) == 1


def test_tog_places_chord_and_ltog_toggles_one_lane(seq_tools, tmp_path):
    """command.rs tog_places_chord (2132) and ltog_toggles_one_lane (2145)."""
    s = S().cmd("tog 0 2 60 100 64 90 67 80").snap("a").cmd("tog 0 2 72 100").snap("b")
    s.cmd("ltog 1 0 36 100;ltog 1 0 38 100").snap("c").cmd("ltog 1 0 36 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert [n["step"] for n in notes(r.state("a"), 0)] == [2, 2, 2]
    assert notes(r.state("b"), 0) == []
    assert len(notes(r.state("c"), 1)) == 2
    assert [n["pitch"] for n in notes(r.end, 1)] == [38]


def test_note_edit_commands(seq_tools, tmp_path):
    """command.rs note_edit_commands (2157)."""
    s = S().cmd("tog 0 0 60 100").cmd("evel 0 0 0 -1 -30").snap("v").cmd("etrn 0 0 0 -1 12")
    s.cmd("enudge 0 0 0 -1 5").snap("n").cmd("ltog 0 0 38 100").cmd("evel 0 0 0 38 -50")
    r = s.run(seq_tools, tmp_path, end=0)
    assert notes(r.state("v"), 0)[0]["vel"] == 70
    assert (notes(r.state("n"), 0)[0]["pitch"], notes(r.state("n"), 0)[0]["tick"]) == (72, 5)
    by = {n["pitch"]: n for n in notes(r.end, 0)}
    assert by[38]["vel"] == 50 and by[72]["vel"] == 70


def test_clip_copy_delete_commands(seq_tools, tmp_path):
    """command.rs clip_copy_delete_commands (2176)."""
    s = S().cmd("tog 0 0 60 100;tog 0 4 62 100").cmd("del 0 0 0 -1").snap("a")
    s.cmd("clipdup 0").snap("b").cmd("clipdel 0").snap("c")
    s.cmd("clipsel 0 0;clipdel 0").cmd("ltog 0 0 36 100;ltog 0 8 36 100;ltog 0 4 38 100")
    s.cmd("del 0 0 255 36")
    r = s.run(seq_tools, tmp_path, end=0)
    assert {n["step"] for n in notes(r.state("a"), 0)} == {4}
    b = r.state("b")
    assert track(b, 0)["active"] == 1 and {n["step"] for n in notes(b, 0)} == {4}
    assert clip(r.state("c"), 0) is None
    assert [n["pitch"] for n in notes(r.end, 0)] == [38]


def test_loop_and_double_commands(seq_tools, tmp_path):
    """command.rs loop_and_double_commands (2223) and clip.rs
    double_loop_copies_notes_and_doubles_length (1016)."""
    s = S().cmd("tog 0 0 60 100;loop 0 0 16").cmd("dbl 0").snap("d").cmd("loop 0 16 16")
    r = s.run(seq_tools, tmp_path, end=0)
    d = clip(r.state("d"), 0)
    assert d["len"] == 32 and any(n[4] == 16 for n in d["notes"])
    assert (clip(r.end, 0)["loop_start"], clip(r.end, 0)["len"]) == (16, 16)


def test_note_within_sub_bar_length_does_not_extend(seq_tools, tmp_path):
    """command.rs note_within_sub_bar_length_does_not_extend (2238)."""
    s = S().cmd("clen 0 12").cmd("tog 0 4 60 100").snap("a").cmd("tog 0 20 60 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert clip(r.state("a"), 0)["len"] == 12
    assert clip(r.end, 0)["len"] == 32


def test_a_press_in_the_hidden_tail_cannot_round_the_clip_up(seq_tools, tmp_path):
    """clip.rs a_press_in_the_hidden_tail_cannot_round_the_clip_up (818)."""
    s = S().cmd("tog 0 0 60 100").cmd("clen 0 15").cmd("tog 0 15 60 100").cmd("ltog 0 15 62 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert clip(r.end, 0)["len"] == 15 and len(notes(r.end, 0)) == 1


def test_step_entry_untransposes_like_live_record(seq_tools, tmp_path):
    """command.rs step_entry_untransposes_like_live_record (2251) and
    tdrum_makes_step_entry_store_the_pad_pitch_verbatim (2268)."""
    s = S().cmd("loop 0 0 16").cmd("ctr 0 5").cmd("tog 0 0 67 100").cmd("ltog 0 4 38 100")
    s.cmd("addp 0 8 8 60 100").cmd("tdrum 0 1").cmd("ltog 0 12 38 100")
    got = {(n["step"], n["pitch"]) for n in notes(s.run(seq_tools, tmp_path, end=0).end, 0)}
    assert got == {(0, 62), (4, 33), (8, 55), (12, 38)}


def test_clip_param_commands_set_active_clip(seq_tools, tmp_path):
    """command.rs clip_param_commands_set_active_clip (2286)."""
    s = S().cmd("loop 0 0 16").cmd("clen 0 9;cscl 0 3 4;ctr 0 -40").snap("a").cmd("clen 0 0")
    r = s.run(seq_tools, tmp_path, end=0)
    a = clip(r.state("a"), 0)
    assert (a["len"], a["scale"], a["transpose"]) == (9, [3, 4], -36)
    assert clip(r.end, 0)["len"] == 1


def test_slen_and_length_caps(seq_tools, tmp_path):
    """command.rs slen_sets_note_length (2301), clip.rs
    adjust_length_caps_at_next_same_pitch (1061)."""
    s = S().cmd("tog 0 0 60 100").cmd("slen 0 0 0 -1 96").snap("a")
    s.cmd("tog 0 2 60 100").cmd("elen 0 0 0 -1 100")
    r = s.run(seq_tools, tmp_path, end=0)
    assert notes(r.state("a"), 0)[0]["gate"] == 96
    assert notes(r.end, 0)[0]["gate"] == 48, "capped at the next same-pitch note"


def test_automation_commands_set_lane_lock_base(seq_tools, tmp_path):
    """command.rs automation_commands_set_lane_lock_base (2311) and
    a_quiet_lock_is_stored_but_not_applied_until_its_step_plays (2341)."""
    s = S().cmd("alabel 0 1 synth:cutoff").snap("l").mark("b").cmd("abase 0 1 64").blocks(1)
    s.mark("q").cmd("abaseq 0 1 30").cmd("aset 0 1 6 80 1").cmd("asetr 0 1 8 11 70 1").blocks(1)
    s.mark("loud").cmd("aset 0 1 5 90").cmd("asetr 0 1 8 11 60").blocks(1).mark("end1")
    s.cmd("aclrs 0 1 5").snap("c").cmd("aclr 0 1")
    r = s.run(seq_tools, tmp_path)
    lane = track(r.state("l"), 0)["lanes"][1]
    assert lane["assigned"] == 1 and lane["label"] == "synth:cutoff"
    assert ccs(r.between("b", "q")) == [(1, 64)]
    assert ccs(r.between("q", "loud")) == []
    assert ccs(r.between("loud", "end1")) == [(1, 90), (1, 60)]
    c = locks_of(r.state("c"))
    assert (1, 5) not in c and c[(1, 6)] == 80 and all(c[(1, s)] == 60 for s in range(8, 12))
    assert track(r.state("c"), 0)["lanes"][1]["assigned"] == 1
    assert track(r.end, 0)["lanes"][1]["assigned"] == 0 and locks_of(r.end) == {}


def test_lane_freed_when_last_clip_lock_removed(seq_tools, tmp_path):
    """command.rs lane_freed_when_last_clip_lock_removed (2378)."""
    s = S().cmd("alabel 0 0 synth:cutoff").cmd("aset 0 0 4 100").cmd("clipsel 0 1")
    s.cmd("aset 0 0 4 90").cmd("clipsel 0 0").cmd("clipdel 0").snap("a").cmd("clipdelat 0 1")
    r = s.run(seq_tools, tmp_path, end=0)
    assert track(r.state("a"), 0)["lanes"][0]["assigned"] == 1
    assert track(r.end, 0)["lanes"][0]["assigned"] == 0
    assert track(r.end, 0)["lanes"][0]["label"] == ""


def test_auto_clear_step_frees_lanes(seq_tools, tmp_path):
    """command.rs auto_clear_step_frees_lone_lane_but_keeps_one_with_other_locks
    (2397) and auto_clear_step_all_frees_step_only_lane (2412)."""
    s = S().cmd("alabel 0 2 synth:res").cmd("aset 0 2 7 64").cmd("aclrs 0 2 7").snap("a")
    s.cmd("alabel 0 1 synth:cutoff").cmd("aset 0 1 3 50;aset 0 1 8 60").cmd("aclrs 0 1 3")
    s.snap("b").cmd("alabel 0 0 synth:x").cmd("aset 0 0 5 70").cmd("aclrstep 0 5")
    r = s.run(seq_tools, tmp_path, end=0)
    assert track(r.state("a"), 0)["lanes"][2]["assigned"] == 0
    assert track(r.state("b"), 0)["lanes"][1]["assigned"] == 1
    assert track(r.end, 0)["lanes"][0]["assigned"] == 0


def test_batch_tags_suppress_a_resent_batch(seq_tools, tmp_path):
    """command.rs a_resent_batch_is_applied_once (1990), a_new_sequence_number_applies
    (2000), an_untagged_batch_still_applies_every_time (2011),
    only_the_immediately_previous_batch_is_suppressed (2023). The tag follows
    the frame, so the script line is not a comment."""
    text = ("@0 #1;tog 0 0 60 100\n@0 #1;tog 0 0 60 100\n@0 #2;tog 0 4 60 100\n"
            "@0 tog 1 0 60 100\n@0 tog 1 0 60 100\n"
            "@0 #7;tog 2 0 60 100\n@0 #8;tog 2 4 60 100\n@0 #7;tog 2 8 60 100\n")
    _, end = run_script(seq_tools, tmp_path, "#! tracks=16\n" + text, compat=True)
    assert len(notes(end, 0)) == 2
    assert len(notes(end, 1)) == 0
    assert len(notes(end, 2)) == 3


def test_tog_while_playing_queues_selected_slot_to_next_bar(seq_tools, tmp_path):
    """command.rs tog_while_playing_queues_selected_slot_to_next_bar (2052),
    ltog_while_playing_queues_selected_slot (2075), tog_does_not_autostart_transport
    (2043)."""
    s = S().cmd("tog 3 0 60 100").snap("stopped").play().snap("p").cmd("tog 0 4 60 100").snap("q")
    s.cmd("ltog 1 4 36 100").snap("l")
    while s.tick < TPB + 2:
        s.blocks(1)
    r = s.run(seq_tools, tmp_path)
    assert not r.state("stopped")["playing"] and clip(r.state("stopped"), 3)["len"] == 16
    assert track(r.state("p"), 0)["playing"] is None
    q = track(r.state("q"), 0)
    assert (q["queued"], q["playing"]) == (0, None)
    assert track(r.state("l"), 1)["queued"] == 0
    assert (track(r.end, 0)["playing"], track(r.end, 0)["queued"]) == (0, None)


# ---- engine.rs: recording (R12) -------------------------------------------------------

def held(pitch=60):
    """engine.rs recording_with_a_held_note (4471)."""
    s = S().cmd("rec 0", starts=True).run_ticks(TPB + 1)
    return s.cmd(f"non 0 {pitch} 100").run_ticks(2 * TPS)


def test_recording_captures_live_notes_after_count_in(seq_tools, tmp_path):
    """engine.rs recording_captures_live_notes_after_count_in (4430)."""
    s = S().cmd("rec 0", starts=True).snap("armed").run_ticks(TPB + 1).snap("rec")
    s.cmd("non 0 60 100").run_ticks(2 * TPS).cmd("nof 0 60")
    r = s.run(seq_tools, tmp_path)
    a = r.state("armed")
    assert a["playing"] and a["counting_in"] and not a["recording"]
    assert r.state("rec")["recording"] and not r.state("rec")["counting_in"]
    n = notes(r.end, 0)
    assert len(n) == 1 and (n[0]["pitch"], n[0]["vel"]) == (60, 100)
    assert n[0]["gate"] >= TPS and n[0]["suppress"] == 1


def test_count_in_and_metronome_emit_clicks(seq_tools, tmp_path):
    """engine.rs count_in_and_metronome_emit_clicks (4453)."""
    s = S().cmd("rec 0", starts=True).run_ticks(TPB).mark("m").cmd("metro 1").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    assert len(kinds(r.between(0, "m"), "click")) == 4
    bar = kinds(r.between("m", 10 ** 12), "click")
    assert len(bar) == 4 and len([e for e in bar if e["a"] == 1]) == 1


def test_rec_stop_keeps_a_note_that_is_still_held(seq_tools, tmp_path):
    """engine.rs rec_stop_keeps_a_note_that_is_still_held (4482)."""
    s = held().cmd("rec 0").snap("x").run_ticks(2 * TPS).cmd("nof 0 60")
    r = s.run(seq_tools, tmp_path)
    assert not r.state("x")["recording"]
    n = notes(r.end, 0)
    assert len(n) == 1 and 3 * TPS <= n[0]["gate"] <= 5 * TPS


def test_rec_stop_captures_nothing_played_after_it(seq_tools, tmp_path):
    """engine.rs rec_stop_captures_nothing_played_after_it (4505)."""
    s = held().cmd("rec 0").cmd("non 0 67 100").run_ticks(TPS).cmd("nof 0 67").cmd("nof 0 60")
    assert [n["pitch"] for n in notes(s.run(seq_tools, tmp_path).end, 0)] == [60]


def test_transport_stop_ends_a_held_note_there(seq_tools, tmp_path):
    """engine.rs transport_stop_ends_a_held_note_there (4519)."""
    n = notes(held().cmd("stop").run(seq_tools, tmp_path).end, 0)
    assert len(n) == 1 and TPS <= n[0]["gate"] <= 3 * TPS


def test_an_unreleased_tail_is_finalized_at_the_clip_end(seq_tools, tmp_path):
    """engine.rs an_unreleased_tail_is_finalized_at_the_clip_end (4535)."""
    s = held().cmd("rec 0").run_ticks(TPB + TPS).snap("x").cmd("nof 0 60")
    r = s.run(seq_tools, tmp_path)
    n = notes(r.state("x"), 0)
    c = clip(r.state("x"), 0)
    assert len(n) == 1 and n[0]["tick"] + n[0]["gate"] == (c["loop_start"] + c["len"]) * TPS
    assert len(notes(r.end, 0)) == 1, "the release duplicated it"


def test_a_tail_note_is_audible_on_the_very_next_loop(seq_tools, tmp_path):
    """engine.rs a_tail_note_is_audible_on_the_very_next_loop (4553)."""
    s = held().cmd("rec 0").mark("a").run_ticks(TPB).mark("b").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    assert len(ons(r.between("a", "b"), pitch=60)) == 1
    assert len(ons(r.between("b", 10 ** 12), pitch=60)) == 1


def test_a_note_finalized_on_its_own_pass_is_still_suppressed(seq_tools, tmp_path):
    """engine.rs a_note_finalized_on_its_own_pass_is_still_suppressed (4573)."""
    assert notes(held().cmd("nof 0 60").run(seq_tools, tmp_path).end, 0)[0]["suppress"] == 1


def test_a_long_tail_stops_at_the_clip_end_instead_of_droning(seq_tools, tmp_path):
    """engine.rs a_long_tail_stops_at_the_clip_end_instead_of_droning (4583)."""
    s = S().cmd("rec 0", starts=True).run_ticks(TPB + 1).run_ticks(14 * TPS)
    s.cmd("non 0 60 100").run_ticks(6 * TPS).cmd("rec 0").run_ticks(40 * TPS).cmd("nof 0 60")
    r = s.run(seq_tools, tmp_path)
    c, n = clip(r.end, 0), notes(r.end, 0)
    assert len(n) == 1 and n[0]["tick"] > 0
    assert n[0]["tick"] + n[0]["gate"] == (c["loop_start"] + c["len"]) * TPS
    assert n[0]["gate"] < c["len"] * TPS


def test_arming_the_next_take_resolves_the_previous_tail(seq_tools, tmp_path):
    """engine.rs arming_the_next_take_resolves_the_previous_tail (4612)."""
    r = held().cmd("rec 0").cmd("rec 0").snap("x").cmd("nof 0 60").run(seq_tools, tmp_path)
    assert len(notes(r.state("x"), 0)) == 1 and len(notes(r.end, 0)) == 1


def test_a_tail_lands_in_the_clip_it_was_played_into(seq_tools, tmp_path):
    """engine.rs a_tail_lands_in_the_clip_it_was_played_into (4624)."""
    r = held().cmd("rec 0").cmd("clipsel 0 1").cmd("nof 0 60").run(seq_tools, tmp_path)
    assert len(notes(r.end, 0, 0)) == 1 and notes(r.end, 0, 1) == []


def test_deleting_the_clip_drops_its_tail(seq_tools, tmp_path):
    """engine.rs deleting_the_clip_drops_its_tail (4637)."""
    s = held().cmd("rec 0").cmd("clipdel 0").cmd("tog 0 4 64 100").cmd("nof 0 60")
    assert [n["pitch"] for n in notes(s.run(seq_tools, tmp_path).end, 0)] == [64]


def test_toggle_record_twice_stops(seq_tools, tmp_path):
    """engine.rs toggle_record_twice_stops (4672)."""
    s = S().cmd("rec 0", starts=True).run_ticks(TPB + 1).snap("a").cmd("rec 0").snap("b")
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["recording"] and not r.state("b")["recording"]


def test_record_while_playing_or_stopped(seq_tools, tmp_path):
    """engine.rs record_while_playing_skips_count_in (4863),
    record_while_stopped_arms_count_in (4873),
    overdub_punch_in_still_records_immediately (5021)."""
    r = S().cmd("tog 0 0 60 100").play().cmd("rec 0").snap("x").run(seq_tools, tmp_path)
    assert r.state("x")["recording"] and not r.state("x")["counting_in"]
    r = S().cmd("tog 0 0 60 100").cmd("rec 0", starts=True).snap("x").run(seq_tools, tmp_path, name="b")
    assert r.state("x")["counting_in"] and not r.state("x")["recording"]


def test_clips_silent_during_count_in_then_play(seq_tools, tmp_path):
    """engine.rs clips_silent_during_count_in_then_play (4882)."""
    s = S().cmd("tog 0 0 60 100").cmd("rec 0", starts=True).run_ticks(TPB - 4).mark("m").run_ticks(8)
    r = s.run(seq_tools, tmp_path)
    assert not ons(r.between(0, "m")) and ons(r.between("m", 10 ** 12), pitch=60)


def test_first_recording_auto_extends_and_overdub_does_not(seq_tools, tmp_path):
    """engine.rs first_recording_auto_extends_clip (4910) and
    overdub_does_not_auto_extend_clip (4923)."""
    s = S().cmd("rec 0", starts=True).run_ticks(TPB + 1).snap("a").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["recording"] and clip(r.state("a"), 0)["len"] == 16
    assert clip(r.end, 0)["len"] == 32
    s = S().cmd("tog 0 0 60 100").cmd("rec 0", starts=True).run_ticks(TPB + 1).run_ticks(TPB)
    assert clip(s.run(seq_tools, tmp_path, name="b").end, 0)["len"] == 16


def test_punch_in_records_into_empty_slot_and_extends(seq_tools, tmp_path):
    """engine.rs punch_in_records_into_empty_slot_and_extends (4938)."""
    s = S().cmd("tog 1 0 48 100").play().cmd("launch 0 2").cmd("rec 0").run_ticks(1).snap("a")
    s.cmd("non 0 60 110").run_ticks(2 * TPS).cmd("nof 0 60").snap("b").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    a = r.state("a")
    assert a["recording"] and track(a, 0)["playing"] == 2 and not track(a, 0)["pending_stop"]
    assert len(notes(r.state("b"), 0, 2)) == 1
    assert clip(r.end, 0, 2)["len"] > clip(r.state("b"), 0, 2)["len"]


def test_punch_in_into_empty_slot_waits_for_the_bar(seq_tools, tmp_path):
    """engine.rs punch_in_into_empty_slot_waits_for_the_bar (4969) and
    second_rec_press_cancels_a_pending_take (5033)."""
    s = S().cmd("tog 1 0 48 100").play().run_ticks(3 * TPS).cmd("launch 0 2").cmd("rec 0")
    s.snap("a").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    a = r.state("a")
    assert not a["recording"] and a["counting_in"]
    e = r.end
    assert e["recording"] and track(e, 0)["playing"] == 2 and not e["counting_in"]
    assert track(e, 0)["pos"] == track(e, 1)["pos"]
    s = S().cmd("tog 1 0 48 100").play().run_ticks(3 * TPS).cmd("launch 0 2").cmd("rec 0")
    s.cmd("rec 0").snap("a").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path, name="b")
    assert not r.state("a")["counting_in"] and not r.end["recording"]


def test_punch_in_take_is_aligned_with_the_master_bar(seq_tools, tmp_path):
    """engine.rs punch_in_take_is_aligned_with_the_master_bar (4996)."""
    s = S().cmd("tog 1 0 48 100").play().run_ticks(5 * TPS).cmd("launch 0 2").cmd("rec 0")
    s.run_ticks(TPB - 5 * TPS + 2 * TPS).cmd("non 0 60 110").run_ticks(TPS).cmd("nof 0 60")
    n = notes(s.run(seq_tools, tmp_path).end, 0, 2)
    assert len(n) == 1 and n[0]["step"] == 2


def armed(left):
    """engine.rs armed_with_count_in_left (5074): 8-frame blocks."""
    s = S(block=8).cmd("rec 0", starts=True)
    while s.tick < TPB - left:
        s.blocks(1)
    return s


def test_preroll_note_is_captured_at_the_clip_start(seq_tools, tmp_path):
    """engine.rs preroll_note_is_captured_at_the_clip_start (5086)."""
    s = armed(6).cmd("non 0 60 100")
    while s.tick < TPB:
        s.blocks(1)
    n = notes(s.cmd("nof 0 60").run(seq_tools, tmp_path).end, 0)
    assert [(x["pitch"], x["step"], x["tick"]) for x in n] == [(60, 0, 0)]


def test_preroll_gate_spans_the_count_in(seq_tools, tmp_path):
    """engine.rs preroll_gate_spans_the_count_in (5101)."""
    s = armed(6).cmd("non 0 60 100")
    while s.tick < TPB:
        s.blocks(1)
    s.run_ticks(10).cmd("nof 0 60")
    assert notes(s.run(seq_tools, tmp_path).end, 0)[0]["gate"] >= 16


def test_preroll_window_is_half_a_step(seq_tools, tmp_path):
    """engine.rs preroll_note_released_before_recording_still_records (5118) and
    note_earlier_than_half_a_step_is_ignored (5126)."""
    s = armed(8).cmd("non 0 62 100").cmd("nof 0 62")
    assert [n["pitch"] for n in notes(s.run(seq_tools, tmp_path).end, 0)] == [62]
    s = armed(TPS).cmd("non 0 64 100").cmd("nof 0 64")
    assert notes(s.run(seq_tools, tmp_path, name="b").end, 0) == []


# ---- engine.rs: launches, scenes, song (R11) ----------------------------------------

def test_launch_when_stopped_is_immediate(seq_tools, tmp_path):
    """engine.rs launch_when_stopped_is_immediate (4682)."""
    s = S().cmd("clipsel 1 2;tog 1 0 60 100;clipsel 1 0").cmd("launch 1 2", starts=True).snap("a")
    r = s.run_ticks(2).run(seq_tools, tmp_path)
    a = r.state("a")
    assert a["playing"] and track(a, 1)["playing"] == 2 and track(a, 1)["active"] == 2
    assert track(a, 0)["playing"] is None
    assert [(e["track"], e["a"], e["b"]) for e in ons(r.events)] == [(1, 60, 100)]


def test_launch_while_running_is_bar_quantized(seq_tools, tmp_path):
    """engine.rs launch_while_running_is_bar_quantized (4696)."""
    s = S().cmd("tog 0 0 60 100;clipsel 0 3;tog 0 0 67 100;clipsel 0 0")
    s.cmd("launch 0 0", starts=True).run_ticks(2 * TPS).cmd("launch 0 3").snap("a").run_ticks(TPB)
    r = s.run(seq_tools, tmp_path)
    assert (track(r.state("a"), 0)["playing"], track(r.state("a"), 0)["queued"]) == (0, 3)
    assert (track(r.end, 0)["playing"], track(r.end, 0)["queued"]) == (3, None)


def test_empty_slot_selects_and_stops_track(seq_tools, tmp_path):
    """engine.rs empty_slot_selects_and_stops_track (4713)."""
    s = S().cmd("tog 2 0 60 100").cmd("launch 2 0", starts=True).run_ticks(4).cmd("launch 2 5")
    r = s.snap("a").run_ticks(TPB).run(seq_tools, tmp_path)
    assert track(r.state("a"), 2)["active"] == 5 and track(r.state("a"), 2)["pending_stop"]
    assert track(r.end, 2)["playing"] is None


def mk(s, t, slot, length=16):
    """A clip of `length` steps in (t, slot), with no notes, leaving slot 0
    selected (Movy's tests set length_steps directly)."""
    return s.cmd(f"clipsel {t} {slot};loop {t} 0 {max(length, 16)};clen {t} {length};clipsel {t} 0")


def test_a_scene_launches_every_track_in_its_column(seq_tools, tmp_path):
    """engine.rs a_scene_launches_every_track_in_its_column (5298). Movy
    calls launch_scene; the UI's verb for it is `song`, which also starts a
    one-scene song. Track 9's stale playing slot comes from launch + stop."""
    s = S()
    mk(s, 0, 2)
    mk(s, 5, 2)
    mk(s, 9, 0)
    s.cmd("launch 9 0", starts=True).cmd("stop").cmd("song 2", starts=True).snap("a")
    a = s.run(seq_tools, tmp_path).state("a")
    assert a["playing"]
    assert track(a, 0)["playing"] == 2 and track(a, 5)["playing"] == 2
    assert track(a, 9)["playing"] is None and track(a, 9)["active"] == 2


def test_a_scene_launched_while_running_is_bar_quantized(seq_tools, tmp_path):
    """engine.rs a_scene_launched_while_running_is_bar_quantized (5321)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 0, 3)
    mk(s, 4, 0)
    a = s.play().cmd("song 3").snap("a").run(seq_tools, tmp_path).state("a")
    assert (track(a, 0)["queued"], track(a, 0)["playing"]) == (3, 0)
    assert track(a, 4)["pending_stop"]


def test_a_scene_lasts_as_long_as_its_longest_clip_rounded_up(seq_tools, tmp_path):
    """engine.rs a_scene_lasts_as_long_as_its_longest_clip_rounded_up_to_bars
    (5337), observed through a song: the 3-bar scene arms its successor on its
    third bar."""
    s = S()
    mk(s, 0, 0, 16)
    mk(s, 1, 0, 48)
    mk(s, 2, 0, 20)
    mk(s, 0, 1)
    s.cmd("song 0", starts=True).cmd("songadd 1").run_ticks(1).snap("b0").run_bars(1).snap("b1")
    s.run_bars(1).snap("b2").run_bars(1).snap("b3")
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("b1"), 0)["queued"] is None
    assert track(r.state("b2"), 0)["queued"] == 1
    assert track(r.state("b3"), 0)["playing"] == 1


def song2(s, a=16, b=16):
    mk(s, 0, 0, a)
    mk(s, 0, 1, b)
    return s.cmd("song 0", starts=True).cmd("songadd 1")


def test_a_song_arms_the_next_scene_one_bar_early_and_loops(seq_tools, tmp_path):
    """engine.rs a_song_arms_the_next_scene_exactly_one_bar_early_and_loops (5378)."""
    s = song2(S()).snap("start").run_ticks(1).snap("t1").run_bars(1).snap("b1").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert r.state("start")["playing"] and track(r.state("start"), 0)["playing"] == 0
    assert track(r.state("t1"), 0)["queued"] == 1
    b1 = r.state("b1")
    assert track(b1, 0)["playing"] == 1 and b1["song_pos"] == 1 and track(b1, 0)["queued"] == 0
    assert track(r.end, 0)["playing"] == 0 and r.end["song_pos"] == 0


def test_a_two_bar_scene_holds_for_two_bars(seq_tools, tmp_path):
    """engine.rs a_two_bar_scene_holds_for_two_bars (5413)."""
    s = song2(S(), a=32).run_ticks(1).snap("t1").run_bars(1).snap("b1").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("t1"), 0)["queued"] is None
    assert track(r.state("b1"), 0)["queued"] == 1
    assert track(r.end, 0)["playing"] == 1


def test_a_repeated_scene_plays_twice_as_long_without_retriggering(seq_tools, tmp_path):
    """engine.rs a_repeated_scene_plays_twice_as_long_without_retriggering (5429)
    and a_song_folds_repeated_presses_into_one_longer_entry (5359)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 0, 1)
    s.cmd("song 0", starts=True).cmd("songadd 0").cmd("songadd 1").snap("s").run_ticks(1).snap("t1")
    s.run_bars(1).snap("b1").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert r.state("s")["song"] == [0, 0, 1]
    assert track(r.state("t1"), 0)["queued"] is None
    assert track(r.state("b1"), 0)["queued"] == 1
    assert track(r.end, 0)["playing"] == 1


def test_a_one_entry_song_never_relaunches_itself(seq_tools, tmp_path):
    """engine.rs a_one_entry_song_never_relaunches_itself (5453)."""
    s = S()
    mk(s, 0, 0)
    r = s.cmd("song 0", starts=True).run_bars(3).run(seq_tools, tmp_path)
    assert track(r.end, 0)["queued"] is None and track(r.end, 0)["cycle"] > 1


def test_play_restarts_the_song_from_the_top(seq_tools, tmp_path):
    """engine.rs play_restarts_the_song_from_the_top (5469)."""
    s = song2(S()).run_ticks(1).run_bars(1).snap("a").cmd("stop").snap("b").play().snap("c")
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["song_pos"] == 1
    assert r.state("b")["song"] == [0, 1]
    assert r.state("c")["song_pos"] == 0 and track(r.state("c"), 0)["playing"] == 0


def test_launching_a_clip_by_hand_deletes_the_song(seq_tools, tmp_path):
    """engine.rs launching_a_clip_by_hand_deletes_the_song (5488) and
    song_add_before_any_song_does_nothing (5503)."""
    s = S().cmd("songadd 3").snap("x")
    s = song2(s).snap("a").cmd("launch 0 1").snap("b")
    r = s.run(seq_tools, tmp_path)
    assert r.state("x")["song"] == []
    assert r.state("a")["song"] == [0, 1]
    assert r.state("b")["song"] == [] and track(r.state("b"), 0)["playing"] == 0


def test_a_take_follows_the_song_into_the_next_scene(seq_tools, tmp_path):
    """engine.rs a_take_follows_the_song_into_the_next_scene (5530)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 0, 1)
    s.cmd("tog 0 0 60 100;clipsel 0 1;tog 0 0 62 100;clipsel 0 0")
    s.cmd("song 0", starts=True).cmd("songadd 1").run_ticks(1).cmd("rec 0").snap("a").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["recording"]
    e = r.end
    assert track(e, 0)["playing"] == 1 and track(e, 0)["active"] == 1 and e["recording"]


def test_arming_the_next_scene_does_not_move_the_edit_target_early(seq_tools, tmp_path):
    """engine.rs arming_the_next_scene_does_not_move_the_edit_target_early (5556)."""
    r = song2(S()).run_ticks(1).run(seq_tools, tmp_path)
    assert (track(r.end, 0)["queued"], track(r.end, 0)["active"]) == (1, 0)


def test_a_first_take_holds_its_track_against_the_song(seq_tools, tmp_path):
    """engine.rs a_first_take_holds_its_track_against_the_song_for_that_scene (5575)."""
    s = S()
    for t in (0, 1):
        mk(s, t, 0)
        mk(s, t, 1)
    s.cmd("song 0", starts=True).cmd("songadd 1").run_ticks(1).cmd("rec 0").run_bars(1)
    e = s.run(seq_tools, tmp_path).end
    assert track(e, 0)["playing"] == 0 and e["recording"] and track(e, 1)["playing"] == 1


def test_a_scene_moves_the_selection_even_on_the_tracks_it_stops(seq_tools, tmp_path):
    """engine.rs a_scene_moves_the_selection_even_on_the_tracks_it_stops (5604)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 1, 0)
    mk(s, 0, 2)
    s.play().cmd("song 2").snap("a").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("a"), 1)["active"] == 0
    e = r.end
    assert track(e, 0)["active"] == 2 and track(e, 1)["active"] == 2 and track(e, 1)["playing"] is None


def test_launching_a_clip_by_hand_outranks_a_scene(seq_tools, tmp_path):
    """engine.rs launching_a_clip_by_hand_outranks_a_scene_the_bar_has_not_reached (5631)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 1, 0)
    mk(s, 1, 5)
    e = s.play().cmd("song 2").cmd("launch 1 5").run_bars(1).run(seq_tools, tmp_path).end
    assert (track(e, 1)["active"], track(e, 1)["playing"]) == (5, 5)


def test_a_song_parks_on_an_empty_scene_and_can_be_left(seq_tools, tmp_path):
    """engine.rs a_song_parks_on_an_empty_scene_without_stopping_the_transport
    (5650) and a_song_that_ends_can_be_left_by_launching_a_clip (5673)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 0, 4)
    s.cmd("song 0", starts=True).cmd("songadd 1").run_ticks(1).run_bars(1).snap("a").run_bars(4)
    s.snap("b").cmd("launch 0 4").snap("c").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    a, b = r.state("a"), r.state("b")
    assert a["song_pos"] == 1 and track(a, 0)["playing"] is None
    assert b["song_pos"] == 1 and track(b, 0)["playing"] is None and track(b, 0)["queued"] is None
    assert b["playing"]
    assert r.state("c")["song"] == [] and track(r.end, 0)["playing"] == 4


def test_a_scene_added_after_a_bar_has_passed_is_not_skipped(seq_tools, tmp_path):
    """engine.rs a_scene_added_after_a_bar_has_passed_is_not_skipped (5691)."""
    s = S()
    for k in range(3):
        mk(s, 0, k)
    s.cmd("song 0", starts=True).run_ticks(1).run_bars(1).cmd("songadd 1").cmd("songadd 2")
    s.run_bars(1).snap("a").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("a"), 0)["playing"] == 1 and r.state("a")["song_pos"] == 1
    assert track(r.end, 0)["playing"] == 2


def test_a_scene_added_during_the_current_bar_falls_in_on_the_next_one(seq_tools, tmp_path):
    """engine.rs a_scene_added_during_the_current_bar_falls_in_on_the_very_next_one (5724)."""
    s = S()
    mk(s, 0, 0)
    mk(s, 0, 1)
    s.cmd("song 0", starts=True).run_ticks(1).snap("a").cmd("songadd 1").snap("b").run_bars(1)
    r = s.run(seq_tools, tmp_path)
    assert track(r.state("a"), 0)["playing"] == 0
    assert track(r.state("b"), 0)["queued"] == 1
    assert track(r.end, 0)["playing"] == 1


# ---- engine.rs: Capture ---------------------------------------------------------------------

def take(s, bpm, n):
    """engine.rs play_take (3994): n eighth notes at bpm, transport stopped.
    5-frame blocks, so the note frames are Movy's exactly at 100 and 120 BPM."""
    step = int(44100 * 60 / bpm / 2)
    assert step % s.block == 0
    for _ in range(n):
        s.cmd("non 0 60 100;nof 0 60")
        s.blocks(step // s.block)
    return s


def test_stopped_capture_sets_the_tempo_and_rolls(seq_tools, tmp_path):
    """engine.rs stopped_capture_sets_the_tempo_and_rolls (4047) and
    selecting_another_candidate_retimes_the_take (4061)."""
    s = take(S(tracks=1, block=5), 100.0, 16).cmd("cap 0").snap("a").cmd("capsel 2").snap("b")
    r = s.run(seq_tools, tmp_path)
    a, b = r.state("a"), r.state("b")
    assert a["bpm_x100"] == 10000 and a["playing"] and a["capture"]["mode"] == 1
    assert a["capture"]["cands"] == [50, 100, 200]
    assert all(n["suppress"] == 0 for n in notes(a, 0))
    assert b["bpm_x100"] == 20000
    assert len(notes(b, 0)) == len(notes(a, 0))
    assert clip(b, 0)["len"] > clip(a, 0)["len"]


def test_a_clip_with_notes_fits_rather_than_retempos(seq_tools, tmp_path):
    """engine.rs a_clip_with_notes_fits_rather_than_retempos (4095)."""
    s = take(S(tracks=1, block=5).cmd("tog 0 0 48 100"), 100.0, 16).cmd("cap 0")
    e = s.run(seq_tools, tmp_path).end
    assert e["bpm_x100"] == 12000 and e["capture"]["mode"] == 2
    assert any(n["pitch"] == 48 for n in notes(e, 0))


def test_the_selector_owns_the_take_until_it_is_dismissed(seq_tools, tmp_path):
    """engine.rs the_selector_owns_the_take_until_it_is_dismissed (4125)."""
    s = take(S(tracks=1, block=5), 100.0, 16).cmd("cap 0").cmd("non 0 72 100").snap("a")
    s.cmd("capdone").snap("b").cmd("non 0 72 100").snap("c")
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["capture"]["pending"] == 0
    assert r.state("b")["capture"]["mode"] == 0
    assert r.state("c")["capture"]["pending"] == 1


def test_capture_overdubs_at_the_position_it_was_heard(seq_tools, tmp_path):
    """engine.rs capture_overdubs_at_the_position_it_was_heard (4138)."""
    s = S(tracks=1).cmd("tog 0 4 60 100").play().run_ticks(6 * TPS).peek("p")
    s.cmd("non 0 67 100;nof 0 67").cmd("cap 0")
    r = s.run(seq_tools, tmp_path)
    at = track(r.state("p"), 0)["pos"]
    n = notes(r.end, 0)
    assert len(n) == 2 and n[-1]["pitch"] == 67 and abs(n[-1]["tick"] - at) <= TPS
    assert clip(r.end, 0)["len"] == 16


def test_capture_into_an_empty_playing_clip_grows_it_to_whole_bars(seq_tools, tmp_path):
    """engine.rs capture_into_an_empty_playing_clip_grows_it_to_whole_bars (4166)."""
    s = S(tracks=1).play()
    for _ in range(5):
        s.cmd("non 0 60 100;nof 0 60").run_ticks(TPB)
    length = clip(s.cmd("cap 0").run(seq_tools, tmp_path).end, 0)["len"]
    assert length % 16 == 0 and length > 16


def test_capture_consumes_the_buffer(seq_tools, tmp_path):
    """engine.rs capture_consumes_the_buffer (4182) and
    capture_consumes_the_buffer_even_when_it_writes_nothing (4193)."""
    s = S(tracks=1).play().cmd("non 0 60 100;nof 0 60").cmd("cap 0").snap("a").cmd("cap 0")
    s.cmd("nof 0 61").cmd("cap 0")
    r = s.run(seq_tools, tmp_path)
    assert r.state("a")["capture"]["pending"] == 0 and r.state("a")["capture"]["gen"] == 1
    assert r.end["capture"]["gen"] == 1, "nothing more was written"


def test_a_long_take_keeps_only_the_last_few_bars(seq_tools, tmp_path):
    """engine.rs a_long_take_keeps_only_the_last_few_bars (4023)."""
    s = take(S(tracks=1, block=5), 120.0, 240).cmd("cap 0")
    e = s.run(seq_tools, tmp_path).end
    bars = clip(e, 0)["len"] // 16
    assert 1 <= bars <= 8 + 1 and len(notes(e, 0)) < 128


# ---- persist.rs: movy1 (R14) ------------------------------------------------------------------

def roundtrip(tool, tmp_path, text, tracks=16, name="set"):
    import subprocess
    src = tmp_path / f"{name}.movy1"
    out = tmp_path / f"{name}.out.movy1"
    src.write_text(text)
    subprocess.run([str(tool), "--compat", "--tracks", str(tracks), "--seq", str(src),
                    "--export", str(out)], check=True, capture_output=True)
    return out.read_text()


def full_set(tracks=16, extra=None, head=("bpm 12000", "swing 50", "link 0")):
    extra = extra or {}
    out = ["movy1", *head]
    for t in range(tracks):
        out.append(f"tk {t} 0 0")
        out += extra.get(t, [])
    return "\n".join(out) + "\n"


def test_round_trips_state_and_clip_params(seq_tools, tmp_path):
    """persist.rs round_trips_state (414), round_trips_clip_quant (390),
    clip_params_round_trip_and_default (505), round_trips_automation (528),
    round_trips_trigs (544), swing_round_trips (575),
    pad_mutes_and_solo_round_trip (439), a_song_survives_a_save_and_load (631):
    byte-identical export of a set Movy's serializer would write."""
    text = full_set(head=("bpm 13000", "swing 72", "link 1", "sg 1 3 3"), extra={
        0: ["pm 0 36", "pm 0 38", "au 0 1 70 synth:cutoff",
            "cl 0 0 32 0 0:24:60:100:0;96:24:64:90:4;96:24:67:80:4",
            "cp 0 0 3 2 -5 70", "lk 0 0 1:3:55", "tg 0 0 2:-1:30:1:4:0;2:36:100:1:1:1"],
        1: [],
        2: ["cl 2 3 16 0 192:24:48:110:8", "cp 2 3 1 1 0 0"],
        3: ["ps 3 42"],
    })
    text = text.replace("tk 1 0 0", "tk 1 0 1").replace("tk 2 0 0", "tk 2 3 0")
    assert roundtrip(seq_tools, tmp_path, text) == text


def test_round_trips_the_swung_step_anchor(seq_tools, tmp_path):
    """persist.rs round_trips_the_swung_step_anchor (362): a stored anchor is
    kept, not re-derived from the tick."""
    text = full_set(head=("bpm 12000", "swing 70", "link 0"),
                    extra={0: ["cl 0 0 16 0 37:6:42:100:1", "cp 0 0 1 1 0 0"]})
    assert roundtrip(seq_tools, tmp_path, text) == text


def test_legacy_lines_load_with_defaults(seq_tools, tmp_path):
    """persist.rs legacy_notes_without_an_anchor_still_load (379),
    legacy_cp_line_loads_quant_zero (401), clip_params_round_trip_and_default
    (505), link_enabled_round_trips_and_defaults_off (585)."""
    out = roundtrip(seq_tools, tmp_path, "movy1\ncl 0 0 16 0 0:24:60:100;36:24:62:90\ncp 0 0 1 1 0\n"
                    "cl 1 0 16 0 \n")
    assert "cl 0 0 16 0 0:24:60:100:0;36:24:62:90:2\n" in out
    assert "cp 0 0 1 1 0 0\n" in out and "cp 1 0 1 1 0 0\n" in out
    assert "link 0\n" in out


def test_clip_lengths_are_preserved(seq_tools, tmp_path):
    """persist.rs clip_length_preserved_with_note_beyond_it (478) and
    sub_bar_clip_length_is_preserved (495)."""
    text = full_set(extra={1: ["cl 1 0 7 0 168:24:60:100:7", "cp 1 0 1 1 0 0"],
                           0: ["cl 0 0 12 0 ", "cp 0 0 1 1 0 0"]})
    assert roundtrip(seq_tools, tmp_path, text) == text


def test_selected_empty_slot_falls_back_to_a_real_clip_on_load(seq_tools, tmp_path):
    """persist.rs selected_empty_slot_falls_back_to_a_real_clip_on_load (601)
    and selected_empty_slot_kept_when_the_track_has_no_clips_at_all (621)."""
    out = roundtrip(seq_tools, tmp_path, "movy1\ntk 0 2 0\ncl 0 0 16 0 0:24:60:100\n"
                    "tk 1 3 0\ncl 1 1 16 0 0:24:62:100\ntk 2 4 0\n")
    assert "tk 0 0 0\n" in out and "tk 1 1 0\n" in out and "tk 2 4 0\n" in out


def test_rejects_unknown_format(seq_tools, tmp_path):
    """persist.rs rejects_unknown_format (559)."""
    import subprocess
    src = tmp_path / "bad.movy1"
    src.write_text("garbage\nbpm 9000\n")
    res = subprocess.run([str(seq_tools), "--seq", str(src)], capture_output=True, text=True)
    assert res.returncode != 0 and "not a movy1 set" in res.stderr


def test_no_pad_mute_or_song_lines_when_none_are_set(seq_tools, tmp_path):
    """persist.rs no_pad_mute_lines_when_none_are_set (460) and
    a_save_with_no_song_writes_no_line_and_clears_a_stale_one (648)."""
    out = roundtrip(seq_tools, tmp_path, "movy1\n")
    assert not [l for l in out.splitlines() if l.split()[0] in ("pm", "ps", "sg")]
