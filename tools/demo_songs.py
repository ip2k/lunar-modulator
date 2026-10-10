#!/usr/bin/env python3
"""Generate the four original, full-length Lunar Modulator demo projects.

The project files are the source of truth in engines/state/examples; the web
copies and manifest are generated from the same deterministic arrangement data.
No samples or third-party musical material are used.
"""
from __future__ import annotations

import argparse
import copy
from itertools import product
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import state_canon  # noqa: E402

SOURCE = ROOT / "engines/state/examples"
WEB = ROOT / "sim/web/www/examples"
TEMPLATE = SOURCE / "first-orbit.lunar"
MANIFEST = ROOT / "sim/web/test/demo-songs.json"

SCALE_MINOR = (0, 2, 3, 5, 7, 8, 10, 12, 14, 15, 17, 19, 20, 22, 24)

SONGS = [
    {
        "slug": "afterglow-relay", "title": "Afterglow Relay", "name": "AFTERGLOW RELAY",
        "genre": "Chillwave", "bpm": 92, "root": "A", "midi_root": 57, "key_index": 9,
        "bars": 76, "swing": 56, "chords": [(57, "Am9"), (53, "Fmaj7"), (48, "Cmaj9"), (55, "G6")],
        "scenes": [("Intro", 4), ("Verse", 8), ("Lift", 4), ("Hook", 8),
                   ("Bridge", 8), ("Vrs2", 8), ("Hook2", 8), ("Outro", 4)],
        "chain": [0, 1, 1, 2, 3, 3, 4, 5, 6, 6, 7], "style": "chill",
        "motif": [(0, 0, 0, 6), (3, 2, 0, 4), (6, 4, 0, 6), (10, 3, 0, 4),
                  (12, 2, 0, 8), (14, 1, 0, 4)],
        "about": "A slow, hazy night drive: warm minor ninths, a patient bass pulse and a six-note hook that opens into the chorus. All parts are original MIDI patterns; no samples are used.",
        "sound": {"bass_model": "VA+Filter", "bass_cutoff": 680, "bass_decay": .43,
                  "chord_model": "VA Pair", "arp": False, "bass_timbre": .47, "lead_brightness": .53,
                  "echo_mix": .18, "hall": .68, "hall_size": .76,
                  "fx_color": "drive", "lead_fx": "echo"},
    },
    {
        "slug": "event-horizon", "title": "Event Horizon", "name": "EVENT HORIZON",
        "genre": "Future bass", "bpm": 144, "root": "F", "midi_root": 53, "key_index": 5,
        "bars": 116, "swing": 50, "chords": [(53, "Fm9"), (49, "Dbmaj7"), (56, "major"), (51, "major")],
        "scenes": [("Intro", 4), ("Verse", 8), ("Build", 4), ("Drop", 8),
                   ("Break", 4), ("Vrs2", 8), ("Drop2", 8), ("Outro", 4)],
        "chain": [0, 0, 1, 1, 2, 3, 3, 3, 3, 4, 5, 5, 6, 6, 6, 6, 7], "style": "future",
        "motif": [(0, 7, 0, 4), (3, 5, 0, 4), (6, 4, 0, 6), (8, 2, 0, 4),
                  (11, 4, 0, 4), (14, 1, 1, 6)],
        "about": "A half-time future-bass arc: a compact rising pickup, wide chord voicings and a four-pass drop whose kick and bass lock around the backbeat. All parts are original MIDI patterns; no samples are used.",
        "sound": {"bass_model": "VA+Filter", "bass_cutoff": 1100, "bass_decay": .3,
                  "chord_model": "VA Pair", "arp": False, "bass_timbre": .62, "lead_brightness": .68,
                  "echo_mix": .24, "hall": .57, "hall_size": .72,
                  "fx_color": "crush", "lead_fx": "echo"},
    },
    {
        "slug": "packet-bloom", "title": "Packet Bloom", "name": "PACKET BLOOM",
        "genre": "Vapor twitch", "bpm": 112, "root": "D", "midi_root": 50, "key_index": 2,
        "bars": 88, "swing": 59, "chords": [(50, "Dm9"), (46, "Bbmaj7"), (53, "Fmaj7"), (48, "Cadd9")],
        "scenes": [("Intro", 4), ("A-side", 8), ("Build", 4), ("Bloom", 8),
                   ("Glitch", 4), ("B-side", 8), ("Bloom2", 8), ("Outro", 4)],
        "chain": [0, 1, 1, 2, 3, 3, 3, 4, 5, 5, 6, 6, 7], "style": "vapor",
        "motif": [(0, 4, 1, 3), (2, 2, 0, 3), (5, 6, 0, 2), (7, 4, 0, 5),
                  (10, 3, 0, 2), (11, 1, 0, 3), (14, 2, 1, 4)],
        "about": "A soft-focus D-minor loop that keeps shedding a beat: off-grid-feeling accents, a descending answer and brief drum edits frame the returning bloom. All parts are original MIDI patterns; no samples are used.",
        "sound": {"bass_model": "VA+Filter", "bass_cutoff": 820, "bass_decay": .36,
                  "chord_model": "VA Pair", "arp": False, "bass_timbre": .52, "lead_brightness": .47,
                  "echo_mix": .31, "hall": .72, "hall_size": .81,
                  "fx_color": "drive", "lead_fx": "warble"},
    },
    {
        "slug": "neon-transit", "title": "Neon Transit", "name": "NEON TRANSIT",
        "genre": "Electropop", "bpm": 120, "root": "E", "midi_root": 52, "key_index": 4,
        "bars": 104, "swing": 50, "chords": [(52, "Em7"), (48, "Cmaj7"), (55, "major"), (50, "major")],
        "scenes": [("Intro", 4), ("Verse", 8), ("Pre", 4), ("Chorus", 8),
                   ("Bridge", 4), ("Vrs2", 8), ("Chor2", 8), ("Outro", 8)],
        "chain": [0, 0, 1, 1, 2, 3, 3, 3, 4, 5, 5, 6, 6, 6, 7], "style": "electro",
        "motif": [(0, 0, 0, 3), (2, 2, 0, 3), (4, 4, 0, 6), (8, 7, 0, 3),
                  (10, 6, 0, 3), (12, 4, 0, 6), (14, 2, 0, 3)],
        "about": "A bright, straight-ahead electropop ride: a singable seven-note instrumental refrain, clipped verse bass and a pre-chorus that opens into three chorus passes. All parts are original MIDI patterns; no samples are used.",
        "sound": {"bass_model": "VA+Filter", "bass_cutoff": 1250, "bass_decay": .28,
                  "chord_model": "VA Pair", "arp": False, "bass_timbre": .58, "lead_brightness": .72,
                  "echo_mix": .14, "hall": .48, "hall_size": .65,
                  "fx_color": "drive", "lead_fx": "echo"},
    },
]


