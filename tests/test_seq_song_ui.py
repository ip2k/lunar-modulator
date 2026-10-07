"""Session and the Song page on the virtual FM-1's panel (stage S9+;
notes/2026-10-06-song-and-scenes.md, every decision adopted: SG1-SG13 and
D15-D18 in the default mode). The golden traces session-* and song-* under
tests/fixtures/seq-ui/ replay byte for byte through fm1-render with the
other traces (tests/test_seq_ui.py); here, what they send and what the
panel shows: scenes under D16, the song built on the Song page and played
hands-free to its end, edits while it plays, the CLEAR confirm, the LEDs
of Session and the Song page, and the saved view (A1) opening both."""
import json

from tests.test_seq_ui import TRACES, WHITE, run, tools  # noqa: F401

SONG = TRACES / "song.verbs"
PLAY_LED = 27 + 12                     # the LED array: 27 keys, then the buttons (PLAY/STOP 12th)
LOOP, COPY, CLEAR = 3, 8, 10           # G#3, C#4, D#4


def go(tools, tmp_path, lines, *extra, seconds=None):  # noqa: F811
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(lines) + "\n")
    args = ["--engine", "test-sine", "--cmd", str(SONG), "--panel", str(panel), *extra]
    if seconds is not None:
        args += ["--seconds", str(seconds)]
    return run(tools["sim"], args)


def cmds(s):
    return [t for _, t in s["seq_ui_cmds"]]


def trace(tools, stem, seconds=None):  # noqa: F811
    args = ["--engine", "test-sine", "--cmd", str(SONG), "--panel", str(TRACES / f"{stem}.panel")]
    return run(tools["sim"], args + (["--seconds", str(seconds)] if seconds else []))


SESSION = ["--button 0.05:SEQ", "--button 0.10:SEQ"]     # SEQ, then SEQ tapped: Session
SONG_PAGE = ["--button 0.05:SEQ", "--button 0.10:SEL:0.1", f"--key 0.12:{LOOP}:100:0.05"]


def test_the_s9_traces_do_what_their_names_say(tools):  # noqa: F811
    assert cmds(trace(tools, "session-launch")) == ["launch 0 0", "launch 0 2", "watch 1", "launch 1 1",
                                                    "stop"]
    assert cmds(trace(tools, "session-scenes")) == ["scene 0", "sgnew 0", "songadd 1", "songadd 1",
                                                    "songadd 2", "scene 4", "stop", "play", "stop"]
    assert cmds(trace(tools, "session-copy-clear")) == ["clipcopy 0 0", "clippaste 0 7", "clipdelat 0 7",
                                                        "play"]
    assert cmds(trace(tools, "session-track-clear")) == ["clipdel 0", "play"]
    assert cmds(trace(tools, "song-edit-playing")) == [
        "sgins 0 0 1", "sgins 1 1 1", "sgset 1 1 2", "sgins 2 2 1", "sgmov 2 -1", "play", "sgdel 1",
        "sgset 1 3 2", "sgset 1 3 3", "sgjump 0", "sgclr", "stop"]
    built = cmds(trace(tools, "song-build"))
    assert built[-4:] == ["sgend 2", "sgname 6 10", "sgname 5 5", "play"]
    # A key on the cursor's own scene grows it (sgset), a new one inserts
    # after the cursor (sgins): never a join, so never a toast.
    assert sum(c.startswith("sgins") for c in built) == 10 and len(built) == 24


