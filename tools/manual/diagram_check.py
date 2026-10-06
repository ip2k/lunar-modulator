"""Checks a drawn diagram for collisions, from its SVG alone.

    python3 tools/manual/diagram_check.py FILE.svg...

It reads what is drawn (each word's box from its position, size, weight and
anchor and diagram_metrics.py's widths; every line and outline as straight
runs; every box) and reports:

- a word closer than PAD to another word, to any line or outline (its own
  box's included), or to the drawing's edge;
- two boxes closer than PAD, or a box that pokes out of its frame or into a
  frame it does not belong to;
- a connection that passes through or within PAD of a box it does not join,
  or into a box it does join;
- two connections that run along each other;
- anything outside the drawing.

diagrams.py marks what each element is with data-kind (node, group, cell,
edge, arrow, rule, legend, swatch, bg), data-id, data-from and data-to, and a
word's box with data-owner. MIT licence.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diagram_metrics as metrics  # noqa: E402

PAD = 3.0
NS = "{http://www.w3.org/2000/svg}"


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    what: str

    def gap(self, o: "Box") -> float:
        """Distance between two boxes; negative when they overlap."""
        dx = max(o.x0 - self.x1, self.x0 - o.x1)
        dy = max(o.y0 - self.y1, self.y0 - o.y1)
        if dx < 0 and dy < 0:
            return max(dx, dy)
        return max(dx, dy) if (dx < 0 or dy < 0) else (dx * dx + dy * dy) ** 0.5

    def inside(self, o: "Box", pad: float) -> bool:
        return (self.x0 >= o.x0 + pad - 1e-6 and self.x1 <= o.x1 - pad + 1e-6 and
                self.y0 >= o.y0 + pad - 1e-6 and self.y1 <= o.y1 - pad + 1e-6)


@dataclass
class Seg:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    what: str
    owner: str
    kind: str


def seg_box_distance(s: Seg, b: Box) -> float:
    """Distance from a segment's centre line to a box (0 when they touch)."""
    # sample-free exact distance for a segment and an axis-aligned box
    if _seg_intersects_box(s, b):
        return 0.0
    best = min(_pt_box(s.x0, s.y0, b), _pt_box(s.x1, s.y1, b))
    for (px, py) in ((b.x0, b.y0), (b.x1, b.y0), (b.x0, b.y1), (b.x1, b.y1)):
        best = min(best, _pt_seg(px, py, s))
    return best


def _pt_box(x, y, b: Box) -> float:
    dx = max(b.x0 - x, 0.0, x - b.x1)
    dy = max(b.y0 - y, 0.0, y - b.y1)
    return (dx * dx + dy * dy) ** 0.5