def midi(degree: int, octave: int, root: int) -> int:
    return root + SCALE_MINOR[degree % len(SCALE_MINOR)] + 12 * octave


def ev(step: int, length: int, pitch: int, velocity: int) -> str:
    # The fifth cl field is a clip-local step index, not probability.
    return f"{step * 24}:{length}:{pitch}:{velocity}:{step}"


def scene_role(scene_index: int, scenes: list[tuple[str, int]]) -> str:
    name = scenes[scene_index][0].lower()
    if "intro" in name or "outro" in name:
        return "edge"
    if "build" in name or "lift" in name or name == "pre":
        return "build"
    if "hook" in name or "chor" in name or "drop" in name or "bloom" in name:
        return "peak"
    if "bridge" in name or "break" in name or "glitch" in name:
        return "contrast"
    return "verse"


def chord_for(song: dict, bar: int, scene: int = 1) -> tuple[int, str]:
    # Later sections change the harmonic starting point instead of restarting
    # every scene on bar one. The final four bars use a written cadence back to
    # the tonic, with the dominant penultimate bar exposed before the resolve.
    if scene == 7:
        cadence = (2, 1, 3, 0)
        if song["style"] == "electro":
            cadence = (2, 1, 2, 3, 1, 3, 3, 0)
        return song["chords"][cadence[bar % len(cadence)]]
    starts = {0: 0, 1: 0, 2: 1, 3: 0, 4: 2, 5: 2, 6: 1}
    return song["chords"][(starts.get(scene, 0) + bar) % 4]


def chord_quality(label: str) -> str:
    lower = label.lower()
    for suffix in ("maj9", "maj7", "add9", "m9", "m7", "6"):
        if lower.endswith(suffix):
            return suffix
    return "major"


def nearest_voicing(song: dict, bar: int, scene: int, tones: list[int]) -> list[int]:
    """Move an equal-size chord stack by nearest voice rather than parallel blocks."""
    if bar == 0:
        return tones
    previous_root, previous_label = chord_for(song, bar - 1, scene)
    intervals = {
        "m9": (0, 3, 7, 10, 14), "maj7": (0, 4, 7, 11),
        "maj9": (0, 4, 7, 11, 14), "6": (0, 4, 7, 9),
        "major": (0, 4, 7), "add9": (0, 4, 7, 14), "m7": (0, 3, 7, 10),
    }
    previous = sorted(previous_root + 12 + semitone
                      for semitone in intervals[chord_quality(previous_label)])
    if len(previous) != len(tones):
        return tones
    choices = [tuple(pitch + octave * 12 for octave in (-1, 0, 1)) for pitch in tones]
    best: tuple[int, tuple[int, ...]] | None = None
    for candidate in product(*choices):
        ordered = tuple(sorted(candidate))
        if len(set(ordered)) != len(ordered):
            continue
        cost = sum(abs(ordered[i] - previous[i]) for i in range(len(ordered)))
        option = (cost, ordered)
        if best is None or option < best:
            best = option
    return list(best[1]) if best else tones