def test_the_song_built_on_the_page_is_the_worked_example_and_stops_by_itself(tools, tmp_path):  # noqa: F811
    """§9's ten entries and 20 presses, Stop at the end, scenes 6 and 7
    named; PLAY plays it hands-free (20 bars at 240 BPM) and the transport
    stops on the bar after the last entry."""
    doc_path = tmp_path / "song.lunar"
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(SONG), "--panel",
                           str(TRACES / "song-build.panel"), "--seconds", "3",
                           "--save-end", f"project:{doc_path}"])
    song = s["song"]
    assert (song["entries"], song["presses"], song["end"], song["follow"]) == (10, 20, 2, 1)
    lines = json.loads(doc_path.read_text())["set"]
    assert "sg 0 0 1 1 2 2 3 3 4 4 2 1 3 3 5 5 6 6 6 6" in lines and "se 2" in lines
    assert "sn 5 Drop" in lines and "sn 6 Outro" in lines
    mid = trace(tools, "song-build", seconds=13.6)
    assert mid["song"]["entry"] == 6 and mid["seq_view"]["view"] == 6 and mid["song"]["cur"] == 6
    end = trace(tools, "song-build")
    assert end["seq_view"]["playing"] == 0 and end["leds"][PLAY_LED] == "0"


def test_one_scene_detaches_the_song_and_stop_then_play_follows_it_again(tools):  # noqa: F811
    """D16 (SG1): LOOP + one scene launches it and keeps the list; STOP
    then PLAY follows the song from entry 1."""
    playing = trace(tools, "session-scenes", seconds=5.0)["song"]
    assert (playing["follow"], playing["entries"]) == (1, 3)
    detached = trace(tools, "session-scenes", seconds=7.0)["song"]
    assert (detached["follow"], detached["entries"], detached["presses"]) == (0, 3, 4)
    again = trace(tools, "session-scenes", seconds=9.0)["song"]
    assert (again["follow"], again["entry"]) == (1, 0)


def test_the_confirm_stays_until_a_press_and_the_press_does_nothing_else(tools, tmp_path):  # noqa: F811
    """SG9: a CLEAR tap in the Track view asks, the question stays through
    a knob turn and seconds of time, and PLAY only closes it: no `play`,
    no `clipdel`."""
    lines = ["--button 0.05:SEQ", f"--key 0.20:{CLEAR}:100:0.05", "--turn 1.00:KNOB1:3"]
    up = go(tools, tmp_path, lines, seconds=4)
    assert up["song"]["confirm"] == 1 and cmds(up) == []
    shut = go(tools, tmp_path, lines + ["--button 4.00:PLAY/STOP"], seconds=5)
    assert shut["song"]["confirm"] == 0 and cmds(shut) == [] and shut["seq_view"]["playing"] == 0
    # In Session, CLEAR + an empty slot asks nothing.
    empty = go(tools, tmp_path, SESSION + [f"--key 0.20:{CLEAR}:100:0.3", f"--key 0.25:{WHITE[7]}:100:0.05"],
               seconds=1)
    assert empty["song"]["confirm"] == 0


def bits(n):
    return {k + 1 for k in range(16) if (n >> k) & 1}


def test_sessions_leds_show_the_slots_the_tracks_and_the_scenes(tools, tmp_path):  # noqa: F811
    """White keys 1-8: track 1's slots (clips in 1-7); 9-16: the tracks,
    the focused one blinking slowly (off at 0.5 s into its second); LOOP
    held: the columns with a clip, then with a song the scenes it uses."""
    s = go(tools, tmp_path, SESSION, seconds=0.6)
    assert bits(s["seq_view"]["key_leds"]) == set(range(1, 8)) | set(range(10, 17))
    held = go(tools, tmp_path, SESSION + [f"--key 0.20:{LOOP}:100:2"], seconds=0.6)
    assert bits(held["seq_view"]["key_leds"]) == set(range(1, 8))
    song = go(tools, tmp_path, SESSION + [f"--key 0.20:{LOOP}:100:2", f"--key 0.30:{WHITE[0]}:100:0.05",
                                          f"--key 0.40:{WHITE[2]}:100:0.05"], seconds=0.6)
    assert song["song"]["loop_held"] == 1 and song["song"]["entries"] == 2
    assert bits(song["seq_view"]["key_leds"]) >= {1} and bits(song["seq_view"]["key_leds"]) <= {1, 3}


