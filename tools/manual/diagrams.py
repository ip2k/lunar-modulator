"""Block and state diagrams for the manual, laid out and drawn as SVG.

    python3 tools/manual/diagrams.py --write        # manual/diagrams/*.toml -> *.svg
    python3 tools/manual/diagrams.py --check        # the SVGs are current and clean
    python3 tools/manual/diagrams.py --png DIR      # also rasterise them (rsvg-convert)

Each diagram has one source, manual/diagrams/NAME.toml (manual/diagrams/
README.md has the format): boxes placed on a grid of columns and rows, frames
around groups of boxes, and connections between them, each of a kind (audio,
notes, modulation, a button press...). Nothing in a source is a coordinate.
This module sizes every box from its words, spaces the grid, routes each
connection as straight runs through the gaps between boxes (choosing, for
each, the route with the fewest bends and crossings, and giving connections
that share a gap a track each), puts each label beside its connection where
nothing else is, and widens a gap and starts again when a label has no room.
diagram_check.py then checks the drawing itself: no word touches another
word, a box, a line or the edge, and no line crosses a box.

The SVG carries its own styles as presentation attributes (as figures.py's
do), so it looks the same inline, as a file and in the PDF. Colours, type and
line styles come from a Theme (diagram_theme.py); words are measured with
diagram_metrics.py. Pure Python and deterministic: the same source gives the
same bytes on any machine. MIT licence.
"""
from __future__ import annotations

import argparse
import copy
import itertools
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diagram_metrics as metrics  # noqa: E402
from diagram_theme import THEME, Theme  # noqa: E402

ROOT = HERE.parents[1]
SOURCES = ROOT / "manual" / "diagrams"

# ---- measures, in diagram units ------------------------------------------------
# The manual shows REF_WIDTH units across the full text column, so a unit is the
# same size in every diagram: 12 units is about 7.4 pt in the A5 book (a 118 mm
# column) and 15 px in a browser.
REF_WIDTH = 540.0
TITLE = (12.0, 600)        # a box's name
SUB = (10.5, 400)          # a box's other lines
LABEL = (10.5, 400)        # a connection's label
GROUP = (11.0, 600)        # a frame's title
CELL = (10.5, 600)         # a cell of a strip
LEGEND = (10.5, 400)
LINE = 1.3                 # line height, times the size

PAD_X, PAD_Y = 10.0, 6.0   # words inside a box
CELL_H, CELL_PAD = 19.0, 6.0
GPAD = 7.0                 # a frame around its boxes
FRAME_GAP = 4.0            # between a frame and the lines that pass it
BAND_X, BAND_Y = 26.0, 26.0    # the least room between columns and rows for lines
SLIVER = 6.0               # a gap no line uses
TRACK = 9.0                # between lines that share a gap
TRACK_EDGE = 9.0           # between the outermost line and the gap's side
STUB = 9.0                 # the least straight run out of a box
CLEAR = 5.0                # a line's least distance from a box it does not touch
PORT_GAP = 11.0            # between two lines on one side of a box
PORT_GAP_MIN = 8.0         # ... when they follow another box's ports
PORT_END = 7.0             # between a line and the corner of its box
LGAP = 4.0                 # a label's box from its line
LPAD = 4.0                 # a label's box from anything else
MARGIN = 8.0               # around the whole drawing
ARROW = (7.5, 3.6)         # length, half width
ARROW_AUDIO = (9.0, 4.6)
CROSS = 4.0                # half the size of a refused cable's cross
MAX_ROUNDS = 60

SIDES = ("L", "R", "T", "B")
OUT = {"L": (-1, 0), "R": (1, 0), "T": (0, -1), "B": (0, 1)}