def drum_bar(style: str, role: str, bar: int, scene: int) -> tuple[list[str], list[str], list[str]]:
    kick: list[str] = []
    hats: list[str] = []
    perc: list[str] = []
    if style == "chill":
        kick_steps = [0, 8] if role != "contrast" else [0]
        snare_steps = [4, 12] if role in ("peak", "verse") else [12]
        hat_steps = [2, 6, 10, 14] if role != "edge" else [6, 14]
    elif style == "future":
        kick_steps = [0, 6, 10] if role in ("peak", "build") else [0, 8]
        snare_steps = [8] if role != "edge" else [12]
        hat_steps = list(range(0, 16, 2)) if role == "peak" else [2, 6, 10, 14]
    elif style == "vapor":
        kick_steps = [0, 5, 10] if role in ("peak", "verse") else [0, 10]
        snare_steps = [4, 12] if role != "edge" else [12]
        hat_steps = [1, 4, 7, 10, 13, 15] if role == "peak" else [2, 6, 10, 14]
    else:
        kick_steps = [0, 4, 8, 12] if role in ("peak", "verse") else [0, 8]
        snare_steps = [4, 12] if role != "edge" else [12]
        hat_steps = [2, 6, 10, 14] if role != "edge" else [6, 14]
    # A bridge is a real subtraction. Leave one sparse marker in the middle
    # rather than retaining the verse kick grid under a different label.
    if role == "contrast":
        if style == "chill":
            kick_steps = [] if bar < 4 else [8]
            snare_steps = [12] if bar in (3, 7) else []
            hat_steps = [6, 14] if bar in (1, 5) else []
        elif style == "electro":
            kick_steps = []
            snare_steps = [12] if bar == 2 else []
            hat_steps = [6, 14] if bar in (1, 3) else []
        elif style == "vapor":
            kick_steps = [10] if bar in (0, 3) else []
            snare_steps = [15] if bar == 2 else []
            hat_steps = [1, 13] if bar in (1, 3) else []
        else:
            kick_steps = []
            snare_steps = [8] if bar == 2 else []
            hat_steps = [2, 14] if bar in (1, 3) else []
    if scene == 7 and style == "electro":
        kick_steps = ([0] if bar == 0 else [8] if bar == 1 else
                      [0] if bar == 2 else [8] if bar == 3 else [])
        snare_steps = [12] if bar in (1, 3) else []
        hat_steps = ([6, 14] if bar in (0, 2) else [14] if bar == 1 else
                     [6] if bar == 3 else [])
    elif scene == 7:
        # Four-bar outro: remove the pulse in two stages and reserve the
        # final bar for the cadence rather than the verse drum pattern.
        kick_steps = ([0] if bar == 0 else [8] if bar == 1 else [])
        snare_steps = ([12] if bar == 1 else [])
        hat_steps = ([6, 14] if bar == 0 else [14] if bar == 1 else [])
    # Builds tighten the subdivision, then clear the final eighth before the
    # next scene arrives.
    if role == "build" and style in ("future", "electro"):
        if bar >= 2:
            hat_steps = list(range(0, 16, 2))
        if bar == 3:
            kick_steps = [0, 6, 10]
    for i, step in enumerate(kick_steps):
        kick.append(ev(step, 7, 36, 112 if i == 0 else 94))
    for step in snare_steps:
        kick.append(ev(step, 7, 38, 101 if step == 12 else 92))
    if role in ("peak", "build") and bar % 4 == 3:
        kick.extend([ev(14, 5, 38, 65), ev(15, 4, 42, 70)])
    for i, step in enumerate(hat_steps):
        hats.append(ev(step, 4, 42, 72 if i % 2 == 0 else 53))
    if style == "vapor" and role in ("peak", "contrast") and bar % 2 == 1:
        perc.extend([ev(3, 4, 46, 66), ev(11, 4, 46, 61)])
    elif role == "peak" and bar % 4 == 3:
        perc.extend([ev(7, 5, 39, 75), ev(15, 4, 46, 73)])
    elif role == "edge" and bar == 0:
        perc.append(ev(14, 4, 46, 48))
    return kick, hats, perc


def bass_bar(song: dict, role: str, bar: int, scene: int = 1) -> list[str]:
    root, label = chord_for(song, bar, scene)
    quality = chord_quality(label)
    third = 3 if quality in ("m9", "m7") else 4
    style = song["style"]
    if style == "chill":
        steps = [(0, 0, 72, 92), (6, third, 5, 64), (8, 0, 72, 86), (14, 7, 5, 62)]
        if role in ("edge", "contrast"):
            steps = [(0, 0, 12, 83), (8, 7, 8, 65)]
    elif style == "future":
        steps = [(0, 0, 72, 104), (3, 0, 5, 72), (8, 7, 72, 92), (11, third, 5, 77), (14, 7, 5, 72)]
        if role in ("edge", "contrast"):
            steps = [(0, 0, 12, 82), (10, third, 8, 60)]
    elif style == "vapor":
        steps = [(0, 0, 72, 84), (5, 7, 5, 65), (9, third, 6, 72), (13, 7, 4, 59)]
        if role in ("edge", "contrast"):
            steps = [(0, 0, 10, 76), (10, 7, 6, 55)]
    else:
        steps = [(0, 0, 72, 98), (4, third, 5, 77), (8, 7, 72, 91), (12, third, 5, 79)]
        if role in ("edge", "contrast"):
            steps = [(0, 0, 10, 82), (8, 7, 8, 63)]
    # Keep the bass one octave below the project tonic used by the melody and
    # chord generator. Selected roots sustain a phrase foundation; pickups
    # remain short. Gate values are raw Movy ticks, not sixteenth steps.
    if scene == 5:
        # Second verse/B-side answers the chord root with a fifth, then leaves
        # a longer root at bar boundaries. Its rhythm is distinct without
        # adding chromatic pitches outside the written harmony.
        if style == "chill":
            steps = [(0, 0, 96, 88), (5, 7, 6, 58), (10, third, 48, 66)]
        elif style == "future":
            steps = [(0, 0, 84, 98), (4, 7, 6, 65), (9, third, 48, 70), (13, 7, 5, 64)]
        elif style == "vapor":
            steps = [(0, 0, 84, 82), (6, 7, 5, 63), (11, third, 48, 67)]
        else:
            steps = [(0, 0, 84, 92), (4, 7, 6, 70), (10, third, 48, 74)]
    elif scene == 6:
        steps = [(s, i, d, min(118, v + (8 if bar % 4 == 3 else 0)))
                 for s, i, d, v in steps]
    elif scene == 7 and style == "electro":
        steps = ([(0, 0, 72, 74), (8, 7, 40, 46)] if bar < 2 else
                 [(0, 0, 72, 65), (8, 4, 36, 48)] if bar < 4 else
                 [(0, 0, 96, 60), (8, 7, 36, 44)] if bar < 7 else
                 [(8, 0, 192, 56)])
    elif scene == 7:
        steps = ([(0, 0, 72, 74), (8, 7, 40, 46)] if bar < 2 else
                 [(0, 0, 120, 62)] if bar == 2 else [(0, 0, 144, 54)])
    return [ev(step, dur, root - 12 + interval, vel) for step, interval, dur, vel in steps]