def test_the_song_pages_cursor_keys_and_leds(tools, tmp_path):  # noqa: F811
    """From `+ add`, keys 1, 2, 2 and 3 make [1, 2x2, 3] with the cursor on
    the last; the arrows move it without wrapping; keys 9-16 light the
    cursor's repeats; a CLEAR tap deletes the entry and says so."""
    build = [f"--key 0.20:{WHITE[0]}:100:0.02", f"--key 0.25:{WHITE[1]}:100:0.02",
             f"--key 0.30:{WHITE[1]}:100:0.02", f"--key 0.35:{WHITE[2]}:100:0.02"]
    s = go(tools, tmp_path, SONG_PAGE + build, seconds=0.6)
    assert (s["song"]["entries"], s["song"]["cur"], s["seq_view"]["view"]) == (3, 2, 6)
    assert bits(s["seq_view"]["key_leds"]) == set(range(1, 9)) | {9}
    up = go(tools, tmp_path, SONG_PAGE + build + ["--key 0.40:1:100:0.02"] * 1 +
            ["--key 0.45:1:100:0.02", "--key 0.50:1:100:0.02", "--key 0.55:1:100:0.02"], seconds=0.8)
    assert up["song"]["cur"] == 0
    assert bits(up["seq_view"]["key_leds"]) == set(range(1, 9)) | {9}
    two = go(tools, tmp_path, SONG_PAGE + build + ["--key 0.40:1:100:0.02"], seconds=0.6)
    assert two["song"]["cur"] == 1 and bits(two["seq_view"]["key_leds"]) == set(range(1, 9)) | {10}
    gone = go(tools, tmp_path, SONG_PAGE + build + ["--key 0.40:1:100:0.02", f"--key 0.50:{CLEAR}:100:0.05"],
              seconds=0.6)
    assert cmds(gone)[-1] == "sgdel 1" and gone["popup"] == ["Entry 2 deleted"]
    assert gone["song"]["entries"] == 2          # [1, 3]: no join


def test_a_join_says_so(tools, tmp_path):  # noqa: F811
    """[1, 2, 1]: KNOB1 turns entry 2 to scene 1, which joins all three."""
    build = [f"--key 0.20:{WHITE[0]}:100:0.02", f"--key 0.25:{WHITE[1]}:100:0.02",
             f"--key 0.30:{WHITE[0]}:100:0.02", "--key 0.35:1:100:0.02", "--turn 0.40:KNOB1:-1"]
    s = go(tools, tmp_path, SONG_PAGE + build, seconds=0.6)
    assert cmds(s)[-1] == "sgset 1 0 1"
    assert s["song"]["entries"] == 1 and s["song"]["cur"] == 0
    assert s["popup"] == ["Joined", "Scene 1 x3"]


def test_a_saved_view_opens_session_and_the_song_page(tools, tmp_path):  # noqa: F811
    """A1 knows the new pages: Session by its track, the Song page by its
    cursor's entry; loading the project opens them."""
    a, b = tmp_path / "a.lunar", tmp_path / "b.lunar"
    go(tools, tmp_path, SESSION, "--save-end", f"project:{a}", seconds=0.3)
    assert json.loads(a.read_text())["view"] == {"mode": "session", "track": 1}
    s = run(tools["sim"], ["--seconds", "0.1", "--load", str(a)])
    assert s["seq_view"]["view"] == 5
    build = [f"--key 0.20:{WHITE[0]}:100:0.02", f"--key 0.25:{WHITE[1]}:100:0.02", "--key 0.30:1:100:0.02"]
    go(tools, tmp_path, SONG_PAGE + build, "--save-end", f"project:{b}", seconds=0.5)
    assert json.loads(b.read_text())["view"] == {"mode": "song", "track": 1, "entry": 1}
    s = run(tools["sim"], ["--seconds", "0.1", "--load", str(b)])
    assert (s["seq_view"]["view"], s["song"]["cur"]) == (6, 0)