def _f(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def lh(size: float) -> float:
    return size * LINE


# ---- the source ------------------------------------------------------------------

@dataclass
class Line:
    text: str
    size: float
    weight: int

    @property
    def width(self) -> float:
        return metrics.text_width(self.text, self.size, self.weight)


def _lines(value, style) -> list[Line]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    out = []
    for item in items:
        for part in str(item).split("\n"):
            out.append(Line(part, *style))
    return out


@dataclass
class Node:
    id: str
    lines: list
    col: int
    row: int
    cs: int = 1
    rs: int = 1
    role: str = "neutral"
    shape: str = "box"       # box, state, hollow, note, start, cells
    cells: list = field(default_factory=list)
    stretch: bool = False
    align: str = "center"    # within its cells: left, center, right
    group: str | None = None
    w: float = 0.0
    h: float = 0.0
    cell_w: float = 0.0


@dataclass
class Group:
    id: str
    label: list
    members: list
    role: str = "neutral"
    title_at: str = "top"    # or bottom
    c0: int = 0
    c1: int = 0
    r0: int = 0
    r1: int = 0


@dataclass
class Edge:
    src: str
    dst: str
    kind: str = "audio"
    role: str | None = None
    label: list = field(default_factory=list)
    exit: tuple = SIDES
    enter: tuple = SIDES
    marker: str = "arrow"    # arrow, refused, none


@dataclass
class Diagram:
    name: str
    title: str
    caption: str
    alt: str
    nodes: dict
    groups: list
    edges: list
    legend: list
    equal_cols: bool = False
    equal_gaps: bool = False
    min_col: float = 0.0
    theme: Theme = THEME


def _sides(value) -> tuple:
    if value is None:
        return SIDES
    names = {"left": "L", "right": "R", "top": "T", "bottom": "B"}
    items = value if isinstance(value, list) else [value]
    return tuple(names[v] for v in items)


def load(path: Path, theme: Theme = THEME) -> Diagram:
    src = tomllib.loads(path.read_text(encoding="utf-8"))
    nodes = {}
    for n in src.get("node", []):
        lines = _lines(n.get("label"), TITLE) + _lines(n.get("sub"), SUB)
        node = Node(n["id"], lines, n["col"], n["row"], n.get("cols", 1), n.get("rows", 1),
                    n.get("role", "neutral"), n.get("shape", "box"), list(n.get("cells", [])),
                    n.get("stretch", False), n.get("align", "center"))
        if node.id in nodes:
            raise ValueError(f"{path.name}: two nodes called {node.id}")
        nodes[node.id] = node
    groups = []
    for g in src.get("group", []):
        grp = Group(g["id"], _lines(g.get("label"), GROUP), list(g["members"]), g.get("role", "neutral"),
                    g.get("title", "top"))
        for m in grp.members:
            if m not in nodes:
                raise ValueError(f"{path.name}: group {grp.id} names no node {m}")
            if nodes[m].group:
                raise ValueError(f"{path.name}: {m} is in two groups")
            nodes[m].group = grp.id
        groups.append(grp)
    edges = []
    ids = set(nodes) | {g.id for g in groups}
    for e in src.get("edge", []):
        edge = Edge(e["from"], e["to"], e.get("kind", "audio"), e.get("role"), _lines(e.get("label"), LABEL),
                    _sides(e.get("exit")), _sides(e.get("enter")), e.get("marker", "arrow"))
        for end in (edge.src, edge.dst):
            if end not in ids:
                raise ValueError(f"{path.name}: an edge names no node {end}")
        if edge.src == edge.dst:
            raise ValueError(f"{path.name}: {edge.src} -> itself: write it on the box instead")
        if edge.kind not in theme.kinds:
            raise ValueError(f"{path.name}: no kind {edge.kind}")
        edges.append(edge)
    legend = src.get("legend")
    if legend is None:
        used = {e.kind for e in edges}
        legend = [k for k in theme.kinds if k in used and theme.kinds[k].legend]
    for item in nodes.values():
        for line in item.lines:
            if metrics.missing(line.text):
                raise ValueError(f"{path.name}: no widths for {metrics.missing(line.text)}")
    return Diagram(path.stem, src["title"], src["caption"], src["alt"], nodes, groups, edges, legend,
                   src.get("equal_cols", False), src.get("equal_gaps", False), float(src.get("min_col", 0.0)),
                   theme)


# ---- geometry helpers -------------------------------------------------------------

@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def grow(self, d: float) -> "Rect":
        return Rect(self.x - d, self.y - d, self.w + 2 * d, self.h + 2 * d)

    def hits(self, o: "Rect") -> bool:
        return self.x < o.x1 and o.x < self.x1 and self.y < o.y1 and o.y < self.y1


def seg_hits_rect(a, b, r: Rect) -> bool:
    """An axis-aligned segment against a rectangle's open interior."""
    (x1, y1), (x2, y2) = a, b
    lo_x, hi_x = min(x1, x2), max(x1, x2)
    lo_y, hi_y = min(y1, y2), max(y1, y2)
    return lo_x < r.x1 and hi_x > r.x and lo_y < r.y1 and hi_y > r.y


def segments(points):
    return list(zip(points, points[1:]))


def crossings(pa, pb) -> int:
    """Proper crossings between two orthogonal polylines."""
    n = 0
    for a1, a2 in segments(pa):
        for b1, b2 in segments(pb):
            ha = a1[1] == a2[1]
            hb = b1[1] == b2[1]
            if ha == hb:
                continue
            h1, h2, v1, v2 = (a1, a2, b1, b2) if ha else (b1, b2, a1, a2)
            y, x = h1[1], v1[0]
            if min(h1[0], h2[0]) < x < max(h1[0], h2[0]) and min(v1[1], v2[1]) < y < max(v1[1], v2[1]):
                n += 1
    return n


def overlaps(pa, pb, tol: float = 3.0) -> float:
    """How far two polylines run along each other, closer than tol."""
    total = 0.0
    for a1, a2 in segments(pa):
        for b1, b2 in segments(pb):
            if a1[1] == a2[1] and b1[1] == b2[1] and abs(a1[1] - b1[1]) < tol:
                lo = max(min(a1[0], a2[0]), min(b1[0], b2[0]))
                hi = min(max(a1[0], a2[0]), max(b1[0], b2[0]))
                total += max(0.0, hi - lo)
            elif a1[0] == a2[0] and b1[0] == b2[0] and abs(a1[0] - b1[0]) < tol:
                lo = max(min(a1[1], a2[1]), min(b1[1], b2[1]))
                hi = min(max(a1[1], a2[1]), max(b1[1], b2[1]))
                total += max(0.0, hi - lo)
    return total


def simplify(points):
    out = []
    for p in points:
        p = (round(p[0], 3), round(p[1], 3))
        if out and abs(out[-1][0] - p[0]) < 1e-6 and abs(out[-1][1] - p[1]) < 1e-6:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            out.pop(i)
        else:
            i += 1
    return out


# ---- measuring -------------------------------------------------------------------

def measure(d: Diagram) -> None:
    for n in d.nodes.values():
        text_w = max((ln.width for ln in n.lines), default=0.0)
        text_h = sum(lh(ln.size) for ln in n.lines)
        if n.shape == "start":
            n.w = n.h = 12.0
            continue
        if n.shape == "cells":
            n.cell_w = max(max(metrics.text_width(c, *CELL) for c in n.cells) + 2 * CELL_PAD, 26.0)
            text_w = max(text_w, n.cell_w * len(n.cells))
            text_h += (5.0 if n.lines else 0.0) + CELL_H
        if n.shape == "note":
            n.w = text_w + PAD_X + 3.0
            n.h = text_h + 2 * 2.0
            continue
        n.w = text_w + 2 * PAD_X
        n.h = text_h + 2 * PAD_Y
        if n.shape == "state":
            n.w += 6.0


# ---- the grid --------------------------------------------------------------------

@dataclass
class Grid:
    cw: list
    rh: list
    band_x: list             # the room for lines in each column gap (C + 1 gaps)
    band_y: list
    pad_l: list              # a frame's room on each side of a gap
    pad_r: list
    pad_t: list
    pad_b: list
    flips: set = field(default_factory=set)   # edges that take the other place in a tie at a side

    def gap_x(self, i: int) -> float:
        return self.pad_l[i] + self.band_x[i] + self.pad_r[i]

    def gap_y(self, j: int) -> float:
        return self.pad_t[j] + self.band_y[j] + self.pad_b[j]

    def col_x(self, c: int) -> float:
        return sum(self.gap_x(i) for i in range(c + 1)) + sum(self.cw[:c])

    def row_y(self, r: int) -> float:
        return sum(self.gap_y(j) for j in range(r + 1)) + sum(self.rh[:r])

    def band_xs(self, i: int) -> tuple[float, float]:
        x0 = sum(self.gap_x(k) for k in range(i)) + sum(self.cw[:i]) + self.pad_l[i]
        return x0, x0 + self.band_x[i]

    def band_ys(self, j: int) -> tuple[float, float]:
        y0 = sum(self.gap_y(k) for k in range(j)) + sum(self.rh[:j]) + self.pad_t[j]
        return y0, y0 + self.band_y[j]


def make_grid(d: Diagram) -> Grid:
    C = max(n.col + n.cs for n in d.nodes.values())
    R = max(n.row + n.rs for n in d.nodes.values())
    cw = [d.min_col] * C
    rh = [0.0] * R
    for n in d.nodes.values():
        if n.cs == 1:
            cw[n.col] = max(cw[n.col], n.w)
        if n.rs == 1:
            rh[n.row] = max(rh[n.row], n.h)
    if d.equal_cols:
        cw = [max(cw)] * C
    pad_l, pad_r = [0.0] * (C + 1), [0.0] * (C + 1)
    pad_t, pad_b = [0.0] * (R + 1), [0.0] * (R + 1)
    title_h = lh(GROUP[0]) + 3.0
    for g in d.groups:
        ms = [d.nodes[m] for m in g.members]
        g.c0, g.c1 = min(m.col for m in ms), max(m.col + m.cs - 1 for m in ms)
        g.r0, g.r1 = min(m.row for m in ms), max(m.row + m.rs - 1 for m in ms)
        pad_r[g.c0] = max(pad_r[g.c0], GPAD + FRAME_GAP)
        pad_l[g.c1 + 1] = max(pad_l[g.c1 + 1], GPAD + FRAME_GAP)
        top, bottom = (title_h, 0.0) if g.title_at == "top" else (0.0, title_h)
        pad_b[g.r0] = max(pad_b[g.r0], GPAD + top + FRAME_GAP)
        pad_t[g.r1 + 1] = max(pad_t[g.r1 + 1], GPAD + bottom + FRAME_GAP)
    grid = Grid(cw, rh, [BAND_X] * (C + 1), [BAND_Y] * (R + 1), pad_l, pad_r, pad_t, pad_b)
    # Spanning boxes and group titles widen the columns and rows they cover.
    for _ in range(3):
        for n in d.nodes.values():
            if n.cs > 1:
                have = grid.col_x(n.col + n.cs - 1) + cw[n.col + n.cs - 1] - grid.col_x(n.col)
                if have < n.w:
                    for c in range(n.col, n.col + n.cs):
                        cw[c] += (n.w - have) / n.cs
            if n.rs > 1:
                have = grid.row_y(n.row + n.rs - 1) + rh[n.row + n.rs - 1] - grid.row_y(n.row)
                if have < n.h:
                    for r in range(n.row, n.row + n.rs):
                        rh[r] += (n.h - have) / n.rs
        for g in d.groups:
            need = max(ln.width for ln in g.label) + 2 * 8.0 - 2 * GPAD if g.label else 0.0
            have = grid.col_x(g.c1) + cw[g.c1] - grid.col_x(g.c0)
            if have < need:
                for c in range(g.c0, g.c1 + 1):
                    cw[c] += (need - have) / (g.c1 - g.c0 + 1)
        if d.equal_cols:
            cw[:] = [max(cw)] * C
    return grid


@dataclass
class Placed:
    rects: dict              # node or group id -> Rect (a group's frame)
    title: dict              # group id -> Rect of its title band
    grid: Grid


def place(d: Diagram, grid: Grid) -> Placed:
    rects, titles = {}, {}
    for n in d.nodes.values():
        x0 = grid.col_x(n.col)
        x1 = grid.col_x(n.col + n.cs - 1) + grid.cw[n.col + n.cs - 1]
        y0 = grid.row_y(n.row)
        y1 = grid.row_y(n.row + n.rs - 1) + grid.rh[n.row + n.rs - 1]
        w = (x1 - x0) if n.stretch else n.w
        h = (y1 - y0) if n.stretch else n.h
        x = {"left": x0, "right": x1 - w}.get(n.align, x0 + (x1 - x0 - w) / 2)
        rects[n.id] = Rect(x, y0 + (y1 - y0 - h) / 2, w, h)
    title_h = lh(GROUP[0]) + 3.0
    for g in d.groups:
        x0 = grid.col_x(g.c0) - GPAD
        x1 = grid.col_x(g.c1) + grid.cw[g.c1] + GPAD
        top, bottom = (title_h, 0.0) if g.title_at == "top" else (0.0, title_h)
        y0 = grid.row_y(g.r0) - GPAD - top
        y1 = grid.row_y(g.r1) + grid.rh[g.r1] + GPAD + bottom
        rects[g.id] = Rect(x0, y0, x1 - x0, y1 - y0)
        words = max((ln.width for ln in g.label), default=0.0)
        height = sum(lh(ln.size) for ln in g.label)
        ty = y0 + 4.0 if g.title_at == "top" else y1 - 4.0 - height
        titles[g.id] = Rect(x0 + 8.0, ty, words, height)
    return Placed(rects, titles, grid)


# ---- routing ------------------------------------------------------------------------

@dataclass(frozen=True)
class Route:
    shape: str               # HVH, VHV, HV, VH
    sa: str
    sb: str
    gap: int | None          # the column gap (HVH) or row gap (VHV) its middle run takes


def side_point(r: Rect, side: str, t: float | None = None):
    """A point on side `side` of r, at coordinate t along it (its middle if None)."""
    if side in ("L", "R"):
        x = r.x if side == "L" else r.x1
        return (x, r.cy if t is None else t)
    y = r.y if side == "T" else r.y1
    return (r.cx if t is None else t, y)


def gap_range(sa: str, sb: str, a0: int, a1: int, b0: int, b1: int, count: int) -> tuple[int, int]:
    """The gaps (0..count) a middle run may take between a box covering
    columns a0..a1, left by side sa (L or R), and one covering b0..b1, entered
    by side sb. Gap g lies left of column g."""
    lo, hi = 0, count
    if sa == "R":
        lo = max(lo, a1 + 1)
    else:
        hi = min(hi, a0)
    if sb == "L":
        hi = min(hi, b0)
    else:
        lo = max(lo, b1 + 1)
    return lo, hi


def realise(route: Route, pa, pb, track: float | None):
    if route.shape == "HVH":
        pts = [pa, (track, pa[1]), (track, pb[1]), pb]
    elif route.shape == "VHV":
        pts = [pa, (pa[0], track), (pb[0], track), pb]
    elif route.shape == "HV":
        pts = [pa, (pb[0], pa[1]), pb]
    else:
        pts = [pa, (pa[0], pb[1]), pb]
    return pts


def leaves(points, side: str, length: float) -> bool:
    """The first run goes out of side `side` for at least `length`."""
    (x0, y0), (x1, y1) = points[0], points[1]
    dx, dy = OUT[side]
    return (x1 - x0) * dx + (y1 - y0) * dy >= length - 1e-6 and ((dx and y1 == y0) or (dy and x1 == x0))


def enters(points, side: str, length: float) -> bool:
    (x0, y0), (x1, y1) = points[-2], points[-1]
    dx, dy = OUT[side]
    return (x0 - x1) * dx + (y0 - y1) * dy >= length - 1e-6 and ((dx and y1 == y0) or (dy and x1 == x0))


class Router:
    def __init__(self, d: Diagram, placed: Placed):
        self.d = d
        self.p = placed
        self.done = []       # polylines already routed

    def obstacles(self, edge: Edge):
        """What a route must keep CLEAR of: every box but its ends, and the
        frames' titles."""
        out = []
        ends = {edge.src, edge.dst}
        for nid, r in self.p.rects.items():
            if nid in self.d.nodes and nid not in ends:
                out.append(r.grow(CLEAR))
        for g in self.d.groups:
            if g.id not in ends and g.label:
                out.append(self.p.title[g.id].grow(CLEAR))
        return out

    def frames(self, edge: Edge):
        """Frames this edge has no business crossing: those around neither end."""
        inside = set()
        for end in (edge.src, edge.dst):
            n = self.d.nodes.get(end)
            if n and n.group:
                inside.add(n.group)
        return [self.p.rects[g.id] for g in self.d.groups if g.id not in inside
                and g.id not in (edge.src, edge.dst)]

    def span(self, ident: str):
        """The columns and rows a box or a frame covers."""
        n = self.d.nodes.get(ident)
        if n:
            return n.col, n.col + n.cs - 1, n.row, n.row + n.rs - 1
        g = next(g for g in self.d.groups if g.id == ident)
        return g.c0, g.c1, g.r0, g.r1

    def candidates(self, edge: Edge):
        grid = self.p.grid
        C, R = len(grid.cw), len(grid.rh)
        a, b = self.span(edge.src), self.span(edge.dst)
        for sa in edge.exit:
            for sb in edge.enter:
                if sa in "LR" and sb in "LR":
                    lo, hi = gap_range(sa, sb, a[0], a[1], b[0], b[1], C)
                    for g in range(lo, hi + 1):
                        yield Route("HVH", sa, sb, g)
                elif sa in "TB" and sb in "TB":
                    lo, hi = gap_range({"T": "L", "B": "R"}[sa], {"T": "L", "B": "R"}[sb],
                                       a[2], a[3], b[2], b[3], R)
                    for g in range(lo, hi + 1):
                        yield Route("VHV", sa, sb, g)
                else:
                    yield Route("HV" if sa in "LR" else "VH", sa, sb, None)

    def provisional(self, edge: Edge, route: Route):
        ra, rb = self.p.rects[edge.src], self.p.rects[edge.dst]
        ta = tb = None
        if route.shape in ("HVH", "VHV"):
            # facing sides that overlap: try the straight line between them
            along_x = route.shape == "VHV"
            lo = max(ra.x, rb.x) if along_x else max(ra.y, rb.y)
            hi = min(ra.x1, rb.x1) if along_x else min(ra.y1, rb.y1)
            if lo + PORT_END <= hi - PORT_END:
                ta = tb = straight_target(ra, rb, along_x)
        pa, pb = side_point(ra, route.sa, ta), side_point(rb, route.sb, tb)
        track = None
        if route.shape == "HVH":
            track = sum(self.p.grid.band_xs(route.gap)) / 2
        elif route.shape == "VHV":
            track = sum(self.p.grid.band_ys(route.gap)) / 2
        return simplify(realise(route, pa, pb, track))

    def cost(self, edge: Edge, route: Route, pts) -> float | None:
        if len(pts) < 2:
            return None
        if not leaves(pts, route.sa, 2.0) or not enters(pts, route.sb, 2.0):
            return None
        ra, rb = self.p.rects[edge.src], self.p.rects[edge.dst]
        for a, b in segments(pts):
            for r in (ra.grow(-1.0), rb.grow(-1.0)):
                if seg_hits_rect(a, b, r):
                    return None
            for r in self.obstacles(edge):
                if seg_hits_rect(a, b, r):
                    return None
        length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in segments(pts))
        bends = len(pts) - 2
        c = length + 28.0 * bends
        if route.gap is not None and len(pts) == 2:
            # a straight line: keep its gap next to where it arrives
            sb = self.span(edge.dst)
            near = {"L": sb[0], "R": sb[1] + 1, "T": sb[2], "B": sb[3] + 1}[route.sb]
            c += 0.01 * abs(route.gap - near)
        for fr in self.frames(edge):
            border = [(fr.x, fr.y), (fr.x1, fr.y), (fr.x1, fr.y1), (fr.x, fr.y1), (fr.x, fr.y)]
            c += 220.0 * crossings(pts, border)
            for a, b in segments(pts):
                if seg_hits_rect(a, b, fr.grow(-GPAD + 2)):
                    c += 400.0
        for other in self.done:
            c += 45.0 * crossings(pts, other["pts"])
            ov = overlaps(pts, other["pts"])
            if ov > 3.0:
                shared = (route.shape == other["route"].shape and route.gap == other["route"].gap
                          and route.shape in ("HVH", "VHV"))
                # two straight lines between the same two boxes: the ports
                # will set them side by side
                pair = (len(pts) == 2 and len(other["pts"]) == 2 and
                        {edge.src, edge.dst} == other["ends"])
                c += (0.0 if pair else 4.0 if shared else 60.0) * ov
        return c

    def route(self, edge: Edge) -> Route:
        best = None
        for route in self.candidates(edge):
            pts = self.provisional(edge, route)
            c = self.cost(edge, route, pts)
            if c is not None and (best is None or c < best[0] - 1e-9):
                best = (c, route, pts)
        if best is None:
            raise ValueError(f"{self.d.name}: no clear route from {edge.src} to {edge.dst}; "
                             "move a box, or loosen the edge's exit or enter")
        self.done.append({"route": best[1], "pts": best[2], "ends": {edge.src, edge.dst}})
        return best[1]


