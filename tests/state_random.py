"""Random states for the state codecs' tests (tests/test_state_codec.py;
notes/2026-10-06-state-files.md §17): documents of every file kind built
from the build's names, which between them write every parameter of every
registered engine, effect, MIDI effect and modulation kind, every pad of
every kit and every FM6 slot (the save-coverage rule, ST20), in forms a
reader must take besides the canonical one: ENUM values by index, names
in another ASCII case or by abbreviation, members in another order (within
the context-first rules), movy1 lines no core writes.
"""
import random

from tests import state_canon as canon
from tools import lunar_state as ls

SOUND, INSERT, MASTER, MFX = ls.SOUND, ls.INSERT, ls.MASTER, ls.MFX


def value(rnd, p, loose=False):
    if p.enum:
        k = rnd.randrange(p.count())
        if loose and rnd.random() < 0.3 or not p.entries:
            return k
        name = p.entries[k]
        return name.swapcase() if loose and rnd.random() < 0.2 and name.isascii() else name
    pick = rnd.randrange(8)
    v = p.min if pick == 0 else p.max if pick == 1 else p.default if pick == 2 else \
        p.min + rnd.random() * (p.max - p.min)
    v = min(max(canon.f32(v), p.min), p.max)
    return int(v) if v == int(v) and abs(v) < 1e9 else v


def key(rnd, table, p, loose):
    """p's key: its name, or in loose form another ASCII case or its
    abbreviation, when that still names p and nothing before it."""
    alt = None
    if loose and rnd.random() < 0.15 and p.name.isascii():
        alt = p.name.swapcase()
    elif loose and rnd.random() < 0.1 and p.abbr:
        alt = p.abbr
    if alt is not None and table[ls.find_param(table, alt) or 0] is p and ls.find_param(table, alt) is not None:
        return alt
    return p.name


def params(rnd, table, focus_side, loose):
    ps = [p for p in sorted(table, key=lambda p: p.uid) if (p.focus == 2) == focus_side]
    if loose:
        rnd.shuffle(ps)
    out, used = {}, set()
    for p in ps:
        k = key(rnd, table, p, loose)
        if ls.ascii_lower(k) in used:
            k = p.name
        used.add(ls.ascii_lower(k))
        out[k] = value(rnd, p, loose)
    return out


def unit(rnd, names, role, e, loose):
    u = {"engine": e.id}
    if role == MFX:
        u["on"] = rnd.random() < 0.5
    u["params"] = params(rnd, e.params, False, loose) if not e.pads else \
        {k: v for k, v in params(rnd, e.params, False, loose).items()}
    if role == SOUND and e.pads:
        u["pads"] = [params(rnd, e.params, True, loose) for _ in range(e.pads)]
    return u


def sound_unit(rnd, names, e, fxs, mfxs, loose):
    u = unit(rnd, names, SOUND, e, loose)
    u["level"] = canon.f32(rnd.choice([0.0, 100.0, rnd.uniform(0, 100)]))
    u["inserts"] = [unit(rnd, names, INSERT, f, loose) if f else None for f in fxs]
    u["midi_fx"] = [unit(rnd, names, MFX, m, loose) if m else None for m in mfxs]
    if loose and rnd.random() < 0.5:
        items = list(u.items())
        head, rest = items[:1], items[1:]
        rnd.shuffle(rest)
        u = dict(head + rest)
    return u


