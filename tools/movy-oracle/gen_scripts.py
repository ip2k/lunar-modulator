#!/usr/bin/env python3
"""Seeded random verb scripts for the Movy oracle (docs/13 stage M3).

    python3 tools/movy-oracle/gen_scripts.py --seed 1 --count 100 --out DIR
    tools/movy-oracle/run-on-aeon.sh --movy1 DIR DIR-out

Writes DIR/rand-<seed>-<nnnnn>.verbs in the shared verb-script format
(tools/movy-oracle/README.md): Movy's own `cmd` verbs, timed in frames.
The same seed and options give the same scripts.

A script sets up a few tracks while stopped (notes, chords, locks, trig
conditions and probability, quantise, swing, scale, transpose, loop
windows), starts the transport one of four ways (play, a clip launch, a
recording with its count-in, a song), then mixes edits and performance
gestures at random frames: toggles, locks, conditions, live recording and
overdubs, launches, scenes and songs, nudges, copy and paste, undo, mutes,
tempo changes, stops and restarts. It ends with `stop`.

Only verbs the FM-1 port keeps are used: never `link`/`minject` (the Move
transport link), `hold`, or the external clock. `--capture` adds Capture
(record-after) phrases. `--no-d5` keeps every loop window at step 0, so no
script reaches docs/13 D5 (Movy's nudge can panic on an offset window).

Our code, MIT. Nothing here runs Movy; run-on-aeon.sh does that in a
container on aeon.
"""

from __future__ import annotations

import argparse
import pathlib
import random

STEPS_PER_BAR = 16
TICKS_PER_STEP = 24
MAX_STEPS = 256
SCALES = [(1, 1)] * 10 + [(2, 1), (1, 2), (4, 1), (1, 4), (3, 2), (2, 3),
                          (3, 4), (4, 3), (1, 8), (8, 1), (5, 4)]
CONDS = [(1, 2), (2, 2), (1, 3), (2, 3), (3, 3), (1, 4), (4, 4), (3, 4),
         (4, 7), (1, 8), (8, 8), (2, 5), (1, 1), (5, 64)]
LABELS = ["synth:cutoff", "synth:reso", "synth:attack", "synth:decay",
          "fx:mix", "fx:time", "synth:timbre", "synth:morph"]
SCALE_PITCHES = [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74]
DRUM_PITCHES = [36, 38, 40, 42, 44, 46, 49, 51]


class ClipModel:
    """What the generator believes about one clip. Approximate on purpose:
    it only steers choices towards targets that matter (steps with notes,
    clips that exist); Movy decides what really happens."""

    def __init__(self) -> None:
        self.length = 0
        self.start = 0
        self.steps: set[int] = set()

    @property
    def exists(self) -> bool:
        return self.length > 0

    def window(self) -> tuple[int, int]:
        return self.start, self.start + max(self.length, STEPS_PER_BAR)


class TrackModel:
    def __init__(self) -> None:
        self.active = 0
        self.clips = [ClipModel() for _ in range(8)]
        self.lanes: set[int] = set()
        self.drum = False

    @property
    def clip(self) -> ClipModel:
        return self.clips[self.active]