def choose_routes(d: Diagram, placed: Placed) -> list:
    router = Router(d, placed)
    order = sorted(range(len(d.edges)), key=lambda i: (
        abs(placed.rects[d.edges[i].src].cx - placed.rects[d.edges[i].dst].cx) +
        abs(placed.rects[d.edges[i].src].cy - placed.rects[d.edges[i].dst].cy), i))
    routes = [None] * len(d.edges)
    for i in order:
        routes[i] = router.route(d.edges[i])
    routes_in_order = [routes[i] for i in order]
    # A gap that holds no middle run needs only the room for a line across it
    # (its run out of one box and its arrowhead), or a sliver if none crosses.
    grid = placed.grid
    across = STUB + ARROW_AUDIO[0] + 10.0
    for axis, band, pads, spans in (
            ("x", grid.band_x, (grid.pad_l, grid.pad_r), [grid.band_xs(g) for g in range(len(grid.band_x))]),
            ("y", grid.band_y, (grid.pad_t, grid.pad_b), [grid.band_ys(g) for g in range(len(grid.band_y))])):
        shape = "HVH" if axis == "x" else "VHV"
        k = 0 if axis == "x" else 1
        for g, (lo, hi) in enumerate(spans):
            if any(r.shape == shape and r.gap == g and len(done["pts"]) > 2
                   for r, done in zip(routes_in_order, router.done)):
                continue
            if g == 0 or g == len(spans) - 1:
                band[g] = 0.0           # the outside: room only for a run that goes round
                continue
            need = SLIVER
            for i, done in zip(order, router.done):
                if any(min(a[k], b[k]) < hi and max(a[k], b[k]) > lo for a, b in segments(done["pts"])):
                    # a refused line keeps room for its cross and some line before it
                    room = across + (20.0 if d.edges[i].marker == "refused" else 0.0)
                    need = max(need, room - pads[0][g] - pads[1][g])
            band[g] = need
    return routes