def dx7_voice(rnd, slot):
    name = "".join(rnd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789-") for _ in range(rnd.randint(1, 10))).strip()
    return {"slot": slot, "name": name or "V",
            "ops": [[rnd.randint(0, m) for m in ls.OP_MAX] for _ in range(6)],
            "globals": [rnd.randint(0, m) for m in ls.GLOB_MAX]}


def mod(rnd, names, kinds, units, kind, seed=True):
    """A rack of `kinds` and random cables between its modules, the system
    sources and the named units' parameters."""
    rack, cables = [], []
    positions = rnd.sample(range(1, 9), len(kinds))
    for pos, k in sorted(zip(positions, kinds)):
        x = {"pos": pos, "kind": k.id, "params": params(rnd, k.params, False, False)}
        if rnd.random() < 0.2:
            x["data"] = {"version": rnd.randint(0, 255), "hex": bytes(rnd.getrandbits(8) for _ in
                                                                         range(rnd.randint(0, 40))).hex()}
        rack.append(x)
    by_pos = {x["pos"]: names.kinds[x["kind"]] for x in rack}
    sources = list(names.sources.values())
    for slot in sorted(rnd.sample(range(1, 33), rnd.randint(0, 12))):
        def ref():
            outs = [(p, k) for p, k in by_pos.items() if k.outs]
            if outs and rnd.random() < 0.6:
                p, k = rnd.choice(outs)
                return {"module": p, "port": rnd.choice(k.outs) if rnd.random() < 0.8 else
                        rnd.randint(1, len(k.outs))}
            return {"source": rnd.choice(sources)}
        pick = rnd.random()
        if pick < 0.5 and units:
            uname, table = rnd.choice(units)
            to = {"unit": uname, "param": rnd.choice(table).name if table else rnd.choice(["Cutoff", "Mix"])}
        elif pick < 0.8 and by_pos:
            p, k = rnd.choice(sorted(by_pos.items()))
            if k.gates and rnd.random() < 0.4:
                to = {"module": p, "gate": rnd.choice(k.gates)}
            else:
                to = {"module": p, "param": rnd.choice(k.params).name}
        else:
            to = {"unit": "host", "param": rnd.choice(names.host).name if kind != "sound" else "Pitch"}
        cables.append({"slot": slot, "on": rnd.random() < 0.8, "from": ref(),
                       "via": ref() if rnd.random() < 0.3 else None, "to": to,
                       "amount": canon.percent(rnd.randint(-16384, 16384)),
                       "offset": canon.percent(rnd.choice([0, rnd.randint(-16384, 16384)])),
                       "polarity": rnd.choice(ls.POLARITY), "curve": rnd.choice(ls.CURVES),
                       "voice": rnd.random() < 0.3, "lock": rnd.choice([0, rnd.randint(1, 4095)])})
    m = {"rack": rack, "cables": cables}
    if seed:
        m = {"seed": rnd.getrandbits(32), **m}
    return m


def set_lines(rnd):
    lines = ["movy1", "bpm %d" % rnd.randint(2000, 30000), "swing %d" % rnd.randint(50, 80), "link 0"]
    if rnd.random() < 0.5:
        lines.append("sg " + " ".join(str(rnd.randint(0, 7)) for _ in range(rnd.randint(1, 30))))
    lines += ["dq %d" % rnd.randint(0, 100), "sn 0 Intro"]
    for t in range(rnd.randint(1, 4)):
        lines += ["tk %d %d 0" % (t, rnd.randint(0, 7)), "au %d 0 %d synth:Timbre" % (t, rnd.randint(0, 127))]
        for s in rnd.sample(range(8), rnd.randint(0, 3)):
            notes = ";".join("%d:%d:%d:%d:%d" % (st * 24, rnd.randint(1, 400), rnd.randint(0, 127),
                                                 rnd.randint(1, 127), st)
                             for st in sorted(rnd.sample(range(64), rnd.randint(0, 16))))
            lines += ["cl %d %d %d 0 %s" % (t, s, rnd.choice([16, 32, 64]), notes),
                      "cp %d %d 1 1 %d 0" % (t, s, rnd.randint(-36, 36))]
            if rnd.random() < 0.5:
                lines.append("lk %d %d " % (t, s) + ";".join("0:%d:%d" % (st, rnd.randint(0, 127))
                                                             for st in range(0, 16, 4)))
            if rnd.random() < 0.3:
                lines.append("tg %d %d 0:-1:50:1:1:0;4:0:100:2:4:1" % (t, s))
    if rnd.random() < 0.5:
        lines.append("tk 9  0 0")          # no core writes this: a raw item
    return lines


def head(kind, rnd):
    h = {"lunar": "1.0", "kind": kind}
    if rnd.random() < 0.7:
        h["made"] = {"by": rnd.choice(["hand", "desktop", "simulator"])}
    if rnd.random() < 0.7:
        h["name"] = "TEST %d" % rnd.randint(0, 999)
        h["title"] = "Ünïcode tïtle — %d ✓" % rnd.randint(0, 99)
        h["about"] = "About: " + "x" * rnd.randint(0, 200)
        h["licence"] = "MIT"
    return h


def documents(names, seed=5, projects=6, loose=False):
    """Documents that between them cover every engine, effect, MIDI effect,
    kind, pad and FM6 slot."""
    rnd = random.Random(seed)
    sounds = [e for e in names.engines if e.role == "sound"]
    fxs = [e for e in names.engines if e.role == "fx"]
    mfxs = [e for e in names.engines if e.role == "mfx"]
    kinds = list(names.kinds.values())
    docs = []
    # One sound file per sound engine, with inserts and MIDI effects cycling.
    for i, e in enumerate(sounds):
        d = head("sound", rnd)
        ins = [fxs[(2 * i) % len(fxs)], fxs[(2 * i + 1) % len(fxs)] if i % 3 else None]
        d["sound"] = sound_unit(rnd, names, e, ins, [mfxs[i % len(mfxs)]] * (i % 3), loose)
        units = [("snd", e.params), ("snd.fx1", ins[0].params)] + ([("snd.fx2", ins[1].params)] if ins[1] else [])
        d["dx7"] = [dx7_voice(rnd, s) for s in rnd.sample(range(1, 33), 2)]
        d["mod"] = mod(rnd, names, rnd.sample(kinds, 2), units, "sound", seed=False)
        docs.append(d)
    # Effects chains through every audio effect.
    for i in range(0, len(fxs), 3):
        d = head("fx", rnd)
        chain = fxs[i:i + 3]
        if rnd.random() < 0.5:
            chain = chain[:1] + [None] + chain[1:]       # a gap in the chain
        d["chain"] = [unit(rnd, names, MASTER, f, loose) if f else None for f in chain]
        units = [("fx%d" % (j + 1), f.params) for j, f in enumerate(chain) if f]
        d["mod"] = mod(rnd, names, rnd.sample(kinds, 1), units, "fx", seed=False)
        docs.append(d)
    # Mod racks through every kind.
    for i in range(0, len(kinds), 4):
        d = head("mods", rnd)
        d["mod"] = mod(rnd, names, kinds[i:i + 4], [("snd1.fx1", None), ("snd2", None), ("fx1", None)], "mods")
        docs.append(d)
    # Projects: everything, every FM6 slot among them.
    slots = list(range(1, 33))
    for i in range(projects):
        d = head("project", rnd)
        d["session"] = {"current": rnd.randint(1, 4), "octave": rnd.randint(-3, 3),
                        "transpose": rnd.randint(-12, 12)}
        if rnd.random() < 0.7:
            d["session"]["key"] = {"root": rnd.choice(ls.ROOTS), "scale": rnd.choice(["major", "minor"])}
        snds, units = [], []
        for k in range(4):
            if k and rnd.random() < 0.3:
                snds.append(None)
                continue
            e = rnd.choice(sounds)
            ins = [rnd.choice(fxs) if rnd.random() < 0.6 else None for _ in range(2)]
            mf = [rnd.choice(mfxs) if rnd.random() < 0.7 else None for _ in range(rnd.randint(0, 4))]
            snds.append(sound_unit(rnd, names, e, ins, mf, loose))
            units.append(("snd%d" % (k + 1), e.params))
            units += [("snd%d.fx%d" % (k + 1, j + 1), f.params) for j, f in enumerate(ins) if f]
        d["sounds"] = snds
        master = [rnd.choice(fxs) if rnd.random() < 0.7 else None for _ in range(2)]
        d["master"] = [unit(rnd, names, MASTER, f, loose) if f else None for f in master]
        units += [("fx%d" % (j + 1), f.params) for j, f in enumerate(master) if f]
        take = slots[i * 6:(i + 1) * 6] if i < 5 else slots[30:]
        d["dx7"] = [dx7_voice(rnd, s) for s in take]
        d["mod"] = mod(rnd, names, rnd.sample(kinds, rnd.randint(0, 8)), units, "project")
        d["set"] = set_lines(rnd)
        d["view"] = {"mode": rnd.choice(ls.MODES), "track": rnd.randint(1, 8)}
        docs.append(d)
    d = head("clip", rnd)
    d["clip"] = ["au 0 0 40 synth:Timbre", "cl 0 0 16 0 0:40:36:100:0;48:40:36:100:2", "cp 0 0 1 1 0 0",
                 "lk 0 0 0:0:40;0:4:64"]
    docs.append(d)
    d = head("settings", rnd)
    d["settings"] = {"metronome": True, "count_in_click": False, "full_velocity": True,
                     "midi_in_channel": rnd.randint(0, 16)}
    docs.append(d)
    return docs


def text(doc, rnd, loose):
    """A document as text: canonical, compact, or with the top members in
    another order the context-first rules allow."""
    if not loose:
        return canon.dumps(doc)
    if rnd.random() < 0.3:
        return canon.compact(doc)
    items = list(doc.items())
    first, rest = items[:2], items[2:]
    late = [kv for kv in rest if kv[0] == "mod"]
    rest = [kv for kv in rest if kv[0] != "mod"]
    rnd.shuffle(rest)
    return canon.dumps(dict(first + rest + late))