class Gen:
    def __init__(self, rng: random.Random, args: argparse.Namespace, index: int) -> None:
        self.r = rng
        self.a = args
        self.index = index
        self.n = args.tracks
        self.rate = args.rate
        self.cmds: list[tuple[int, int, str]] = []
        self.seq = 0
        self.bpm = 120.0
        self.tracks = [TrackModel() for _ in range(self.n)]
        # Most activity on a few tracks, so clips get dense enough to matter.
        self.busy = list(range(min(self.n, self.r.choice([1, 2, 2, 3, 4]))))
        self.undo_id = 1
        # D5: Movy's nudge panics when a note's anchor lies two or more steps
        # past the clip's length (an offset window, or a clip shortened under
        # its notes). With --no-d5 a script either nudges or reshapes clips,
        # never both, and windows start at step 0.
        self.reshape_ok = not args.no_d5 or self.r.random() < 0.5
        self.nudge_ok = not args.no_d5 or not self.reshape_ok
        self.playing = False

    # ── helpers ────────────────────────────────────────────────────────
    def at(self, frame: int, cmd: str) -> None:
        self.cmds.append((max(0, int(frame)), self.seq, cmd))
        self.seq += 1

    def bar_frames(self) -> float:
        return self.rate * 240.0 / self.bpm

    def step_frames(self) -> float:
        return self.bar_frames() / STEPS_PER_BAR

    def track(self) -> int:
        if self.r.random() < 0.85:
            return self.r.choice(self.busy)
        return self.r.randrange(self.n)

    def pitch(self, t: int) -> int:
        if self.tracks[t].drum:
            return self.r.choice(DRUM_PITCHES)
        return self.r.choice(SCALE_PITCHES)

    def vel(self) -> int:
        return self.r.choice([1, 40, 64, 90, 100, 110, 127, self.r.randint(1, 127)])

    def step_in(self, t: int, grow: float = 0.08) -> int:
        c = self.tracks[t].clip
        lo, hi = c.window()
        if self.r.random() < grow:
            return min(MAX_STEPS - 1, hi + self.r.randrange(STEPS_PER_BAR))
        return self.r.randrange(lo, min(hi, MAX_STEPS))

    def note_step(self, t: int) -> int:
        c = self.tracks[t].clip
        if c.steps and self.r.random() < 0.8:
            return self.r.choice(sorted(c.steps))
        return self.step_in(t, 0.0)

    def lane_pitch(self, t: int) -> int:
        return -1 if self.r.random() < 0.6 else self.pitch(t)

    def ensure_len(self, c: ClipModel, step: int) -> None:
        if not c.exists:
            c.length = STEPS_PER_BAR
        if step >= c.start + c.length:
            end = (step // STEPS_PER_BAR + 1) * STEPS_PER_BAR
            c.length = min(end - c.start, MAX_STEPS - c.start)

    # ── one-shot edits (frame f) ───────────────────────────────────────
    def e_tog(self, f: int) -> None:
        t = self.track()
        s = self.step_in(t)
        notes = [(self.pitch(t), self.vel())]
        if self.r.random() < 0.25:
            notes += [(self.pitch(t), self.vel()) for _ in range(self.r.randint(1, 3))]
        self.at(f, f"tog {t} {s} " + " ".join(f"{p} {v}" for p, v in notes))
        c = self.tracks[t].clip
        if s in c.steps:
            c.steps.discard(s)
        else:
            c.steps.add(s)
            self.ensure_len(c, s)

    def e_ltog(self, f: int) -> None:
        t = self.track()
        s = self.step_in(t)
        self.at(f, f"ltog {t} {s} {self.pitch(t)} {self.vel()}")
        c = self.tracks[t].clip
        c.steps.add(s)
        self.ensure_len(c, s)

    def e_addp(self, f: int) -> None:
        t = self.track()
        lo, hi = self.tracks[t].clip.window()
        s0 = self.r.randrange(lo, hi)
        s1 = min(hi - 1, s0 + self.r.choice([0, 1, 3, 7, 15]))
        self.at(f, f"addp {t} {s0} {s1} {self.pitch(t)} {self.vel()}")
        c = self.tracks[t].clip
        c.steps.update(range(s0, s1 + 1))
        self.ensure_len(c, s1)

    def e_del(self, f: int) -> None:
        t = self.track()
        s0 = self.note_step(t)
        s1 = s0 + self.r.choice([0, 0, 0, 3, 15])
        s1 = min(s1, MAX_STEPS - 1)
        self.at(f, f"del {t} {s0} {s1} {self.lane_pitch(t)}")
        self.tracks[t].clip.steps -= set(range(s0, s1 + 1))

    def e_alabel(self, f: int, t: int | None = None) -> None:
        t = self.track() if t is None else t
        lane = self.r.randrange(8)
        self.at(f, f"alabel {t} {lane} {self.r.choice(LABELS)}")
        self.tracks[t].lanes.add(lane)

    def lane(self, t: int) -> int:
        lanes = sorted(self.tracks[t].lanes)
        if lanes and self.r.random() < 0.85:
            return self.r.choice(lanes)
        return self.r.randrange(8)

    def e_aset(self, f: int) -> None:
        t = self.track()
        quiet = self.r.choice(["", " 1", " 0", " 1"])
        self.at(f, f"aset {t} {self.lane(t)} {self.step_in(t, 0.0)} {self.r.randint(0, 127)}{quiet}")

    def e_asetr(self, f: int) -> None:
        t = self.track()
        s0 = self.step_in(t, 0.0)
        s1 = min(MAX_STEPS - 1, s0 + self.r.choice([1, 3, 7, 15]))
        quiet = self.r.choice(["", " 1"])
        self.at(f, f"asetr {t} {self.lane(t)} {s0} {s1} {self.r.randint(0, 127)}{quiet}")

    def e_aclr(self, f: int) -> None:
        t = self.track()
        k = self.r.random()
        if k < 0.5:
            self.at(f, f"aclrs {t} {self.lane(t)} {self.step_in(t, 0.0)}")
        elif k < 0.8:
            self.at(f, f"aclrstep {t} {self.step_in(t, 0.0)}")
        else:
            lane = self.lane(t)
            self.at(f, f"aclr {t} {lane}")
            self.tracks[t].lanes.discard(lane)

    def e_abase(self, f: int) -> None:
        t = self.track()
        verb = self.r.choice(["abase", "abase", "abaseq"])
        self.at(f, f"{verb} {t} {self.lane(t)} {self.r.randint(0, 127)}")

    def e_trig(self, f: int) -> None:
        t = self.track()
        s0 = self.note_step(t)
        s1 = s0 if self.r.random() < 0.8 else min(MAX_STEPS - 1, s0 + self.r.choice([3, 15]))
        p = self.lane_pitch(t)
        k = self.r.random()
        if k < 0.4:
            pct = self.r.choice([0, 10, 25, 50, 75, 90, 100, self.r.randint(0, 100)])
            self.at(f, f"eprob {t} {s0} {s1} {p} {pct}")
        elif k < 0.85:
            a, b = self.r.choice(CONDS)
            self.at(f, f"econd {t} {s0} {s1} {p} {a} {b}")
        else:
            self.at(f, f"einv {t} {s0} {s1} {p} {self.r.randint(0, 1)}")

    def e_note_edit(self, f: int) -> None:
        t = self.track()
        s0 = self.note_step(t)
        s1 = s0 if self.r.random() < 0.75 else min(MAX_STEPS - 1, s0 + 15)
        p = self.lane_pitch(t)
        k = self.r.random()
        if k < 0.25:
            self.at(f, f"evel {t} {s0} {s1} {p} {self.r.choice([-50, -10, -1, 1, 10, 50])}")
        elif k < 0.5:
            self.at(f, f"elen {t} {s0} {s1} {p} {self.r.choice([-24, -6, -1, 1, 6, 24, 48, 200])}")
        elif k < 0.65:
            self.at(f, f"slen {t} {s0} {s1} {p} {self.r.choice([1, 6, 12, 24, 48, 96, 400])}")
        elif k < 0.9 and self.nudge_ok:
            self.at(f, f"enudge {t} {s0} {s1} {p} {self.r.choice([-2, -1, 1, 2, -24, 24, 30])}")
        else:
            self.at(f, f"etrn {t} {s0} {s1} {p} {self.r.choice([-12, -1, 1, 7, 12])}")

    def e_clip_param(self, f: int) -> None:
        t = self.track()
        k = self.r.random()
        if k < 0.25:
            self.at(f, f"cq {t} {self.r.choice([0, 25, 50, 75, 100, self.r.randint(0, 100)])}")
        elif k < 0.35:
            self.at(f, f"dq {self.r.choice([0, 50, 100])}")
        elif k < 0.6:
            n, d = self.r.choice(SCALES)
            self.at(f, f"cscl {t} {n} {d}")
        elif k < 0.8:
            self.at(f, f"ctr {t} {self.r.choice([-36, -12, -5, 0, 3, 7, 12, 36])}")
        elif self.reshape_ok:
            c = self.tracks[t].clip
            steps = self.r.choice([1, 3, 7, 12, 15, 16, 24, 32])
            self.at(f, f"clen {t} {steps}")
            if c.exists:
                c.length = min(steps, MAX_STEPS - c.start)

    def e_loop(self, f: int) -> None:
        t = self.track()
        c = self.tracks[t].clip
        if self.r.random() < 0.3 or not self.reshape_ok:
            self.at(f, f"dbl {t}")
            if c.exists and c.start + 2 * c.length <= MAX_STEPS:
                c.steps |= {s + c.length for s in c.steps if c.start <= s < c.start + c.length}
                c.length *= 2
            return
        start = 0 if self.a.no_d5 else self.r.choice([0, 0, 0, 16, 32])
        length = self.r.choice([16, 16, 32, 48, 64])
        self.at(f, f"loop {t} {start} {length}")
        c.start, c.length = start, min(length, MAX_STEPS - start)

    def e_groove(self, f: int) -> None:
        if self.r.random() < 0.55:
            self.at(f, f"swing {self.r.choice([50, 54, 58, 62, 66, 70, 75, 80])}")
        else:
            bpm = self.r.choice([60, 90, 100, 120, 128, 140, 174, 200, 250])
            bpm_x100 = bpm * 100 + self.r.choice([0, 0, 0, 33, 50])
            self.at(f, f"bpm {bpm_x100}")
            self.bpm = bpm_x100 / 100.0

    def e_session(self, f: int) -> None:
        t = self.track()
        k = self.r.random()
        slot = self.r.choice([0, 0, 1, 1, 2, 3, 7])
        if k < 0.45:
            self.at(f, f"launch {t} {slot}")
            self.tracks[t].active = slot
            self.playing = self.playing or self.tracks[t].clips[slot].exists
        elif k < 0.6:
            self.at(f, f"stoptrk {t}")
        elif k < 0.8:
            self.at(f, f"clipsel {t} {slot}")
            self.tracks[t].active = slot
        else:
            self.at(f, f"watch {t}")

    def e_song(self, f: int) -> None:
        scene = self.r.choice([0, 0, 1, 1, 2, 3])
        if self.r.random() < 0.4:
            self.at(f, f"song {scene}")
        else:
            self.at(f, f"songadd {scene}")

    def e_copy(self, f: int) -> None:
        t = self.track()
        k = self.r.random()
        if k < 0.5:
            s0 = self.note_step(t)
            s1 = min(MAX_STEPS - 1, s0 + self.r.choice([0, 0, 3, 15]))
            t2 = self.track()
            d = self.step_in(t2, 0.0)
            self.at(f, f"cpy {t} {s0} {s1}")
            self.at(f, f"pst {t2} {d}")
            if self.r.random() < 0.3:
                self.at(f, "cpyclr")
        elif k < 0.7:
            s = self.r.choice([0, 1, 2])
            self.at(f, f"clipcopy {t} {self.tracks[t].active}")
            self.at(f, f"clippaste {t} {s}")
            src = self.tracks[t].clip
            dst = self.tracks[t].clips[s] = ClipModel()
            dst.length, dst.start, dst.steps = src.length, src.start, set(src.steps)
            self.tracks[t].active = s
        elif k < 0.85:
            self.at(f, f"clipdup {t}")
        elif k < 0.95:
            self.at(f, f"clipdel {t}")
            self.tracks[t].clips[self.tracks[t].active] = ClipModel()
        else:
            s = self.r.randrange(8)
            self.at(f, f"clipdelat {t} {s}")
            self.tracks[t].clips[s] = ClipModel()

    def e_mute(self, f: int) -> None:
        t = self.track()
        k = self.r.random()
        if k < 0.5:
            self.at(f, f"mute {t} {self.r.randint(0, 1)}")
        elif k < 0.7:
            self.at(f, f"pmute {t} {self.pitch(t)} {self.r.randint(0, 1)}")
        elif k < 0.85:
            self.at(f, f"psolo {t} {self.r.choice([-1, -1, self.pitch(t)])}")
        else:
            d = self.r.randint(0, 1)
            self.at(f, f"tdrum {t} {d}")
            self.tracks[t].drum = bool(d)

    def e_misc(self, f: int) -> None:
        k = self.r.random()
        if k < 0.4:
            self.at(f, f"metro {self.r.randint(0, 1)}")
        elif k < 0.6:
            self.at(f, f"wlane {self.r.choice([-1, -1, 36, 60])}")
        elif k < 0.8:
            # Play while playing restarts the transport.
            self.at(f, "play")
            self.playing = True
        else:
            self.at(f, "stop")
            gap = self.r.uniform(0.1, 1.0) * self.bar_frames()
            self.at(f + gap, "play")
            self.playing = True

    ONE_SHOTS = (
        ("e_tog", 12), ("e_ltog", 4), ("e_addp", 1), ("e_del", 2),
        ("e_aset", 9), ("e_asetr", 2), ("e_aclr", 3), ("e_abase", 3),
        ("e_trig", 7), ("e_note_edit", 6), ("e_clip_param", 5), ("e_loop", 3),
        ("e_groove", 3), ("e_session", 4), ("e_song", 2), ("e_copy", 3),
        ("e_mute", 3), ("e_misc", 2),
    )

    # ── gestures spanning time ─────────────────────────────────────────
    def phrase(self, f: int, t: int, bars: float) -> int:
        """Live pad notes on track t from frame f for about `bars` bars;
        returns the frame after the last release."""
        end = f + bars * self.bar_frames()
        cur = f
        held: list[tuple[float, int]] = []
        while cur < end:
            p = self.pitch(t)
            self.at(cur, f"non {t} {p} {self.vel()}")
            length = self.r.choice([0.25, 0.5, 1, 1, 2, 4, 9]) * self.step_frames()
            held.append((cur + length, p))
            cur += self.r.choice([0, 0.5, 1, 1, 1, 2, 3]) * self.step_frames() + self.r.uniform(0, 30)
        last = cur
        for off, p in held:
            self.at(off, f"nof {t} {p}")
            last = max(last, off)
        return int(last)

    def g_record(self, f: int) -> int:
        t = self.track()
        self.at(f, f"rec {t}")
        lead = self.bar_frames() if not self.playing else self.r.uniform(0, 0.5) * self.bar_frames()
        if not self.playing:
            self.playing = True
        start = f + lead - self.r.uniform(0, 1.5) * self.step_frames()
        last = self.phrase(int(start), t, self.r.choice([0.5, 1, 1, 2]))
        if self.r.random() < 0.7:
            last = int(last + self.r.uniform(0, 1) * self.bar_frames())
            self.at(last, f"rec {t}")
        return last

    def g_undo(self, f: int) -> int:
        snap, cap = self.undo_id, self.undo_id + 1
        self.undo_id += 2
        self.at(f, f"usnap {snap}")
        name, _ = self.r.choice(self.ONE_SHOTS[:12])
        getattr(self, name)(f)
        if self.r.random() < 0.3:
            self.at(f, f"ucommit {snap}")
        later = int(f + self.r.uniform(0.1, 1.5) * self.bar_frames())
        self.at(later, f"uswap {snap} {cap}")
        if self.r.random() < 0.4:
            redo = self.undo_id
            self.undo_id += 1
            later = int(later + self.r.uniform(0.1, 1.0) * self.bar_frames())
            self.at(later, f"uswap {cap} {redo}")
        if self.r.random() < 0.1:
            self.at(later, "uclr")
        return later

    def g_capture(self, f: int) -> int:
        t = self.track()
        self.at(f, f"watch {t}")
        last = self.phrase(f, t, self.r.choice([1, 2]))
        cap_at = int(last + self.r.uniform(0.05, 0.5) * self.bar_frames())
        self.at(cap_at, f"cap {t}")
        if not self.playing:
            self.playing = True
            if self.r.random() < 0.5:
                self.at(cap_at, f"capsel {self.r.randrange(4)}")
            self.at(cap_at + int(self.bar_frames()), "capdone")
        return cap_at

    # ── whole script ───────────────────────────────────────────────────
    def setup(self) -> None:
        if self.r.random() < 0.5:
            self.e_groove(0)
        if self.r.random() < 0.5:
            self.e_groove(0)
        if self.r.random() < 0.2:
            self.at(0, f"dq {self.r.choice([0, 50, 100])}")
        for t in self.busy:
            tm = self.tracks[t]
            if self.r.random() < 0.15:
                self.at(0, f"tdrum {t} 1")
                tm.drum = True
            slots = [0] + self.r.sample(range(1, 4), self.r.choice([0, 0, 1, 2]))
            for slot in slots:
                if slot:
                    self.at(0, f"clipsel {t} {slot}")
                tm.active = slot
                if self.r.random() < 0.3:
                    self.e_loop(0)
                bars = self.r.choice([1, 1, 1, 2, 4])
                for _ in range(self.r.randint(2, 6 * bars)):
                    s = self.r.randrange(tm.clip.start, tm.clip.start + bars * STEPS_PER_BAR)
                    s = min(s, MAX_STEPS - 1)
                    if s in tm.clip.steps:
                        continue
                    notes = [(self.pitch(t), self.vel())]
                    if self.r.random() < 0.2:
                        notes.append((self.pitch(t), self.vel()))
                    verb = "ltog" if tm.drum and len(notes) == 1 else "tog"
                    args = " ".join(f"{p} {v}" for p, v in notes)
                    self.at(0, f"{verb} {t} {s} {args}")
                    tm.clip.steps.add(s)
                    self.ensure_len(tm.clip, s)
                for _ in range(self.r.randint(0, 3)):
                    self.e_trig_on(0, t)
                if self.r.random() < 0.3:
                    n, d = self.r.choice(SCALES)
                    self.at(0, f"cscl {t} {n} {d}")
                if self.r.random() < 0.2:
                    self.at(0, f"ctr {t} {self.r.choice([-12, -5, 7, 12])}")
                if self.r.random() < 0.3:
                    self.at(0, f"cq {t} {self.r.choice([25, 50, 100])}")
            if self.r.random() < 0.7:
                for _ in range(self.r.randint(1, 3)):
                    self.e_alabel(0, t)
                for lane in sorted(tm.lanes):
                    verb = "abase" if self.r.random() < 0.5 else "abaseq"
                    self.at(0, f"{verb} {t} {lane} {self.r.randint(0, 127)}")
                for _ in range(self.r.randint(0, 6)):
                    lane = self.lane(t)
                    s = self.step_in(t, 0.0)
                    self.at(0, f"aset {t} {lane} {s} {self.r.randint(0, 127)} 1")
            if slots != [0] and self.r.random() < 0.7:
                self.at(0, f"clipsel {t} 0")
                tm.active = 0
        if self.r.random() < 0.15:
            self.at(0, "metro 1")

    def e_trig_on(self, f: int, t: int) -> None:
        s = self.note_step(t)
        p = self.lane_pitch(t)
        if self.r.random() < 0.5:
            a, b = self.r.choice(CONDS)
            self.at(f, f"econd {t} {s} {s} {p} {a} {b}")
        else:
            self.at(f, f"eprob {t} {s} {s} {p} {self.r.choice([10, 50, 90])}")

    def start(self, f: int) -> int:
        k = self.r.random()
        if self.a.capture and k < 0.1:
            return self.g_capture(f)
        if k < 0.6:
            self.at(f, "play")
        elif k < 0.75:
            t = self.r.choice(self.busy)
            self.at(f, f"launch {t} {self.tracks[t].active}")
        elif k < 0.9:
            return self.g_record(f)
        else:
            self.at(f, f"song {self.r.choice([0, 0, 1])}")
            if self.r.random() < 0.6:
                self.at(f, f"songadd {self.r.choice([1, 2, 0])}")
        self.playing = True
        return f

    def build(self) -> str:
        seconds = self.r.uniform(self.a.min_seconds, self.a.max_seconds)
        end = int(seconds * self.rate)
        self.setup()
        cur = self.start(int(self.r.uniform(0, 0.25) * self.rate))
        names = [n for n, _ in self.ONE_SHOTS]
        weights = [w for _, w in self.ONE_SHOTS]
        while True:
            cur += int(self.r.choice([0, 0.25, 0.5, 1, 1, 2, 4, 8]) * self.step_frames()
                       + self.r.uniform(0, 200))
            if cur >= end:
                break
            k = self.r.random()
            if k < 0.06:
                self.g_record(cur)
            elif k < 0.11:
                self.g_undo(cur)
            elif self.a.capture and k < 0.14:
                self.g_capture(cur)
            else:
                getattr(self, self.r.choices(names, weights)[0])(cur)
        last = max([end] + [c[0] for c in self.cmds])
        self.at(last, "stop")
        self.cmds.sort(key=lambda c: (c[0], c[1]))
        head = (f"#! rate={self.rate} block={self.a.block} tracks={self.n}\n"
                f"# gen_scripts.py seed={self.a.seed} index={self.index}"
                f"{' capture' if self.a.capture else ''}{' no-d5' if self.a.no_d5 else ''}\n")
        return head + "".join(f"@{f} {c}\n" for f, _, c in self.cmds)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--tracks", type=int, default=8, choices=range(1, 17), metavar="1..16")
    ap.add_argument("--rate", type=int, default=44118)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--min-seconds", type=float, default=4.0)
    ap.add_argument("--max-seconds", type=float, default=16.0)
    ap.add_argument("--capture", action="store_true", help="add Capture (record-after) phrases")
    ap.add_argument("--no-d5", action="store_true", help="keep loop windows at step 0 (no D5)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for i in range(args.count):
        # One generator per script, seeded from (seed, index), so script i
        # does not depend on --count.
        g = Gen(random.Random(f"{args.seed}:{i}"), args, i)
        (args.out / f"rand-{args.seed}-{i:05d}.verbs").write_text(g.build())


if __name__ == "__main__":
    main()