# ---- ports and tracks ------------------------------------------------------------

def assign_ports(d: Diagram, placed: Placed, routes: list, prev: dict | None, flips=frozenset()):
    """Where each edge meets each of its boxes: spread along the side, each as
    near as it can be to where its line comes from, in an order that keeps
    lines from crossing at the box."""
    att = {}
    for i, (e, r) in enumerate(zip(d.edges, routes)):
        att.setdefault((e.src, r.sa), []).append((i, "a"))
        att.setdefault((e.dst, r.sb), []).append((i, "b"))
    ports = {}
    for (nid, side), items in att.items():
        rect = placed.rects[nid]
        along_x = side in "TB"
        lo, hi = (rect.x, rect.x1) if along_x else (rect.y, rect.y1)
        mid = (lo + hi) / 2
        keyed = []
        for i, end in items:
            e, r = d.edges[i], routes[i]
            other = placed.rects[e.dst if end == "a" else e.src]
            far = other.cx if along_x else other.cy
            want = mid
            facing = (r.shape == "HVH" and not along_x) or (r.shape == "VHV" and along_x)
            o_lo, o_hi = (other.x, other.x1) if along_x else (other.y, other.y1)
            straight = facing and max(lo, o_lo) + PORT_END <= min(hi, o_hi) - PORT_END
            if straight:
                want = straight_target(rect, other, along_x)
                if prev and (i, "b" if end == "a" else "a") in prev:
                    want = prev[(i, "b" if end == "a" else "a")]
            elif facing:
                want = far          # the end of the side nearest where it goes
            # order along the side by where each line is headed, so that
            # lines leaving one side do not cross at the box
            key = (want if straight else far, i in flips, i)
            keyed.append((key, i, end, want))
        keyed.sort()
        n = len(keyed)
        lo_p, hi_p = lo + PORT_END, hi - PORT_END
        if n * PORT_GAP > hi_p - lo_p + PORT_GAP or hi_p < lo_p:
            pos = [lo + (hi - lo) * (k + 1) / (n + 1) for k in range(n)]
        else:
            pos = [min(max(w, lo_p), hi_p) for _, _, _, w in keyed]
            # two lines matching ports on a smaller box may sit closer
            gaps = [PORT_GAP] + [max(PORT_GAP_MIN, min(PORT_GAP, keyed[k][3] - keyed[k - 1][3]))
                                 if keyed[k][3] > keyed[k - 1][3] else PORT_GAP for k in range(1, n)]
            for k in range(1, n):
                pos[k] = max(pos[k], pos[k - 1] + gaps[k])
            if pos[-1] > hi_p:
                pos[-1] = hi_p
                for k in range(n - 2, -1, -1):
                    pos[k] = min(pos[k], pos[k + 1] - gaps[k + 1])
        for (key, i, end, _w), p in zip(keyed, pos):
            ports[(i, end)] = p
    return ports