def chord_bar(song: dict, role: str, bar: int, scene: int) -> tuple[list[str], list[str]]:
    root, label = chord_for(song, bar, scene)
    quality = chord_quality(label)
    style = song["style"]
    # Wide, stable voicings leave room for the bass. Repeated stabs are
    # deliberately different by style; only sound slots with an enabled arp
    # transform their simultaneous chord events.
    intervals = {
        "m9": (0, 3, 7, 10, 14), "maj7": (0, 4, 7, 11),
        "maj9": (0, 4, 7, 11, 14), "6": (0, 4, 7, 9),
        "major": (0, 4, 7),
        "add9": (0, 4, 7, 14), "m7": (0, 3, 7, 10),
    }
    chord_intervals = intervals[quality.lower()]
    if style == "future" and quality == "major":
        # The two major-drop chords carry a ninth above the octave as a fourth
        # voice, keeping their swell width consistent with the minor-ninth
        # shapes without turning the arp back on.
        chord_intervals = (0, 4, 7, 14)
    # Second peaks turn the original triad/pad upward rather than merely
    # repeating the first peak's root-position block.
    if scene == 6 and len(chord_intervals) >= 4:
        chord_intervals = chord_intervals[1:] + (chord_intervals[0] + 12,)
    tones = [root + 12 + semitones for semitones in chord_intervals]
    if style == "chill":
        tones = nearest_voicing(song, bar, scene, tones)
    if role == "peak":
        # Future bass keeps all chord tones together for a two-beat swell;
        # the chord-slot arpeggiator is disabled so the voicing stays wide.
        dur = 192 if style == "future" else 84 if style == "electro" else 64
        stab_steps = [0, 8] if style in ("future", "electro") else [0]
        velocity = 72 if style == "chill" else 89
    elif role == "build":
        dur, stab_steps, velocity = 64, [0, 12], 78
    elif role == "edge":
        dur, stab_steps, velocity = 110, [0], 61
    elif role == "contrast":
        dur, stab_steps, velocity = 78, [0, 10], 67
    else:
        dur, stab_steps, velocity = 52, ([0, 8] if style == "electro" else [0]), 72
    if scene == 7 and style == "electro":
        dur, stab_steps, velocity = (192 if bar < 7 else 384), [0], 56
    if scene == 6:
        # A later peak adds a held upper answer; fewer repeated root attacks
        # leave room for the newly inverted top voices.
        stab_steps = [0, 8] if style in ("future", "electro") else [0, 10]
    chords = [ev(step, dur, pitch, velocity) for step in stab_steps for pitch in tones]
    # The second chord slot adds a quiet upper response only in active
    # sections, avoiding a constant fifth/lead doubling.
    answer: list[str] = []
    if role in ("peak", "build"):
        step = 12 if style != "vapor" else 11
        answer = [ev(step, 28, tones[2], 58), ev(step + 2, 24, tones[-1], 54)]
    elif role == "verse" and bar % 2 == 1:
        answer = [ev(14, 20, root + 19, 45)]
    if scene == 6 and bar % 4 == 3:
        answer.extend([ev(10, 30, tones[-1] + 12, 62), ev(14, 54, tones[-2] + 12, 67)])
    return chords, answer