def _pt_seg(px, py, s: Seg) -> float:
    vx, vy = s.x1 - s.x0, s.y1 - s.y0
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - s.x0) * vx + (py - s.y0) * vy) / L))
    qx, qy = s.x0 + t * vx, s.y0 + t * vy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def _seg_intersects_box(s: Seg, b: Box) -> bool:
    # Liang-Barsky clipping
    t0, t1 = 0.0, 1.0
    dx, dy = s.x1 - s.x0, s.y1 - s.y0
    for p, q in ((-dx, s.x0 - b.x0), (dx, b.x1 - s.x0), (-dy, s.y0 - b.y0), (dy, b.y1 - s.y0)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _num(el, name, default=0.0) -> float:
    v = el.get(name)
    return float(v) if v is not None else default


def _path_points(d: str):
    """Absolute M/L/H/V/Z paths, as diagrams.py writes them, as runs."""
    runs, cur, start = [], None, None
    for cmd, args in re.findall(r"([MLHVZ])([^MLHVZ]*)", d):
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", args)]
        if cmd == "M":
            cur = start = (nums[0], nums[1])
            for k in range(2, len(nums), 2):
                nxt = (nums[k], nums[k + 1])
                runs.append((cur, nxt))
                cur = nxt
        elif cmd == "L":
            for k in range(0, len(nums), 2):
                nxt = (nums[k], nums[k + 1])
                runs.append((cur, nxt))
                cur = nxt
        elif cmd == "H":
            nxt = (nums[0], cur[1])
            runs.append((cur, nxt))
            cur = nxt
        elif cmd == "V":
            nxt = (cur[0], nums[0])
            runs.append((cur, nxt))
            cur = nxt
        elif cmd == "Z":
            runs.append((cur, start))
            cur = start
    return runs


def text_box(el) -> Box:
    size = _num(el, "font-size", 12.0)
    weight = int(el.get("font-weight", "400"))
    text = "".join(el.itertext())
    w = metrics.text_width(text, size, weight)
    x, y = _num(el, "x"), _num(el, "y")
    anchor = el.get("text-anchor", "start")
    x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
    return Box(x0, y - metrics.ASCENT * size, x0 + w, y + metrics.DESCENT * size, f"'{text}'")


def read(svg: str):
    root = ET.fromstring(svg)
    vb = [float(v) for v in root.get("viewBox").split()]
    view = Box(vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3], "the drawing")
    words, nodes, groups, cells, segs = [], [], [], [], []
    member = {}
    for el in root.iter():
        tag = el.tag.replace(NS, "")
        kind = el.get("data-kind", "")
        ident = el.get("data-id", "")
        if tag == "text":
            b = text_box(el)
            b.what = f"{b.what} ({el.get('data-owner', '?')})"
            words.append((b, el.get("data-owner", "")))
            continue
        if kind == "bg":
            continue
        width = _num(el, "stroke-width", 1.0) if el.get("stroke", "none") != "none" else 0.0
        if tag == "rect":
            x, y, w, h = _num(el, "x"), _num(el, "y"), _num(el, "width"), _num(el, "height")
            b = Box(x, y, x + w, y + h, f"{kind} {ident}")
            if kind == "node":
                nodes.append((b, ident))
                if el.get("data-group"):
                    member[ident] = el.get("data-group")
            elif kind == "group":
                groups.append((b, ident))
            elif kind == "cell":
                cells.append((b, ident))
            if width:
                for (a, c) in (((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
                               ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))):
                    segs.append(Seg(a[0], a[1], c[0], c[1], width, f"the outline of {kind} {ident}",
                                    ident, kind))
        elif tag == "circle":
            cx, cy, r = _num(el, "cx"), _num(el, "cy"), _num(el, "r")
            b = Box(cx - r, cy - r, cx + r, cy + r, f"{kind} {ident}")
            if kind == "node":
                nodes.append((b, ident))
            for (a, c) in (((b.x0, b.y0), (b.x1, b.y0)), ((b.x1, b.y0), (b.x1, b.y1)),
                           ((b.x1, b.y1), (b.x0, b.y1)), ((b.x0, b.y1), (b.x0, b.y0))):
                segs.append(Seg(a[0], a[1], c[0], c[1], 0.0, f"{kind} {ident}", ident, kind))
        elif tag == "path":
            fill = el.get("fill", "none")
            w = width if width else (0.0 if fill == "none" else 0.01)
            for a, c in _path_points(el.get("d", "")):
                label = {"edge": f"the line {el.get('data-from')} -> {el.get('data-to')}",
                         "arrow": f"the arrowhead of {ident}"}.get(kind, f"{kind} {ident}")
                segs.append(Seg(a[0], a[1], c[0], c[1], w, label, ident, kind))
            if kind == "edge":
                segs[-1].owner = ident
    return view, words, nodes, groups, cells, segs, member