def straight_target(a: Rect, b: Rect, along_x: bool) -> float:
    """Where a straight line between facing sides of a and b best runs: the
    middle of the smaller side, kept inside both."""
    if along_x:
        lo, hi = max(a.x, b.x) + PORT_END, min(a.x1, b.x1) - PORT_END
        mid = a.cx if a.w <= b.w else b.cx
    else:
        lo, hi = max(a.y, b.y) + PORT_END, min(a.y1, b.y1) - PORT_END
        mid = a.cy if a.h <= b.h else b.cy
    return min(max(mid, lo), hi) if lo <= hi else mid


def end_points(d: Diagram, placed: Placed, routes: list, ports: dict):
    out = []
    for i, (e, r) in enumerate(zip(d.edges, routes)):
        pa = side_point(placed.rects[e.src], r.sa, ports[(i, "a")])
        pb = side_point(placed.rects[e.dst], r.sb, ports[(i, "b")])
        out.append((pa, pb))
    return out


def assign_tracks(d: Diagram, placed: Placed, routes: list, ends: list):
    """Gives each middle run in a gap a track, so runs that share a gap never
    lie on each other, in the order that crosses the fewest legs. Returns the
    tracks and each gap's needed band."""
    grid = placed.grid
    by_gap = {}
    for i, r in enumerate(routes):
        if r.shape not in ("HVH", "VHV"):
            continue
        pa, pb = ends[i]
        if r.shape == "HVH":
            a, b = pa[1], pb[1]
        else:
            a, b = pa[0], pb[0]
        if abs(a - b) < 0.5:
            continue
        by_gap.setdefault((r.shape, r.gap), []).append((i, min(a, b), max(a, b)))
    tracks, need = {}, {}
    for (shape, gap), segs in sorted(by_gap.items()):
        lo, hi = grid.band_xs(gap) if shape == "HVH" else grid.band_ys(gap)
        # groups of runs that overlap along the gap, each needing its own track
        segs.sort(key=lambda s: (s[1], s[2], s[0]))
        comps, cur, cur_hi = [], [], None
        for s in segs:
            if cur and s[1] > cur_hi + TRACK:
                comps.append(cur)
                cur, cur_hi = [], None
            cur.append(s)
            cur_hi = s[2] if cur_hi is None else max(cur_hi, s[2])
        if cur:
            comps.append(cur)
        width = 0
        for comp in comps:
            order = best_order(ends, comp, shape, (lo + hi) / 2)
            k = len(order)
            width = max(width, k)
            for slot, i in enumerate(order):
                tracks[i] = slot - (k - 1) / 2       # in TRACKs from the band's middle
        need[(shape, gap)] = max(BAND_X if shape == "HVH" else BAND_Y, (width - 1) * TRACK + 2 * TRACK_EDGE)
    coords = {}
    for i, r in enumerate(routes):
        if r.shape not in ("HVH", "VHV"):
            continue
        lo, hi = grid.band_xs(r.gap) if r.shape == "HVH" else grid.band_ys(r.gap)
        coords[i] = (lo + hi) / 2 + tracks.get(i, 0.0) * TRACK
    return coords, need


def best_order(ends, comp, shape, mid):
    """The track order, across the gap, in which the runs' legs cross the
    fewest other runs (every order is tried for up to six runs)."""
    ids = [s[0] for s in comp]
    if len(ids) == 1:
        return ids
    span = {s[0]: (s[1], s[2]) for s in comp}
    legs = {}
    for i in ids:
        legs[i] = []
        for p in ends[i]:
            along, across = (p[1], p[0]) if shape == "HVH" else (p[0], p[1])
            legs[i].append((along, 1 if across > mid else -1))
    perms = itertools.permutations(ids) if len(ids) <= 6 else [tuple(ids)]
    best = None
    for perm in perms:
        pos = {i: k for k, i in enumerate(perm)}
        cost = 0
        for i in ids:
            for along, sign in legs[i]:
                for j in ids:
                    lo, hi = span[j]
                    if j != i and lo < along < hi and (pos[j] - pos[i]) * sign > 0:
                        cost += 1
                    # two legs on one line from opposite sides must not meet
                    for along_j, sign_j in (legs[j] if j != i else ()):
                        if abs(along - along_j) < 2.0 and sign < 0 < sign_j and pos[j] < pos[i]:
                            cost += 100
        if best is None or cost < best[0]:
            best = (cost, perm)
    return list(best[1])


# ---- labels ---------------------------------------------------------------------

@dataclass
class Placement:
    rect: Rect
    lines: list
    edge: int


def label_size(lines) -> tuple[float, float]:
    return max(ln.width for ln in lines), sum(lh(ln.size) for ln in lines)


def label_spots(pts, w: float, h: float):
    """Where a label of w x h may sit beside a polyline, best first."""
    segs = sorted(enumerate(segments(pts)), key=lambda s: -(abs(s[1][0][0] - s[1][1][0]) +
                                                            abs(s[1][0][1] - s[1][1][1])))
    for _k, (a, b) in segs:
        if a[1] == b[1]:
            x0, x1 = sorted((a[0], b[0]))
            y = a[1]
            for frac in (0.5, 0.3, 0.7, 0.15, 0.85, 0.0, 1.0):
                cx = x0 + (x1 - x0) * frac
                yield Rect(cx - w / 2, y - LGAP - h, w, h)
                yield Rect(cx - w / 2, y + LGAP, w, h)
        else:
            y0, y1 = sorted((a[1], b[1]))
            x = a[0]
            for frac in (0.5, 0.3, 0.7, 0.15, 0.85):
                cy = y0 + (y1 - y0) * frac
                yield Rect(x + LGAP + 1.0, cy - h / 2, w, h)
                yield Rect(x - LGAP - 1.0 - w, cy - h / 2, w, h)


# ---- the layout ---------------------------------------------------------------------

@dataclass
class Layout:
    d: Diagram
    placed: Placed
    routes: list
    paths: list
    labels: list


def edge_width(d: Diagram, e: Edge) -> float:
    return d.theme.kinds[e.kind].width


def settle(d: Diagram, grid: Grid, routes: list):
    """One layout on this grid: ports, tracks (widening a gap that needs more
    tracks), lines and labels. Returns the Layout, or None and the edge in
    trouble with the lines as they stand."""
    for _round in range(MAX_ROUNDS):
        if d.equal_gaps and len(grid.band_x) > 2:
            widest = max(grid.gap_x(g) for g in range(1, len(grid.band_x) - 1))
            for g in range(1, len(grid.band_x) - 1):
                grid.band_x[g] += widest - grid.gap_x(g)
        placed = place(d, grid)
        ports = assign_ports(d, placed, routes, None, grid.flips)
        ends = end_points(d, placed, routes, ports)
        for _pass in range(3):
            # each straight line's two ends move towards each other
            ports = assign_ports(d, placed, routes, {
                (i, "a"): (ends[i][0][1] if routes[i].sa in "LR" else ends[i][0][0]) for i in range(len(ends))} | {
                (i, "b"): (ends[i][1][1] if routes[i].sb in "LR" else ends[i][1][0]) for i in range(len(ends))},
                grid.flips)
            ends = end_points(d, placed, routes, ports)
        coords, need = assign_tracks(d, placed, routes, ends)
        grew = False
        for (shape, gap), want in need.items():
            band = grid.band_x if shape == "HVH" else grid.band_y
            if band[gap] < want - 1e-6:
                band[gap] = want
                grew = True
        if grew:
            continue
        paths = [simplify(realise(r, a, b, coords.get(i))) for i, (r, (a, b)) in enumerate(zip(routes, ends))]
        bad = route_problems(d, placed, paths)
        if bad:
            return None, (bad[0][0], bad[0][1], paths)
        labels, stuck = place_labels(d, placed, paths)
        if stuck is None:
            return Layout(d, placed, routes, paths, labels), None
        return None, (stuck, f"no room for the label of {d.edges[stuck].src} -> {d.edges[stuck].dst}", paths)
    raise ValueError(f"{d.name}: the tracks did not settle")