def lead_bar(song: dict, role: str, bar: int, scene: int, track: int) -> list[str]:
    root = song["midi_root"]
    motif = song["motif"]
    # Track 7 answers the lead by lifting selected motif notes a fifth and
    # arriving later; it never copies the complete hook.
    if track == 7:
        # Answer at the lead's rests with a fifth above the written phrase;
        # second sections invert the reply and move it later in the bar.
        if scene == 7:
            if song["style"] == "electro":
                return []
            return [ev(12, 24, midi(2, 0, root) + 7, 40)] if bar == 1 else []
        if scene == 0:
            return []
        if role not in ("peak", "build"):
            note = motif[-1] if scene == 5 else motif[2]
            step = 13 if scene == 5 else 14
            return [ev(step, 30 if bar % 2 else 18,
                       midi(note[1], note[2], root) + 7, 48)] if bar % 2 else []
        main = [tuple(map(int, item.split(":")))
                for item in lead_bar(song, role, bar, scene, 3)]
        preferred = {
            "chill": (5, 13, 1, 9, 6, 14),
            "future": (5, 13, 1, 9, 6, 14),
            "vapor": (6, 14, 1, 9, 5, 13),
            "electro": (6, 14, 1, 9, 5, 13),
        }[song["style"]]
        windows = []
        for step in preferred:
            start = step * 24
            if all(start + 24 <= tick or start >= tick + length
                   for tick, length, *_ in main):
                windows.append(step)
            if len(windows) == 2:
                break
        if not windows:
            return []
        source = main[-1][2] if main else midi(2, 0, root)
        pitches = (source + 7, source + (12 if scene == 6 else 7))
        return [ev(step, 24, pitches[i], 45 if scene == 6 else 48)
                for i, step in enumerate(windows)]

    if scene == 0 and track == 3:
        # Stage each opening over four bars: silence, a distant answer, a
        # two-note identity, then a compact pickup into the first full section.
        first, second, fifth = motif[0], motif[1], motif[-1]
        if bar == 0:
            return []
        if bar == 1:
            return [ev(8, 18, midi(first[1], first[2] + 1, root), 43)]
        if bar == 2:
            return [ev(0, 24, midi(second[1], second[2], root), 49),
                    ev(12, 18, midi(first[1], first[2] + 1, root), 42)]
        pickup = 10 if song["style"] == "vapor" else 12
        return [ev(4, 18, midi(fifth[1], fifth[2], root), 47),
                ev(pickup, 24, midi(first[1], first[2] + 1, root), 52)]
    if role == "edge":
        selected = motif[:2] if scene % 2 == 0 else motif[-2:]
    elif role == "contrast":
        selected = motif[2:5:2]
    elif role == "verse":
        selected = motif[1:5:2] if scene == 5 else motif[:4:2]
    elif role == "build":
        selected = motif[1:5]
    else:
        selected = motif
    if scene == 5:
        # Reverse pitch/rhythm payload over ascending onset slots. Keeping the
        # old onset attached would be undone when serialized by chronological tick.
        reversed_payload = list(reversed(selected))
        selected = [(selected[i][0], *reversed_payload[i][1:])
                    for i in range(len(selected))]
    out = []
    if scene == 7 and song["style"] == "electro":
        # One directional eight-bar exit; its final four bars thin to a single
        # low tonic instead of restarting the completed cadence.
        if bar < 4:
            if bar == 3:
                return [ev(8, 48, midi(2, 1, root), 54)]
            return [ev(0, 24, midi((bar + 2) % 7, 1, root), 48)] if bar in (0, 2) else []
        if bar == 4:
            return [ev(0, 48, midi(4, 1, root), 49)]
        if bar == 5:
            return [ev(8, 36, midi(2, 1, root), 44)]
        if bar == 6:
            return [ev(12, 24, midi(1, 1, root), 38)]
        return [ev(8, 192, root, 42)]
    if scene == 7:
        if bar == 3:
            return [ev(8, 96, root, 55)]
        if bar >= 2:
            return []
    for i, (step, degree, octave, length) in enumerate(selected):
        # Every other pass gets a small pickup variation, while the hook's
        # recognizable first and last tones stay anchored.
        shift = 1 if bar % 4 == 3 and i not in (0, len(selected) - 1) else 0
        pitch = midi(degree + shift, octave + 1, root)
        if scene == 6 and role == "peak" and i >= len(selected) // 2:
            # Keep the second-half answer a real fourth above the phrase, not
            # a scale-degree wrap that can drop an upper note by an octave.
            pitch += 5
        vel = 85 if role == "peak" else 70 if role == "build" else 59
        gate = length * 3 if role in ("peak", "build") else length * 2
        if scene == 7 and i == len(selected) - 1:
            gate = 72
            pitch = root
        elif role in ("peak", "build") and bar % 4 == 3 and i == len(selected) - 1:
            # Let each four-bar phrase land on the barline instead of clipping
            # every final motif tone to a sixteenth-note pickup.
            gate = max(gate, 48)
        out.append(ev(step, gate, pitch, vel))
    return out


