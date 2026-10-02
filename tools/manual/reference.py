"""Reference data for the manual, read from the code rather than written by hand.

- Engines and effects: `engines/build/fm1-render --list` (JSON). Each parameter
  has a name, a type (0 continuous, 1 list), a range, a default and a page;
  lists carry their value names in `names` when the renderer reports them.
- The sequencer, when its code is in the tree: the grid constants of
  `engines/include/fm1_seq.h`, the verbs of `engines/seq/seq_cmd.c` (described
  in manual/data/seq-verbs.toml) and `engines/build/fm1-seq --sizes`. Without
  `fm1_seq.h` every sequencer table is skipped.

Everything here returns HTML fragments; build.py places them. MIT licence.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PARAM_FLOAT, PARAM_ENUM = 0, 1
DASH = "\u2013"
KIND_LABEL = {"sound": "Sound engine", "audio_fx": "Effect", "midi_fx": "MIDI effect"}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def num(v: float) -> str:
    """A parameter value as a person reads it: 0.5, 12, −24 (a real minus)."""
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s.replace("-", "−")


@dataclass
class Param:
    name: str
    type: int
    min: float
    max: float
    default: float
    page: int
    names: list[str] | None = None

    @property
    def is_list(self) -> bool:
        return self.type == PARAM_ENUM

    @property
    def count(self) -> int:
        return int(round(self.max - self.min)) + 1


@dataclass
class Engine:
    id: str
    name: str
    credits: str
    kind: str
    max_voices: int
    params: list[Param] = field(default_factory=list)

    def pages(self) -> list[list[tuple[int, Param]]]:
        """Parameters by page; within a page, KNOB1-4 in parameter order."""
        out: dict[int, list[tuple[int, Param]]] = {}
        for p in self.params:
            out.setdefault(p.page, [])
            out[p.page].append((len(out[p.page]), p))
        return [out[k] for k in sorted(out)]


def parse_list(data) -> list[Engine]:
    engines = []
    for e in data:
        params = [Param(p["name"], int(p["type"]), float(p["min"]), float(p["max"]),
                        float(p["def"]), int(p["page"]), p.get("names"))
                  for p in e.get("params", [])]
        engines.append(Engine(e["id"], e["name"], e.get("credits", ""), e["kind"],
                              int(e.get("max_voices", 0)), params))
    return engines


def run_list(renderer: Path) -> list:
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


# ---- engine tables ------------------------------------------------------------

def check_engine(e: Engine) -> list[str]:
    """Problems a reader would trip over: more than four knobs on a page, a
    list without names, names that do not match the range."""
    problems = []
    for page in e.pages():
        if len(page) > 4:
            problems.append(f"{e.id}: page {page[0][1].page + 1} has {len(page)} parameters "
                            "for four knobs")
    for p in e.params:
        if p.is_list and p.names is None:
            problems.append(f"{e.id}: {p.name}: fm1-render --list reports no value names")
        elif p.is_list and len(p.names) != p.count:
            problems.append(f"{e.id}: {p.name}: {len(p.names)} names for {p.count} values")
    return problems


def value_name(p: Param, v: float) -> str | None:
    if p.is_list and p.names:
        i = int(round(v - p.min))
        if 0 <= i < len(p.names):
            return p.names[i]
    return None


def engine_table(e: Engine) -> str:
    """Knob map, parameter table and list values for one engine or effect."""
    kind = KIND_LABEL.get(e.kind, e.kind)
    rows = []
    knob_rows = []
    for page in e.pages():
        cells = []
        for knob, p in page:
            cells.append(f"<td>{esc(p.name)}</td>")
        cells += ["<td class='empty'>–</td>"] * (4 - len(cells))
        knob_rows.append(f"<tr><th scope='row'>Page {page[0][1].page + 1}</th>{''.join(cells[:4])}</tr>")
        for knob, p in page:
            if p.is_list:
                kind_cell = f"List, {p.count} values"
                rng = f"{num(p.min)} – {num(p.max)}"
                dname = value_name(p, p.default)
                dflt = f"{num(p.default)}" + (f" <span class='vname'>{esc(dname)}</span>" if dname else "")
            else:
                kind_cell = "Continuous"
                rng = f"{num(p.min)} – {num(p.max)}"
                dflt = num(p.default)
            rows.append(
                f"<tr><th scope='row'>{esc(p.name)}</th>"
                f"<td class='nowrap'>Page {p.page + 1} · KNOB{knob + 1}</td>"
                f"<td>{kind_cell}</td><td class='num nowrap'>{rng}</td><td class='num'>{dflt}</td></tr>")
    parts = [f"<div class='reference' data-engine='{esc(e.id)}'>"]
    parts.append(
        "<table class='knobmap'>"
        f"<caption>{esc(e.name)}: what the four knobs do on each page</caption>"
        "<thead><tr><th scope='col'><span class='sr'>Page</span></th>"
        "<th scope='col'>KNOB1</th><th scope='col'>KNOB2</th><th scope='col'>KNOB3</th>"
        "<th scope='col'>KNOB4</th></tr></thead>"
        f"<tbody>{''.join(knob_rows)}</tbody></table>")
    parts.append(
        "<table class='params'>"
        f"<caption>{esc(e.name)} parameters</caption>"
        "<thead><tr><th scope='col'>Parameter</th><th scope='col'>Where</th>"
        "<th scope='col'>Type</th><th scope='col'>Range</th><th scope='col'>Default</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    for p in e.params:
        if not p.is_list:
            continue
        if p.names:
            items = "".join(f"<li><span class='vnum'>{num(p.min + i)}</span> {esc(n)}</li>"
                            for i, n in enumerate(p.names))
            cls = "values long" if len(p.names) > 16 else "values"
            parts.append(f"<div class='{cls}'><p class='values-title'>{esc(p.name)} values</p>"
                         f"<ol>{items}</ol></div>")
        else:
            parts.append(f"<p class='values-missing'>{esc(p.name)}: values {num(p.min)} to "
                         f"{num(p.max)}. Their names appear here once the desktop renderer "
                         "reports them.</p>")
    voices = f"{e.max_voices} voices" if e.kind == "sound" else kind
    parts.append(f"<p class='reference-meta'><span>{esc(voices)}</span> · "
                 f"<span>Identifier <code>{esc(e.id)}</code></span> · "
                 f"<span>{esc(e.credits)}</span></p>")
    parts.append("</div>")
    return "".join(parts)


def engine_summary(engines: list[Engine], kind: str, section_ids: dict[str, str]) -> str:
    """One row per engine of a kind, linking to its section when it has one."""
    rows = []
    for e in engines:
        if e.kind != kind:
            continue
        name = esc(e.name)
        if e.id in section_ids:
            name = f"<a href='{esc(section_ids[e.id])}'>{name}</a>"
        lists = [p.name for p in e.params if p.is_list]
        cells = [f"<th scope='row'>{name}</th>"]
        if kind == "sound":
            cells.append(f"<td class='num'>{e.max_voices}</td>")
        cells.append(f"<td class='num'>{len(e.params)}</td>")
        cells.append(f"<td>{esc(', '.join(lists)) or DASH}</td>")
        cells.append(f"<td>{esc(e.credits)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    head = "<th scope='col'>Name</th>"
    if kind == "sound":
        head += "<th scope='col'>Voices</th>"
    head += "<th scope='col'>Parameters</th><th scope='col'>Chosen from a list</th><th scope='col'>Built from</th>"
    what = "Sound engines" if kind == "sound" else "Effects"
    return (f"<table class='summary'><caption>{what} in this build</caption>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")


# ---- the sequencer ------------------------------------------------------------------

@dataclass
class SeqInfo:
    defines: dict[str, int]
    comments: dict[str, str]
    verbs: list[str]
    sizes: dict | None


DEFINE_RE = re.compile(r"^#define\s+(FM1_SEQ_[A-Z0-9_]+)\s+(\d+)u?\b[^/\n]*(?:/\*\s*(.*?)\s*\*/)?", re.M)
VERB_RE = re.compile(r'\{\s*"([a-z0-9]+)"\s*,\s*FM1_SEQ_V_[A-Z0-9_]+\s*\}')


def load_seq(repo: Path, seq_tool: Path | None) -> SeqInfo | None:
    header = repo / "engines" / "include" / "fm1_seq.h"
    if not header.is_file():
        return None
    text = header.read_text()
    defines, comments = {}, {}
    for m in DEFINE_RE.finditer(text):
        defines[m.group(1)] = int(m.group(2))
        if m.group(3):
            comments[m.group(1)] = m.group(3)
    m = re.search(r"FM-1 build uses (\d+)\.\.(\d+)", text)
    if m:
        defines["_FM1_TRACKS_LO"], defines["_FM1_TRACKS_HI"] = int(m.group(1)), int(m.group(2))
    cmd = repo / "engines" / "seq" / "seq_cmd.c"
    verbs = VERB_RE.findall(cmd.read_text()) if cmd.is_file() else []
    sizes = None
    if seq_tool and seq_tool.is_file():
        try:
            out = subprocess.run([str(seq_tool), "--sizes"], check=True, capture_output=True,
                                 text=True, timeout=60)
            sizes = json.loads(out.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            sizes = None
    return SeqInfo(defines, comments, verbs, sizes)


def seq_glance(seq: SeqInfo) -> str:
    d = seq.defines
    rows = []

    def row(label, value, note=""):
        rows.append(f"<tr><th scope='row'>{esc(label)}</th><td>{value}</td>"
                    f"<td>{esc(note)}</td></tr>")

    if "FM1_SEQ_PPQN" in d:
        row("Clock resolution", f"{d['FM1_SEQ_PPQN']} ticks per quarter note",
            "MIDI clock out is 24 per quarter note")
    if "FM1_SEQ_TICKS_PER_STEP" in d and "FM1_SEQ_STEPS_PER_BAR" in d:
        row("Step", f"{d['FM1_SEQ_TICKS_PER_STEP']} ticks, a sixteenth note",
            f"{d['FM1_SEQ_STEPS_PER_BAR']} steps to a 4/4 bar")
    if "FM1_SEQ_MAX_STEPS" in d and "FM1_SEQ_STEPS_PER_BAR" in d:
        bars = d["FM1_SEQ_MAX_STEPS"] // d["FM1_SEQ_STEPS_PER_BAR"]
        row("Clip length", f"1 – {d['FM1_SEQ_MAX_STEPS']} steps", f"up to {bars} bars")
    if "FM1_SEQ_MAX_TRACKS" in d:
        lo, hi = d.get("_FM1_TRACKS_LO"), d.get("_FM1_TRACKS_HI")
        row("Tracks", f"up to {d['FM1_SEQ_MAX_TRACKS']}",
            f"the FM-1 build is planned with {lo} to {hi}" if lo and hi else "")
    if "FM1_SEQ_SLOTS" in d:
        row("Clip slots", f"{d['FM1_SEQ_SLOTS']} per track", "a scene is one slot on every track")
    if "FM1_SEQ_LANES" in d:
        row("Parameter-lock lanes", f"{d['FM1_SEQ_LANES']} per track",
            "each lane drives one parameter")
    if "FM1_SEQ_VAL_MAX" in d:
        row("Lock values", f"0 – {d['FM1_SEQ_VAL_MAX']}",
            "scaled onto the parameter's own range")
    if "FM1_SEQ_CHORD_MAX" in d:
        row("Notes on one step", f"up to {d['FM1_SEQ_CHORD_MAX']} at once", "a chord")
    if "FM1_SEQ_BPM_X100_MIN" in d and "FM1_SEQ_BPM_X100_MAX" in d:
        row("Tempo", f"{d['FM1_SEQ_BPM_X100_MIN'] / 100:.0f} – "
                     f"{d['FM1_SEQ_BPM_X100_MAX'] / 100:.0f} BPM", "in steps of 0.01 BPM")
    if not rows:
        return ""
    return ("<table class='glance'><caption>The sequencer at a glance</caption>"
            "<thead><tr><th scope='col'>Item</th><th scope='col'>Value</th>"
            "<th scope='col'>Notes</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def seq_memory(seq: SeqInfo) -> str:
    s = seq.sizes
    if not s or "tracks" not in s:
        return ""
    rows = []
    for t in ("4", "6", "8", "16"):
        if t not in s["tracks"]:
            continue
        plain = f"{s['tracks'][t] / 1024:.1f} KB"
        cap = s.get("capture256", {}).get(t)
        with_cap = f"{cap / 1024:.1f} KB" if cap is not None else DASH
        rows.append(f"<tr><th scope='row'>{t}</th><td class='num'>{plain}</td>"
                    f"<td class='num'>{with_cap}</td></tr>")
    return ("<table class='memory'><caption>Memory the sequencer takes, by number of tracks</caption>"
            "<thead><tr><th scope='col'>Tracks</th><th scope='col'>Without Capture</th>"
            "<th scope='col'>With a 256-event Capture</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def load_verb_notes(path: Path) -> dict:
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text())


def seq_verbs(seq: SeqInfo, notes: dict, warnings: list[str]) -> str:
    if not seq.verbs:
        return ""
    groups: dict[str, list[str]] = {}
    order = notes.get("groups", {}).get("order", [])
    described = notes.get("verb", {})
    for v in seq.verbs:
        g = described.get(v, {}).get("group", "Not described yet")
        groups.setdefault(g, []).append(v)
        if v not in described:
            warnings.append(f"sequencer verb '{v}' has no entry in manual/data/seq-verbs.toml")
    for v in described:
        if v not in seq.verbs:
            warnings.append(f"manual/data/seq-verbs.toml describes '{v}', which seq_cmd.c no longer has")
    names = [g for g in order if g in groups] + [g for g in groups if g not in order]
    body = []
    for g in names:
        body.append(f"<tr class='group'><th colspan='3' scope='colgroup'>{esc(g)}</th></tr>")
        for v in groups[g]:
            d = described.get(v, {})
            args = " ".join(d.get("args", "").split())
            body.append(f"<tr><th scope='row'><code>{esc(v)}</code></th>"
                        f"<td><code>{esc(args) or DASH}</code></td>"
                        f"<td>{esc(d.get('does', 'Not described yet.'))}</td></tr>")
    return ("<table class='verbs'><caption>Sequencer commands for scripts</caption>"
            "<thead><tr><th scope='col'>Verb</th><th scope='col'>Arguments</th>"
            "<th scope='col'>What it does</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")