def apply_growth(d: Diagram, grid: Grid, option) -> None:
    axis, g, amount = option
    amount = max(amount, 4.0)
    if axis == "flip":
        grid.flips ^= {g}
    elif axis == "x":
        grid.band_x[g] += amount
    elif axis == "y":
        grid.band_y[g] += amount
    elif axis == "row":
        grid.rh[g] += amount
    else:
        grid.cw[g] += amount
        if d.equal_cols:
            grid.cw[:] = [max(grid.cw)] * len(grid.cw)


def layout(d: Diagram) -> Layout:
    """Lays a diagram out. When a label has no room, or a line comes too near
    a box, it tries each way of making room in turn (a gap, a row, a column)
    and keeps the first that helps."""
    measure(d)
    grid = make_grid(d)
    routes = choose_routes(d, place(d, grid))
    tried: dict = {}
    for _round in range(MAX_ROUNDS):
        result, trouble = settle(d, grid, routes)
        if result:
            return result
        i, why, paths = trouble
        options = growth_options(d, grid, routes, paths, i)
        chosen = None
        for axis, g, amount in options:
            for share in ((1.0,) if axis == "flip" else (0.25, 0.5, 1.0)):
                opt = (axis, g, amount * share)
                trial = copy.deepcopy(grid)
                apply_growth(d, trial, opt)
                res2, trouble2 = settle(d, trial, routes)
                if res2 is not None or trouble2[0] != i or trouble2[1] != why:
                    chosen = opt
                    break
            if chosen:
                break
        if chosen is None:
            k = tried.get(i, 0)
            tried[i] = k + 1
            if not options or k >= 3 * len(options):
                raise ValueError(f"{d.name}: {why}")
            chosen = options[k % len(options)]
        apply_growth(d, grid, chosen)
    raise ValueError(f"{d.name}: the layout did not settle in {MAX_ROUNDS} rounds")


def route_problems(d: Diagram, placed: Placed, paths: list):
    """Runs that, now ports and tracks are known, come too close to a box or
    lie along another edge's run."""
    out = []
    for i, (e, pts) in enumerate(zip(d.edges, paths)):
        ends = {e.src, e.dst}
        first = abs(pts[1][0] - pts[0][0]) + abs(pts[1][1] - pts[0][1])
        last = abs(pts[-1][0] - pts[-2][0]) + abs(pts[-1][1] - pts[-2][1])
        arrow = (ARROW_AUDIO if e.kind == "audio" else ARROW)[0] if e.marker == "arrow" else 6.0
        if first < STUB - 1e-6 or last < arrow + STUB / 2 - 1e-6:
            out.append((i, f"{e.src} -> {e.dst} has too short a run at one end"))
        for a, b in segments(pts):
            for nid, r in placed.rects.items():
                if nid in d.nodes and nid not in ends and seg_hits_rect(a, b, r.grow(CLEAR - 1)):
                    out.append((i, f"{e.src} -> {e.dst} passes {nid}"))
        for j in range(i):
            if overlaps(pts, paths[j], 2.0) > 2.0:
                out.append((i, f"{e.src} -> {e.dst} runs along {d.edges[j].src} -> {d.edges[j].dst}"))
    return out


def growth_options(d: Diagram, grid: Grid, routes: list, paths: list, i: int) -> list:
    """Ways to make room for edge i's label (or line), cheapest first: the gap
    its middle run takes, the gaps and rows its runs cross or lie in, then the
    columns."""
    r = routes[i]
    w, h = label_size(d.edges[i].label) if d.edges[i].label else (TRACK, TRACK)
    options = []
    pts = paths[i]
    xs = [grid.band_xs(g) for g in range(len(grid.band_x))]
    ys = [grid.band_ys(g) for g in range(len(grid.band_y))]
    rows = [(grid.row_y(k), grid.row_y(k) + grid.rh[k]) for k in range(len(grid.rh))]
    cols = [(grid.col_x(k), grid.col_x(k) + grid.cw[k]) for k in range(len(grid.cw))]
    if r.shape == "HVH":
        options.append(("x", r.gap, w + LGAP + LPAD))
    if r.shape == "VHV":
        options.append(("y", r.gap, h + LGAP + LPAD))
    later = []
    for a, b in sorted(segments(pts), key=lambda s: -(abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))):
        if a[1] == b[1]:
            lo, hi = sorted((a[0], b[0]))
            for g, (x0, x1) in enumerate(xs):
                if lo < x1 + 1 and hi > x0 - 1 and 0 < g < len(xs) - 1:
                    options.append(("x", g, max(TRACK, w + 2 * LPAD - (hi - lo))))
            for g, (y0, y1) in enumerate(ys):
                if y0 - 1 <= a[1] <= y1 + 1:
                    options.append(("y", g, h + LGAP + LPAD))
            for k, (y0, y1) in enumerate(rows):
                if y0 <= a[1] <= y1:
                    options.append(("row", k, 2 * (h + LGAP + LPAD)))
        else:
            lo, hi = sorted((a[1], b[1]))
            for g, (y0, y1) in enumerate(ys):
                if lo < y1 + 1 and hi > y0 - 1 and 0 < g < len(ys) - 1:
                    options.append(("y", g, max(TRACK, h + 2 * LPAD - (hi - lo))))
            for g, (x0, x1) in enumerate(xs):
                if x0 - 1 <= a[0] <= x1 + 1:
                    options.append(("x", g, w + LGAP + LPAD))
            for k, (x0, x1) in enumerate(cols):
                if x0 <= a[0] <= x1:
                    later.append(("col", k, 2 * (w + LGAP + LPAD)))
    out = []
    # first, for free: swap places with a line that shares a side and a direction
    e = d.edges[i]
    mine = {(e.src, r.sa), (e.dst, r.sb)}
    shared = [j for j, (f, rj) in enumerate(zip(d.edges, routes))
              if j != i and mine & {(f.src, rj.sa), (f.dst, rj.sb)}]
    if shared and not ({i} | set(shared)) & grid.flips:
        out.append(("flip", i, 0.0))
    for o in options + later:
        if o not in out:
            out.append(o)
    return out