def offset_event(event: str, tick_offset: int) -> str:
    fields = event.split(":")
    tick = int(fields[0]) + tick_offset
    fields[0] = str(tick)
    fields[4] = str(tick // 24)
    return ":".join(fields)


def lock_curve(song: dict, scene_index: int, parameter: str, bar: int = 0) -> tuple[int, list[int]]:
    role = scene_role(scene_index, song["scenes"])
    bases = {"edge": 34, "verse": 48, "build": 73, "peak": 91, "contrast": 58}
    offsets = {"Timbre": 4 if song["style"] in ("future", "electro") else -3,
               "Brightness": 8 if song["style"] in ("future", "electro") else -7}
    base = max(0, min(127, bases[role] + offsets[parameter]))
    if role == "build":
        # Each style gets its own four-bar movement; the last bar drops below
        # the opening level so the withheld attacks have a matching pullback.
        curves = {
            "chill": (0, 5, 13, -19),
            "future": (0, 11, 22, -16),
            "vapor": (0, 4, 15, -22),
            "electro": (0, 8, 18, -20),
        }
        base = max(0, min(120, base + curves[song["style"]][min(bar, 3)]))
    elif role == "peak" and scene_index == 6 and bar >= 4:
        lifts = {"chill": 5, "future": 9, "vapor": 7, "electro": 11}
        base = min(120, base + lifts[song["style"]])
    elif role == "contrast":
        base = max(8, base - (12 if bar < 4 else 4))
    return base, [max(0, min(127, base - 5)), base, min(127, base + 10), base]


def arrangement(song: dict) -> list[str]:
    lines = ["movy1", f"bpm {song['bpm'] * 100}", f"swing {song['swing']}", "link 0",
             f"key {song['key_index']} 1", "sg " + " ".join(map(str, song["chain"])), "se 2"]
    for i, (name, _) in enumerate(song["scenes"]):
        lines.append(f"sn {i} {name}")
    for track in range(8):
        active = 0
        lines.append(f"tk {track} {active} 0")
    bass_base = round(song["sound"]["bass_timbre"] * 127)
    lead_base = round(song["sound"]["lead_brightness"] * 127)
    lines.extend([f"au 1 0 {bass_base} synth:Timbre",
                  f"au 3 0 {lead_base} synth:Brightness"])
    # Three fixed drum roles, four pitched roles and one upper response all
    # route through the project's four sound slots.
    for track, slot in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 0), (5, 2), (6, 0), (7, 3)]:
        lines.append(f"rt {track} 1 {slot}")
    for scene_index, (scene_name, bars) in enumerate(song["scenes"]):
        role = scene_role(scene_index, song["scenes"])
        steps = bars * 16
        all_events: dict[int, list[str]] = {t: [] for t in range(8)}
        for bar in range(bars):
            kicks, hats, perc = drum_bar(song["style"], role, bar, scene_index)
            base = bar * 16
            for evstr in kicks:
                all_events[0].append(offset_event(evstr, base * 24))
            for evstr in hats:
                all_events[4].append(offset_event(evstr, base * 24))
            for evstr in perc:
                all_events[6].append(offset_event(evstr, base * 24))
            for event in bass_bar(song, role, bar, scene_index):
                all_events[1].append(offset_event(event, base * 24))
            chords, answer = chord_bar(song, role, bar, scene_index)
            for event in chords:
                all_events[2].append(offset_event(event, base * 24))
            for event in answer:
                all_events[5].append(offset_event(event, base * 24))
            for event in lead_bar(song, role, bar, scene_index, 3):
                all_events[3].append(offset_event(event, base * 24))
            for event in lead_bar(song, role, bar, scene_index, 7):
                all_events[7].append(offset_event(event, base * 24))
            # Leave the final half-beat empty at the end of a build, making
            # the next section's downbeat an actual arrival.
            if role == "build" and bar == bars - 1:
                for track in range(8):
                    cutoff = base * 24 + (288 if track == 2 else 336)
                    kept = []
                    for event in all_events[track]:
                        fields = event.split(":")
                        tick, length = int(fields[0]), int(fields[1])
                        if tick >= cutoff:
                            continue
                        fields[1] = str(min(length, cutoff - tick))
                        kept.append(":".join(fields))
                    all_events[track] = kept
        for track in range(8):
            events = ";".join(sorted(all_events[track], key=lambda item: int(item.split(":", 1)[0])))
            lines.append(f"cl {track} {scene_index} {steps} 0 {events}")
            lines.append(f"cp {track} {scene_index} 1 1 0 0")
            if track in (1, 3):
                parameter = "Timbre" if track == 1 else "Brightness"
                locks = ";".join(
                    f"0:{bar_index * 16 + step}:{value}"
                    for bar_index in range(bars)
                    for step, value in zip(
                        (0, 4, 8, 12),
                        lock_curve(song, scene_index, parameter, bar_index)[1],
                    )
                )
                lines.append(f"lk {track} {scene_index} {locks}")
    return lines


def build(song: dict) -> dict:
    doc = copy.deepcopy(state_canon.loads(TEMPLATE.read_text(encoding="utf-8")))
    doc["name"] = song["name"]
    doc["title"] = song["title"]
    doc["about"] = song["about"]
    # Project JSON stores the selected sound slot as 1..4 (the reader maps it
    # to an internal zero-based index). Keep the template's valid slot 2.
    doc["session"]["current"] = 2
    doc["session"]["key"] = {"root": song["root"], "scale": "minor"}
    sounds = doc["sounds"]
    sounds[0]["params"]["Kit"] = "Punch"
    sounds[0]["params"]["Accent"] = .56 if song["style"] == "vapor" else .68
    sounds[0]["params"]["Kit Decay"] = .42
    sounds[1]["params"]["Model"] = song["sound"]["bass_model"]
    sounds[1]["params"]["Timbre"] = song["sound"]["bass_timbre"]
    sounds[1]["params"]["Decay"] = song["sound"]["bass_decay"]
    sounds[1]["inserts"][0]["params"]["Cutoff"] = song["sound"]["bass_cutoff"]
    if song["sound"]["fx_color"] == "crush":
        sounds[1]["inserts"][1] = {"engine": "crush", "params": {
            "Bits": 11, "Rate": .48, "Jitter": .06, "Mix": .22,
            "Tone": .72, "Level": 1,
        }}
    sounds[2]["params"]["Model"] = song["sound"]["chord_model"]
    sounds[2]["params"]["Timbre"] = .38 if song["style"] == "chill" else .54
    sounds[2]["params"]["Decay"] = .52 if song["style"] in ("future", "electro") else .68
    sounds[2]["midi_fx"][0]["on"] = song["sound"]["arp"]
    sounds[2]["midi_fx"][0]["params"]["Rate"] = "1/8" if song["style"] == "future" else "1/16"
    # The Future bass chord slot stays un-arpeggiated so each full voicing
    # swells together; the stored Gate is inert while the effect is off.
    sounds[2]["midi_fx"][0]["params"]["Gate"] = 52
    sounds[3]["params"]["Brightness"] = song["sound"]["lead_brightness"]
    sounds[3]["params"]["Env Time"] = .62 if song["style"] == "chill" else .42
    if song["sound"]["lead_fx"] == "warble":
        sounds[3]["inserts"][0] = {"engine": "warble", "params": {
            "Wow": .58, "Flutter": .34, "Mix": .24,
        }}
    else:
        sounds[3]["inserts"][0]["params"]["Mix"] = song["sound"]["echo_mix"]
    doc["master"][0]["params"]["Decay"] = song["sound"]["hall"]
    doc["master"][0]["params"]["Size"] = song["sound"]["hall_size"]
    doc["set"] = arrangement(song)
    return doc