def check(svg: str, pad: float = PAD) -> list[str]:
    view, words, nodes, groups, cells, segs, member = read(svg)
    out = []
    # words: the edge, each other, every line
    for k, (b, owner) in enumerate(words):
        if not b.inside(view, pad):
            out.append(f"{b.what} is within {pad} of the drawing's edge or past it")
        for b2, o2 in words[k + 1:]:
            # the lines of one block are set together: they only must not touch
            if b.gap(b2) < (0.5 if o2 == owner else pad):
                out.append(f"{b.what} and {b2.what} are {b.gap(b2):.1f} apart")
        for s in segs:
            dist = seg_box_distance(s, b) - s.width / 2
            if dist < pad:
                out.append(f"{b.what} is {dist:.1f} from {s.what}")
        for nb, nid in nodes + cells + groups:
            # a word overlapping a box must lie inside it (its outline is a run above)
            if b.gap(nb) < 0 and not b.inside(nb, 0.0):
                out.append(f"{b.what} straddles {nb.what}")
    # boxes against boxes and frames
    for k, (a, aid) in enumerate(nodes):
        for b, bid in nodes[k + 1:]:
            if a.gap(b) < pad:
                out.append(f"boxes {aid} and {bid} are {a.gap(b):.1f} apart")
        for g, gid in groups:
            if member.get(aid) == gid:
                if not a.inside(g, pad):
                    out.append(f"box {aid} is not inside its frame {gid}")
            elif a.gap(g) < pad and not (g.inside(a, 0) or a.inside(g, pad)):
                out.append(f"box {aid} touches frame {gid}")
            elif a.inside(g, -1.0) and member.get(aid) != gid:
                out.append(f"box {aid} sits inside frame {gid}, which does not list it")
    for k, (a, aid) in enumerate(groups):
        for b, bid in groups[k + 1:]:
            if a.gap(b) < pad:
                out.append(f"frames {aid} and {bid} are {a.gap(b):.1f} apart")
    # lines against boxes: an edge keeps clear of every box it does not join,
    # and does not enter the ones it joins
    edges = [s for s in segs if s.kind in ("edge", "arrow")]
    ends = {}
    root = ET.fromstring(svg)
    for el in root.iter():
        if el.get("data-kind") == "edge":
            ends[el.get("data-id")] = {el.get("data-from"), el.get("data-to")}
    for s in edges:
        joins = ends.get(s.owner, set())
        for b, nid in nodes:
            if nid in joins:
                inner = Box(b.x0 + 1, b.y0 + 1, b.x1 - 1, b.y1 - 1, b.what)
                if inner.x0 < inner.x1 and _seg_intersects_box(s, inner):
                    out.append(f"{s.what} enters {b.what}")
            else:
                dist = seg_box_distance(s, b) - s.width / 2
                if dist < pad:
                    out.append(f"{s.what} is {dist:.1f} from {b.what}")
    # connections that run along each other
    lines = [s for s in segs if s.kind == "edge"]
    for k, a in enumerate(lines):
        for b in lines[k + 1:]:
            if a.owner == b.owner:
                continue
            ov = _overlap(a, b, 2.0)
            if ov > 2.0:
                out.append(f"{a.what} runs {ov:.0f} along {b.what}")
    # everything inside the drawing
    for s in segs:
        for (x, y) in ((s.x0, s.y0), (s.x1, s.y1)):
            if not (view.x0 + s.width / 2 <= x <= view.x1 - s.width / 2 and
                    view.y0 + s.width / 2 <= y <= view.y1 - s.width / 2):
                out.append(f"{s.what} leaves the drawing")
                break
    return sorted(set(out))


def _overlap(a: Seg, b: Seg, tol: float) -> float:
    if a.y0 == a.y1 and b.y0 == b.y1 and abs(a.y0 - b.y0) < tol:
        lo = max(min(a.x0, a.x1), min(b.x0, b.x1))
        hi = min(max(a.x0, a.x1), max(b.x0, b.x1))
        return max(0.0, hi - lo)
    if a.x0 == a.x1 and b.x0 == b.x1 and abs(a.x0 - b.x0) < tol:
        lo = max(min(a.y0, a.y1), min(b.y0, b.y1))
        hi = min(max(a.y0, a.y1), max(b.y0, b.y1))
        return max(0.0, hi - lo)
    return 0.0


def main(argv=None) -> int:
    status = 0
    for name in (argv if argv is not None else sys.argv[1:]):
        problems = check(Path(name).read_text(encoding="utf-8"))
        for p in problems:
            print(f"{name}: {p}")
        status |= bool(problems)
    return status


if __name__ == "__main__":
    sys.exit(main())