def arrow_points(d: Diagram, e: Edge, pts):
    """The arrowhead (or the refusal's cross) at an edge's end, and where its
    line stops."""
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    length = abs(x1 - x0) + abs(y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    al, aw = ARROW_AUDIO if e.kind == "audio" else ARROW
    if e.marker == "arrow":
        base = (x1 - ux * al, y1 - uy * al)
        tri = [(x1, y1), (base[0] - uy * aw, base[1] + ux * aw), (base[0] + uy * aw, base[1] - ux * aw)]
        return "arrow", tri, (x1 - ux * (al - 1.0), y1 - uy * (al - 1.0))
    if e.marker == "refused":
        c = (x1 - ux * 9.0, y1 - uy * 9.0)
        s = CROSS
        return "cross", [((c[0] - s, c[1] - s), (c[0] + s, c[1] + s)),
                         ((c[0] - s, c[1] + s), (c[0] + s, c[1] - s))], c
    return "none", [], (x1, y1)


def place_labels(d: Diagram, placed: Placed, paths: list):
    fixed = []
    for nid, r in placed.rects.items():
        if nid in d.nodes:
            fixed.append(r.grow(LPAD))
    for g in d.groups:
        fr = placed.rects[g.id]
        t = 1.0
        fixed += [Rect(fr.x - LPAD, fr.y - LPAD, fr.w + 2 * LPAD, t + 2 * LPAD),
                  Rect(fr.x - LPAD, fr.y1 - LPAD, fr.w + 2 * LPAD, t + 2 * LPAD),
                  Rect(fr.x - LPAD, fr.y - LPAD, t + 2 * LPAD, fr.h + 2 * LPAD),
                  Rect(fr.x1 - LPAD, fr.y - LPAD, t + 2 * LPAD, fr.h + 2 * LPAD)]
        if g.label:
            fixed.append(placed.title[g.id].grow(LPAD))
    lines, own = [], []
    for i, (e, pts) in enumerate(zip(d.edges, paths)):
        half = edge_width(d, e) / 2
        for a, b in segments(pts):
            lines.append((i, Rect(min(a[0], b[0]) - half, min(a[1], b[1]) - half,
                                  abs(a[0] - b[0]) + 2 * half, abs(a[1] - b[1]) + 2 * half)))
            own.append((i, Rect(min(a[0], b[0]), min(a[1], b[1]), abs(a[0] - b[0]), abs(a[1] - b[1]))))
        kind, shape, _stop = arrow_points(d, e, pts)
        if kind == "arrow":
            xs, ys = [p[0] for p in shape], [p[1] for p in shape]
            lines.append((i, Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))))
        elif kind == "cross":
            c = _stop
            lines.append((i, Rect(c[0] - 5, c[1] - 5, 10, 10)))
    placed_labels = []
    for i, (e, pts) in enumerate(zip(d.edges, paths)):
        if not e.label:
            continue
        w, h = label_size(e.label)
        spot = None
        for cand in label_spots(pts, w, h):
            box = cand.grow(LPAD)
            if any(box.hits(r) for r in fixed):
                continue
            if any(box.hits(r) for j, r in lines if j != i):
                continue
            if any(cand.grow(LGAP - 0.5).hits(r) for j, r in own if j == i):
                continue
            if any(box.hits(r) for j, r in lines if j == i and r.w <= 12 and r.h <= 12):
                continue
            if any(box.hits(p.rect.grow(LPAD)) for p in placed_labels):
                continue
            spot = cand
            break
        if spot is None:
            return placed_labels, i
        placed_labels.append(Placement(spot, e.label, i))
    return placed_labels, None


# ---- drawing --------------------------------------------------------------------------

def text_el(x: float, baseline: float, line: Line, colour: str, anchor: str, theme: Theme, **data) -> str:
    extra = "".join(f" data-{k}='{escape(str(v))}'" for k, v in data.items())
    return (f"<text x='{_f(x)}' y='{_f(baseline)}' fill='{colour}' font-family='{theme.font}' "
            f"font-size='{_f(line.size)}' font-weight='{line.weight}' text-anchor='{anchor}'{extra}>"
            f"{escape(line.text)}</text>")


def block(lines, top: float):
    """Baselines for lines stacked from `top`."""
    out, y = [], top
    for ln in lines:
        h = lh(ln.size)
        out.append(y + (h - (metrics.ASCENT + metrics.DESCENT) * ln.size) / 2 + metrics.ASCENT * ln.size)
        y += h
    return out


def legend_items(d: Diagram):
    theme = d.theme
    for item in d.legend:
        if isinstance(item, str):
            yield ("kind", item, theme.kinds[item].legend)
        elif "kind" in item:
            yield ("kind", item["kind"], item.get("label", theme.kinds[item["kind"]].legend))
        else:
            yield ("role", item["role"], item["label"])