def outputs() -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    manifest = []
    for song in SONGS:
        name = song["slug"] + ".lunar"
        raw = state_canon.dumps(build(song)).encode("utf-8")
        files[SOURCE / name] = raw
        files[WEB / name] = raw
        manifest.append({
            "file": "../../../engines/state/examples/" + name,
            "title": song["title"], "bpm": song["bpm"], "bars": song["bars"], "scenes": 8,
        })
    files[MANIFEST] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return files


def check(files: dict[Path, bytes]) -> list[str]:
    errors = []
    # Keep sparse future-bass edge bars in the same chord quality as the
    # main pattern. Fm9 must use Ab, not the natural A from a fixed +4.
    future = next(song for song in SONGS if song["style"] == "future")
    future_edge = bass_bar(future, "edge", 0, 0)
    if future_edge != [ev(0, 12, future["chords"][0][0] - 12, 82),
                       ev(10, 8, future["chords"][0][0] - 9, 60)]:
        errors.append("future-bass edge third does not match its minor chord quality")
    future_doc = build(future)
    if future_doc["sounds"][2]["midi_fx"][0]["on"]:
        errors.append("future-bass chord slot must keep its arp off for simultaneous swells")
    for song in SONGS:
        generated = arrangement(song)
        clips = {}
        for line in generated:
            fields = line.split()
            if fields[0] == "cl":
                clips[(int(fields[1]), int(fields[2]))] = fields[5] if len(fields) > 5 else ""
        if tuple(clips.get((track, 1)) for track in range(8)) == tuple(
                clips.get((track, 5)) for track in range(8)):
            errors.append(f"{song['title']}: second verse/side exactly copies the first")
        if tuple(clips.get((track, 3)) for track in range(8)) == tuple(
                clips.get((track, 6)) for track in range(8)):
            errors.append(f"{song['title']}: final peak exactly copies the first peak")
        verse_slots = song["motif"][1:5:2]
        expected_reverse = [
            ev(verse_slots[i][0], verse_slots[-1 - i][3] * 2,
               midi(verse_slots[-1 - i][1], verse_slots[-1 - i][2] + 1,
                    song["midi_root"]), 59)
            for i in range(len(verse_slots))
        ]
        if lead_bar(song, "verse", 0, 5, 3) != expected_reverse:
            errors.append(f"{song['title']}: second verse does not remap reversed payload to ascending onsets")
        later_peak = [tuple(map(int, event.split(":")))
                      for event in lead_bar(song, "peak", 0, 6, 3)]
        selected = song["motif"]
        expected_later = [
            midi(degree, octave + 1, song["midi_root"]) + (5 if i >= len(selected) // 2 else 0)
            for i, (_, degree, octave, _) in enumerate(selected)
        ]
        if [event[2] for event in later_peak] != expected_later:
            errors.append(f"{song['title']}: later peak must lift the second phrase without scale wrap")
        if song["style"] == "future":
            peak_chords = [e for e in clips[(2, 3)].split(";") if e]
            events = [list(map(int, e.split(":"))) for e in peak_chords]
            for bar in range(8):
                local = [e for e in events if bar * 384 <= e[0] < (bar + 1) * 384]
                _, chord_label = chord_for(song, bar, 3)
                expected_tones = {"m9": 5, "maj7": 4, "maj9": 5, "6": 4,
                                  "major": 4, "add9": 4, "m7": 4}
                expected_tones = expected_tones[chord_quality(chord_label)]
                for step in (0, 8):
                    onset = bar * 384 + step * 24
                    stack = [e for e in local if e[0] == onset]
                    if len(stack) != expected_tones or any(e[1] != 192 for e in stack):
                        errors.append("future-bass peak must hold its full simultaneous voicing for two beats")
                        break
        if song["style"] == "electro":
            if song["scenes"][7][1] != 8 or song["chain"].count(7) != 1:
                errors.append("Neon Transit outro must be one continuous eight-bar exit")
            outro_kicks = [tuple(map(int, event.split(":")))
                           for event in clips[(0, 7)].split(";") if event]
            if any(event[0] >= 4 * 384 for event in outro_kicks):
                errors.append("Neon Transit outro drums must withdraw for its final four bars")
        for scene in (3, 6):
            main = [list(map(int, e.split(":"))) for e in clips[(3, scene)].split(";") if e]
            answer = [list(map(int, e.split(":"))) for e in clips[(7, scene)].split(";") if e]
            if any(max(a[0], b[0]) < min(a[0] + a[1], b[0] + b[1])
                   for a in main for b in answer):
                errors.append(f"{song['title']}: scene {scene} lead and answer overlap")
        for peak_scene in (3, 6):
            lead = [event for event in clips[(3, peak_scene)].split(";") if event]
            phrase_end_tick = 3 * 16 * 24 + 14 * 24
            ending = [event for event in lead if int(event.split(":")[0]) == phrase_end_tick]
            if not ending or int(ending[-1].split(":")[1]) < 48:
                errors.append(f"{song['title']}: peak phrases need a held barline landing")
        build_locks = {}
        for line in generated:
            fields = line.split()
            if fields[0] == "lk" and fields[2] == "2":
                track = int(fields[1])
                bars = build_locks.setdefault(track, [])
                values = [int(item.split(":")[2]) for item in fields[3].split(";")]
                bars.extend(tuple(values[i:i + 4]) for i in range(0, len(values), 4))
        for track in (1, 3):
            if len(build_locks.get(track, [])) != 4 or len(set(build_locks[track])) != 4:
                errors.append(f"{song['title']}: build locks do not evolve across all four bars")
        build_scene = 2
        build_bars = song["scenes"][build_scene][1]
        last_bar_tick = (build_bars - 1) * 16 * 24
        build_clips = [line.split() for line in generated
                       if line.startswith("cl ") and line.split()[2] == str(build_scene)]
        if build_bars != 4:
            errors.append(f"{song['title']}: expected a four-bar build")
        else:
            for fields in build_clips:
                cutoff = last_bar_tick + (288 if int(fields[1]) == 2 else 336)
                events = fields[5].split(";") if len(fields) > 5 else ()
                if any(int(event.split(":")[0]) + int(event.split(":")[1]) > cutoff
                       for event in events if event):
                    errors.append(f"{song['title']}: final build note extends into the withdrawal")
                    break
    for song in SONGS:
        first_root = song["chords"][0][0]
        first_bass = bass_bar(song, "verse", 0)[0].split(":")
        if int(first_bass[2]) != first_root - 12:
            errors.append(f"{song['title']}: bass root is not one octave below the project tonic")
    for path, expected in files.items():
        if not path.exists():
            errors.append(f"missing: {path.relative_to(ROOT)}")
        elif path.read_bytes() != expected:
            errors.append(f"out of date: {path.relative_to(ROOT)}")
    listed = [f"examples/{s['slug']}.lunar" for s in SONGS]
    current = (ROOT / "sim/web/www/files.js").read_text(encoding="utf-8")
    for path in listed:
        if f"path: '{path}'" not in current:
            errors.append(f"missing web preload entry: {path}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    if len(manifest) != len(SONGS):
        errors.append(f"manifest has {len(manifest)} entries, expected {len(SONGS)}")
    for song_index, song in enumerate(SONGS):
        path = SOURCE / f"{song['slug']}.lunar"
        if song_index < len(manifest):
            expected_entry = {
                "file": "../../../engines/state/examples/" + path.name,
                "title": song["title"], "bpm": song["bpm"],
                "bars": song["bars"], "scenes": 8,
            }
            if manifest[song_index] != expected_entry:
                errors.append(f"manifest entry {song_index} does not match {song['title']}")
        doc = state_canon.loads(path.read_text(encoding="utf-8"))
        if doc["session"]["current"] not in range(1, 5):
            errors.append(f"{path.name}: selected sound slot is outside the 1..4 file range")
        set_lines = doc["set"]
        bpm_line = next((line for line in set_lines if line.startswith("bpm ")), "")
        if bpm_line != f"bpm {song['bpm'] * 100}":
            errors.append(f"{path.name}: tempo does not match the production sheet")
        sg = next(line for line in set_lines if line.startswith("sg ")).split()[1:]
        chain = list(map(int, sg))
        if len(set(chain)) != 8 or set(chain) != set(range(8)):
            errors.append(f"{path.name}: song chain must visit all eight scenes")
        if chain != song["chain"]:
            errors.append(f"{path.name}: scene chain differs from the production sheet")
        if song["style"] == "electro":
            if song["scenes"][7][1] != 8 or song["chain"].count(7) != 1:
                errors.append("Neon Transit must use one eight-bar outro occurrence")
            outro_fields = next(e.split() for e in arrangement(song)
                                if e.startswith("cl 0 7 "))
            outro_events = [event for event in outro_fields[5].split(";") if event]
            if any(int(event.split(":")[0]) >= 4 * 16 * 24 for event in outro_events):
                errors.append("Neon Transit outro drums must stay absent in its final four bars")
        if "se 2" not in set_lines:
            errors.append(f"{path.name}: end mode is not Stop")
        if len(doc["sounds"]) != 4 or len([l for l in set_lines if l.startswith("tk ")]) != 8:
            errors.append(f"{path.name}: expected four sounds and eight track slots")
        scene_bars = dict(enumerate(length for _, length in song["scenes"]))
        clips = {}
        lock_tracks = set()
        for line in set_lines:
            fields = line.split()
            if fields[0] == "cl" and len(fields) >= 5:
                clips[(int(fields[1]), int(fields[2]))] = int(fields[3])
                # The final field on each event is the clip-local step index.
                for event in fields[5].split(";") if len(fields) > 5 else ():
                    event_fields = list(map(int, event.split(":")))
                    if event_fields[4] != event_fields[0] // 24:
                        errors.append(f"{path.name}: note step does not match its tick")
            elif fields[0] == "lk" and len(fields) == 4:
                lock_tracks.add((int(fields[1]), int(fields[2])))
        for scene, bars in scene_bars.items():
            for track in range(8):
                if clips.get((track, scene)) != bars * 16:
                    errors.append(f"{path.name}: track {track} scene {scene} has the wrong clip length")
            for track in (1, 3):
                if (track, scene) not in lock_tracks:
                    errors.append(f"{path.name}: scene {scene} is missing track {track} parameter locks")
        chain_bars = sum(scene_bars[index] for index in chain)
        if chain_bars != song["bars"]:
            errors.append(f"{path.name}: chain totals {chain_bars} bars, expected {song['bars']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write generated projects and manifest")
    group.add_argument("--check", action="store_true", help="check generated files and preload entries")
    args = parser.parse_args()
    files = outputs()
    if args.write:
        for path, raw in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        print(f"wrote {len(files)} generated files")
        return 0
    errors = check(files)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{len(files)} generated files and four project chains are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