def render(lay: Layout) -> str:
    d, theme, placed = lay.d, lay.d.theme, lay.placed
    body = []
    # frames
    for g in d.groups:
        fr = placed.rects[g.id]
        role = theme.roles[g.role]
        body.append(f"<rect data-kind='group' data-id='{g.id}' x='{_f(fr.x)}' y='{_f(fr.y)}' "
                    f"width='{_f(fr.w)}' height='{_f(fr.h)}' rx='8' fill='{role.wash}' "
                    f"stroke='{role.stroke}' stroke-width='1.3'/>")
        for ln, base in zip(g.label, block(g.label, placed.title[g.id].y)):
            body.append(text_el(fr.x + 8.0, base, ln, role.text, "start", theme, owner=g.id))
    # edges
    marks = []
    for i, (e, pts) in enumerate(zip(d.edges, lay.paths)):
        k = theme.kinds[e.kind]
        colour = theme.roles[e.role or k.role].stroke
        kind, shape, stop = arrow_points(d, e, pts)
        drawn = pts[:-1] + [stop]
        dpath = "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in drawn)
        dash = f" stroke-dasharray='{k.dash}'" if k.dash else ""
        body.append(f"<path data-kind='edge' data-id='e{i}' data-from='{e.src}' data-to='{e.dst}' "
                    f"d='{dpath}' fill='none' stroke='{colour}' stroke-width='{_f(k.width)}'{dash} "
                    f"stroke-linecap='{k.cap}' stroke-linejoin='round'/>")
        if kind == "arrow":
            tri = " L".join(f"{_f(x)} {_f(y)}" for x, y in shape)
            marks.append(f"<path data-kind='arrow' data-id='e{i}' d='M{tri} Z' fill='{colour}'/>")
        elif kind == "cross":
            for (a, b) in shape:
                marks.append(f"<path data-kind='arrow' data-id='e{i}' d='M{_f(a[0])} {_f(a[1])} "
                             f"L{_f(b[0])} {_f(b[1])}' stroke='{colour}' stroke-width='1.8' "
                             f"stroke-linecap='round'/>")
    body += marks
    # boxes
    for n in d.nodes.values():
        r = placed.rects[n.id]
        role = theme.roles[n.role]
        grp = f" data-group='{n.group}'" if n.group else ""
        if n.shape == "start":
            body.append(f"<circle data-kind='node' data-id='{n.id}'{grp} cx='{_f(r.cx)}' cy='{_f(r.cy)}' "
                        f"r='{_f(r.w / 2)}' fill='{theme.ink}'/>")
            continue
        if n.shape == "note":
            body.append(f"<rect data-kind='node' data-id='{n.id}'{grp} x='{_f(r.x)}' y='{_f(r.y)}' "
                        f"width='{_f(r.w)}' height='{_f(r.h)}' fill='none' stroke='none'/>")
            body.append(f"<path data-kind='rule' data-id='{n.id}' d='M{_f(r.x + 1)} {_f(r.y + 1)} "
                        f"L{_f(r.x + 1)} {_f(r.y1 - 1)}' stroke='{role.stroke}' stroke-width='2'/>")
            for ln, base in zip(n.lines, block(n.lines, r.y + 2.0)):
                body.append(text_el(r.x + 2 + PAD_X, base, ln, theme.ink, "start", theme, owner=n.id))
            continue
        rx = {"state": 11.0}.get(n.shape, 4.0)
        dash = " stroke-dasharray='4 3'" if n.shape == "hollow" else ""
        body.append(f"<rect data-kind='node' data-id='{n.id}'{grp} x='{_f(r.x)}' y='{_f(r.y)}' "
                    f"width='{_f(r.w)}' height='{_f(r.h)}' rx='{_f(rx)}' fill='{role.fill}' "
                    f"stroke='{role.stroke}' stroke-width='1.3'{dash}/>")
        text_h = sum(lh(ln.size) for ln in n.lines)
        cells_h = (5.0 if n.lines else 0.0) + CELL_H if n.shape == "cells" else 0.0
        top = r.y + (r.h - text_h - cells_h) / 2
        for ln, base in zip(n.lines, block(n.lines, top)):
            body.append(text_el(r.cx, base, ln, theme.ink, "middle", theme, owner=n.id))
        if n.shape == "cells":
            cy = top + text_h + (5.0 if n.lines else 0.0)
            total = n.cell_w * len(n.cells)
            cx0 = r.cx - total / 2
            for k, label in enumerate(n.cells):
                fill = role.fill if label else theme.page
                body.append(f"<rect data-kind='cell' data-id='{n.id}.{k}' x='{_f(cx0 + k * n.cell_w)}' "
                            f"y='{_f(cy)}' width='{_f(n.cell_w)}' height='{_f(CELL_H)}' fill='{fill}' "
                            f"stroke='{role.stroke}' stroke-width='1'/>")
                if label:
                    ln = Line(label, *CELL)
                    base = cy + (CELL_H - (metrics.ASCENT + metrics.DESCENT) * ln.size) / 2 + \
                        metrics.ASCENT * ln.size
                    body.append(text_el(cx0 + (k + 0.5) * n.cell_w, base, ln, theme.ink, "middle", theme,
                                        owner=f"{n.id}.{k}"))
    # labels
    for p in lay.labels:
        for ln, base in zip(p.lines, block(p.lines, p.rect.y)):
            body.append(text_el(p.rect.cx, base, ln, theme.ink, "middle", theme, owner=f"e{p.edge}"))
    # extent so far
    xs, ys = [], []
    for nid, r in placed.rects.items():
        xs += [r.x, r.x1]
        ys += [r.y, r.y1]
    for pts in lay.paths:
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    for p in lay.labels:
        xs += [p.rect.x, p.rect.x1]
        ys += [p.rect.y, p.rect.y1]
    x0, x1, y0, y1 = min(xs) - 2, max(xs) + 2, min(ys) - 2, max(ys) + 2
    # legend, under everything, wrapped to the width
    items = list(legend_items(d))
    if items:
        y = y1 + 12.0
        x = x0
        row_h = lh(LEGEND[0])
        width = max(x1 - x0, 300.0)
        for what, key, text in items:
            ln = Line(text, *LEGEND)
            sample = 30.0 if what == "kind" else 14.0
            item_w = sample + 6.0 + ln.width
            if x > x0 and x + item_w > x0 + width:
                x = x0
                y += row_h + 4.0
            mid = y + row_h / 2
            if what == "kind":
                k = theme.kinds[key]
                colour = theme.roles[k.role].stroke
                dash = f" stroke-dasharray='{k.dash}'" if k.dash else ""
                # a refused cable's sample ends in its cross, as the cables do, so
                # the legend tells it from a cable by shape as well as colour
                cross = key == "refused"
                end = x + sample - CROSS if cross else x + sample
                body.append(f"<path data-kind='legend' d='M{_f(x)} {_f(mid)} L{_f(end)} {_f(mid)}' "
                            f"stroke='{colour}' stroke-width='{_f(k.width)}'{dash} "
                            f"stroke-linecap='{k.cap}' fill='none'/>")
                if cross:
                    for dy in (-CROSS, CROSS):
                        body.append(f"<path data-kind='legend' d='M{_f(end - CROSS)} {_f(mid - dy)} "
                                    f"L{_f(end + CROSS)} {_f(mid + dy)}' stroke='{colour}' "
                                    f"stroke-width='1.8' stroke-linecap='round'/>")
            else:
                role = theme.roles[key]
                body.append(f"<rect data-kind='swatch' x='{_f(x)}' y='{_f(mid - 5)}' width='14' height='10' "
                            f"rx='2' fill='{role.fill}' stroke='{role.stroke}' stroke-width='1.3'/>")
            base = block([ln], y)[0]
            body.append(text_el(x + sample + 6.0, base, ln, theme.ink, "start", theme, owner="legend"))
            x += item_w + 16.0
            x1 = max(x1, x - 16.0)
        y1 = y + row_h
    vb = (x0 - MARGIN, y0 - MARGIN, x1 - x0 + 2 * MARGIN, y1 - y0 + 2 * MARGIN)
    head = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{_f(vb[2] * 1.5)}' height='{_f(vb[3] * 1.5)}' "
            f"viewBox='{' '.join(_f(v) for v in vb)}' role='img'>"
            f"<title>{escape(d.title)}</title><desc>{escape(d.alt)}</desc>"
            f"<rect data-kind='bg' x='{_f(vb[0])}' y='{_f(vb[1])}' width='{_f(vb[2])}' height='{_f(vb[3])}' "
            f"fill='{theme.page}'/>")
    return "\n".join([head] + body + ["</svg>"]) + "\n"


# ---- the set of diagrams ----------------------------------------------------------------

def sources(root: Path = SOURCES) -> list[Path]:
    return sorted(root.glob("*.toml"))


def build(path: Path, theme: Theme = THEME) -> tuple[Diagram, str]:
    d = load(path, theme)
    return d, render(layout(d))


def view_width(svg: str) -> float:
    """The share of the text column, in per cent, at which the manual shows a
    diagram, so that one unit is the same size in every diagram."""
    vb = svg.split("viewBox='", 1)[1].split("'", 1)[0].split()
    return min(100.0, float(vb[2]) / REF_WIDTH * 100.0)


def main(argv=None) -> int:
    import diagram_check
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="write manual/diagrams/*.svg from the sources")
    ap.add_argument("--check", action="store_true", help="fail if an SVG is stale or has a collision")
    ap.add_argument("--png", metavar="DIR", help="also rasterise each diagram into DIR (rsvg-convert)")
    ap.add_argument("names", nargs="*", help="only these diagrams")
    args = ap.parse_args(argv)
    status = 0
    for src in sources():
        if args.names and src.stem not in args.names:
            continue
        _d, svg = build(src)
        out = src.with_suffix(".svg")
        problems = diagram_check.check(svg)
        for p in problems:
            print(f"{src.stem}: {p}")
            status = 1
        if args.write:
            out.write_text(svg, encoding="utf-8")
        elif args.check and (not out.is_file() or out.read_text(encoding="utf-8") != svg):
            print(f"{out.relative_to(ROOT)} is stale: run tools/manual/diagrams.py --write")
            status = 1
        if args.png:
            tool = shutil.which("rsvg-convert")
            if not tool:
                print("no rsvg-convert on PATH")
                return 1
            Path(args.png).mkdir(parents=True, exist_ok=True)
            subprocess.run([tool, "-z", "2", "-o", str(Path(args.png) / f"{src.stem}.png")],
                           input=svg.encode(), check=True)
        print(f"{src.stem}: {view_width(svg):.0f} % of the column, {len(problems)} problems")
    return status


if __name__ == "__main__":
    sys.exit(main())
