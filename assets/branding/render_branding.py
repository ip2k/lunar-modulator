#!/usr/bin/env python3
"""Render the Lunar Modulator branding art, deterministically.

Writes, next to this script unless --out says otherwise:

  banner.png               1280x320 README banner
  banner.svg               the same banner as vector art, text as outlines
  boot-splash-240.png      240x240 TFT boot screen, pixel-exact to the RGB565 data
  boot-splash-240.rgb565   that screen as raw RGB565, little-endian, row-major

Everything in the pictures is generated here: gradients, a seeded starfield,
the moon and its craters, an orbit with a small station, and an FM waveform.
There are no photographs and no third-party artwork. The lettering is drawn
from the glyph outlines of Audiowide (SIL Open Font License 1.1, see
fonts/OFL.txt); artwork made with an OFL font is not itself under the OFL.

    python3 assets/branding/render_branding.py [--font PATH] [--out DIR]

Needs Pillow, fontTools and numpy. They are not project dependencies; install
them in a throwaway virtual environment.

Every element is rasterised by point sampling (SS x SS samples per pixel) with
the same geometry the SVG uses, and the script refuses to write anything if a
line of text comes within the minimum gap of another element or of an edge.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

HERE = Path(__file__).resolve().parent
DEFAULT_FONT = HERE / "fonts" / "Audiowide-Regular.ttf"

NAME = "LUNAR MODULATOR"
TAGLINE = "INTERGALACTIC MODULATION STATION"
SEED = 20261001  # the day the name was chosen
SS = 4  # samples per pixel along each axis

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


# --------------------------------------------------------------------------
# Colour, numbers


def rgb(hexstr: str) -> np.ndarray:
    h = hexstr.lstrip("#")
    return np.array([int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)])


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# --------------------------------------------------------------------------
# Paints: evaluated per pixel for the PNG, emitted as <defs> for the SVG.
# A gradient's stops change either colour or opacity between neighbours, never
# both, so straight and premultiplied interpolation agree.


class Solid:
    def __init__(self, color: str, alpha: float = 1.0):
        self.color, self.alpha = color, alpha

    def eval(self, X, Y):
        c = np.broadcast_to(rgb(self.color), X.shape + (3,))
        return c, np.full(X.shape, self.alpha)

    def svg(self, defs) -> tuple[str, float]:
        return self.color, self.alpha


class Gradient:
    def __init__(self, stops):
        self.stops = stops  # [(offset 0..1, "#rrggbb", alpha)]

    def _lookup(self, t):
        t = np.clip(t, 0.0, 1.0)
        offs = [s[0] for s in self.stops]
        cols = np.array([rgb(s[1]) for s in self.stops])
        alps = np.array([s[2] for s in self.stops])
        c = np.stack([np.interp(t, offs, cols[:, i]) for i in range(3)], axis=-1)
        return c, np.interp(t, offs, alps)

    def _stops_svg(self) -> str:
        return "".join(
            f'<stop offset="{num(o)}" stop-color="{c}" stop-opacity="{num(a)}"/>'
            for o, c, a in self.stops
        )


class Linear(Gradient):
    def __init__(self, x0, y0, x1, y1, stops):
        super().__init__(stops)
        self.p = (x0, y0, x1, y1)

    def eval(self, X, Y):
        x0, y0, x1, y1 = self.p
        dx, dy = x1 - x0, y1 - y0
        return self._lookup(((X - x0) * dx + (Y - y0) * dy) / (dx * dx + dy * dy))

    def svg(self, defs):
        x0, y0, x1, y1 = self.p
        gid = defs.add(
            f'<linearGradient id="{{id}}" gradientUnits="userSpaceOnUse" '
            f'x1="{num(x0)}" y1="{num(y0)}" x2="{num(x1)}" y2="{num(y1)}">'
            f"{self._stops_svg()}</linearGradient>"
        )
        return f"url(#{gid})", 1.0


class Radial(Gradient):
    def __init__(self, cx, cy, r, stops):
        super().__init__(stops)
        self.c = (cx, cy, r)

    def eval(self, X, Y):
        cx, cy, r = self.c
        return self._lookup(np.hypot(X - cx, Y - cy) / r)

    def svg(self, defs):
        cx, cy, r = self.c
        gid = defs.add(
            f'<radialGradient id="{{id}}" gradientUnits="userSpaceOnUse" '
            f'cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}">'
            f"{self._stops_svg()}</radialGradient>"
        )
        return f"url(#{gid})", 1.0


# --------------------------------------------------------------------------
# Shapes. A shape knows its outline as polygons (for the rasteriser) and as
# SVG markup, so both outputs come from one geometry.


class Shape:
    def __init__(self, polys, svg_tag: str, bbox=None):
        self.polys = [np.asarray(p, dtype=float) for p in polys]
        self.svg_tag = svg_tag  # markup with a "{attrs}" slot
        if bbox is None:
            pts = np.vstack(self.polys)
            bbox = (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())
        self.bbox = tuple(float(v) for v in bbox)


class Circle(Shape):
    def __init__(self, cx, cy, r):
        self.cx, self.cy, self.r = cx, cy, r
        self.polys = None
        self.svg_tag = f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" {{attrs}}/>'
        self.bbox = (cx - r, cy - r, cx + r, cy + r)


def polygon(points) -> Shape:
    d = "M" + " L".join(f"{num(x)} {num(y)}" for x, y in points) + " Z"
    return Shape([points], f'<path d="{d}" {{attrs}}/>')


def crescent(cx, cy, r, shadow_dist, shadow_angle) -> Shape:
    """A disc of radius r minus an equal disc offset by shadow_dist along
    shadow_angle (radians, y down). Exact arcs in the SVG."""
    a = math.acos(shadow_dist / (2 * r))
    phi = shadow_angle
    sx, sy = cx + shadow_dist * math.cos(phi), cy + shadow_dist * math.sin(phi)
    pts = []
    n = 160
    for i in range(n + 1):  # lit limb, the long way round, away from the shadow
        t = phi + a + (2 * math.pi - 2 * a) * i / n
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    for i in range(1, n):  # terminator, along the shadow disc
        t = phi + math.pi + a - 2 * a * i / n
        pts.append((sx + r * math.cos(t), sy + r * math.sin(t)))
    p1 = (cx + r * math.cos(phi + a), cy + r * math.sin(phi + a))
    p2 = (cx + r * math.cos(phi - a), cy + r * math.sin(phi - a))
    d = (
        f"M{num(p1[0])} {num(p1[1])} A{num(r)} {num(r)} 0 1 1 {num(p2[0])} {num(p2[1])} "
        f"A{num(r)} {num(r)} 0 0 0 {num(p1[0])} {num(p1[1])} Z"
    )
    return Shape([pts], f'<path d="{d}" {{attrs}}/>')


# --------------------------------------------------------------------------
# Text from glyph outlines


class FlattenPen(BasePen):
    """Collects contours as polylines, flattening curves to TOL pixels."""

    TOL = 0.02

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours, self._cur = [], None

    def _moveTo(self, pt):
        self._cur = [pt]

    def _lineTo(self, pt):
        self._cur.append(pt)

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        dev = math.hypot(p0[0] - 2 * p1[0] + p2[0], p0[1] - 2 * p1[1] + p2[1])
        n = max(2, math.ceil(math.sqrt(dev / (8 * self.TOL))))
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self._cur.append(
                (
                    u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
                )
            )

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        n = 24
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self._cur.append(
                tuple(
                    u**3 * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t**3 * p3[k]
                    for k in (0, 1)
                )
            )

    def _closePath(self):
        if self._cur and len(self._cur) > 2:
            self.contours.append(self._cur)
        self._cur = None

    _endPath = _closePath


class Face:
    def __init__(self, path: Path):
        self.tt = TTFont(str(path))
        self.glyphs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt["head"].unitsPerEm
        self.cap = self.tt["OS/2"].sCapHeight
        self.hmtx = self.tt["hmtx"]
        self.kern = {}
        if "kern" in self.tt:
            for table in self.tt["kern"].kernTables:
                self.kern.update(getattr(table, "kernTable", {}))

    def run(self, text, tracking_em=0.0):
        """[(glyph, x in font units)] with kerning and tracking."""
        out, x, prev = [], 0.0, None
        for ch in text:
            g = self.cmap[ord(ch)]
            if prev is not None:
                x += self.kern.get((prev, g), 0) + tracking_em * self.upm
            out.append((g, x))
            x += self.hmtx[g][0]
            prev = g
        return out

    def shape(self, text, size, x, baseline, tracking_em=0.0) -> Shape:
        s = size / self.upm
        flat = FlattenPen(self.glyphs)
        svg = SVGPathPen(self.glyphs, ntos=num)
        for g, gx in self.run(text, tracking_em):
            m = (s, 0, 0, -s, x + gx * s, baseline)
            self.glyphs[g].draw(TransformPen(flat, m))
            self.glyphs[g].draw(TransformPen(svg, m))
        return Shape(flat.contours, f'<path d="{svg.getCommands()}" {{attrs}}/>')

    def ink(self, text, size, tracking_em=0.0):
        """Ink box (x0, y0, x1, y1) relative to origin and baseline."""
        return self.shape(text, size, 0.0, 0.0, tracking_em).bbox

    def place(self, text, size, baseline, *, left=None, center=None, tracking_em=0.0):
        x0, _, x1, _ = self.ink(text, size, tracking_em)
        if left is not None:
            x = left - x0
        else:
            x = center - (x0 + x1) / 2
        return self.shape(text, size, x, baseline, tracking_em)

    def tracking_to_width(self, text, size, width):
        x0, _, x1, _ = self.ink(text, size)
        return (width - (x1 - x0)) / (size * (len(text) - 1))

    def cap_px(self, size):
        return self.cap * size / self.upm


# --------------------------------------------------------------------------
# Scene: paint operations in layers, plus the boxes the layout check and the
# starfield must respect. Layers let the stars be placed after the text is
# laid out but painted underneath it.

BACKDROP, STARS, MOON, TEXT = range(4)


class Scene:
    def __init__(self, w, h, background):
        self.w, self.h = w, h
        self.background = background
        self.layer = BACKDROP
        self._ops = []
        self.boxes = {}  # name -> bbox, checked against each other and the edges

    @property
    def ops(self):
        return [op for _, op in sorted(self._ops, key=lambda o: o[0])]  # stable

    def fill(self, shape, paint, clip=None):
        self._ops.append((self.layer, ("fill", shape, paint, clip)))

    def stroke(self, points, width, paint):
        pts = np.asarray(points, dtype=float)
        hw = width / 2
        bbox = (pts[:, 0].min() - hw, pts[:, 1].min() - hw, pts[:, 0].max() + hw, pts[:, 1].max() + hw)
        self._ops.append((self.layer, ("stroke", pts, width, paint, bbox)))
        return bbox

    def reserve(self, name, bbox):
        self.boxes[name] = tuple(float(v) for v in bbox)


def union(*boxes):
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def grow(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


def check_layout(scene, min_gap, margin):
    """Text and the main objects must keep min_gap from each other and margin
    from the edges. Raises SystemExit on any violation."""
    errors, gaps = [], {}
    names = list(scene.boxes)
    for name in names:
        x0, y0, x1, y1 = scene.boxes[name]
        edge = min(x0, y0, scene.w - x1, scene.h - y1)
        if edge < margin:
            errors.append(f"{name} is {edge:.1f}px from an edge (minimum {margin})")
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            A, B = scene.boxes[a], scene.boxes[b]
            gap = max(B[0] - A[2], A[0] - B[2], B[1] - A[3], A[1] - B[3])
            gaps[f"{a}/{b}"] = round(gap, 1)
            if gap < min_gap:
                errors.append(f"{a} and {b} are {gap:.1f}px apart (minimum {min_gap})")
    if errors:
        raise SystemExit("layout check failed:\n  " + "\n  ".join(errors))
    return gaps


# --------------------------------------------------------------------------
# Raster backend: point-sampled coverage, SS x SS samples per pixel.


def _window(bbox, w, h):
    x0 = max(0, math.floor(bbox[0]) - 1)
    y0 = max(0, math.floor(bbox[1]) - 1)
    x1 = min(w, math.ceil(bbox[2]) + 1)
    y1 = min(h, math.ceil(bbox[3]) + 1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _samples(lo, hi):
    return lo + (np.arange((hi - lo) * SS) + 0.5) / SS


def _poly_mask(polys, win):
    """Non-zero winding fill, sampled at sample centres."""
    x0, y0, x1, y1 = win
    ys = _samples(y0, y1)
    edges = np.vstack([np.hstack([p, np.roll(p, -1, axis=0)]) for p in polys])
    edges = edges[edges[:, 1] != edges[:, 3]]
    ya, yb = edges[:, 1], edges[:, 3]
    up = np.where(yb > ya, 1, -1)
    lo, hi = np.minimum(ya, yb), np.maximum(ya, yb)
    Y = ys[:, None]
    active = (Y >= lo) & (Y < hi)
    X = edges[:, 0] + (Y - ya) / (yb - ya) * (edges[:, 2] - edges[:, 0])
    mask = np.zeros((len(ys), (x1 - x0) * SS), dtype=bool)
    for r in range(len(ys)):
        idx = np.nonzero(active[r])[0]
        if len(idx) < 2:
            continue
        order = np.argsort(X[r, idx], kind="stable")
        xs, ws = X[r, idx][order], np.cumsum(up[idx][order])
        for i in np.nonzero(ws[:-1] != 0)[0]:
            c0 = max(0, math.ceil((xs[i] - x0) * SS - 0.5))
            c1 = min(mask.shape[1], math.ceil((xs[i + 1] - x0) * SS - 0.5))
            if c1 > c0:  # spans outside the window would index from the end
                mask[r, c0:c1] = True
    return mask


def _capsule_mask(points, hw, win):
    """Union of round-capped segments of half-width hw (a disc if one point)."""
    x0, y0, x1, y1 = win
    mask = np.zeros(((y1 - y0) * SS, (x1 - x0) * SS), dtype=bool)
    pts = np.asarray(points, dtype=float)
    segs = [(pts[0], pts[0])] if len(pts) == 1 else list(zip(pts[:-1], pts[1:]))
    for a, b in segs:
        sx0 = max(0, math.floor((min(a[0], b[0]) - hw - x0) * SS))
        sx1 = min(mask.shape[1], math.ceil((max(a[0], b[0]) + hw - x0) * SS) + 1)
        sy0 = max(0, math.floor((min(a[1], b[1]) - hw - y0) * SS))
        sy1 = min(mask.shape[0], math.ceil((max(a[1], b[1]) + hw - y0) * SS) + 1)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        X = x0 + (np.arange(sx0, sx1) + 0.5) / SS
        Y = y0 + (np.arange(sy0, sy1) + 0.5) / SS
        X, Y = np.meshgrid(X, Y)
        d = b - a
        L2 = float(d @ d)
        t = 0.0 if L2 == 0 else np.clip(((X - a[0]) * d[0] + (Y - a[1]) * d[1]) / L2, 0, 1)
        dist2 = (X - a[0] - t * d[0]) ** 2 + (Y - a[1] - t * d[1]) ** 2
        mask[sy0:sy1, sx0:sx1] |= dist2 <= hw * hw
    return mask


def _coverage(shape, win):
    if isinstance(shape, Circle):
        m = _capsule_mask([(shape.cx, shape.cy)], shape.r, win)
    else:
        m = _poly_mask(shape.polys, win)
    x0, y0, x1, y1 = win
    return m.reshape(y1 - y0, SS, x1 - x0, SS).mean(axis=(1, 3))


def render_raster(scene) -> np.ndarray:
    h, w = scene.h, scene.w
    Y, X = np.mgrid[0:h, 0:w] + 0.5
    img, _ = scene.background.eval(X, Y)
    img = np.array(img, dtype=float)
    for op in scene.ops:
        if op[0] == "fill":
            _, shape, paint, clip = op
            win = _window(shape.bbox, w, h)
            if win is None:
                continue
            cov = _coverage(shape, win)
            if clip is not None:
                cov = cov * _coverage(clip, win)
        else:
            _, pts, width, paint, bbox = op
            win = _window(bbox, w, h)
            if win is None:
                continue
            x0, y0, x1, y1 = win
            m = _capsule_mask(pts, width / 2, win)
            cov = m.reshape(y1 - y0, SS, x1 - x0, SS).mean(axis=(1, 3))
        x0, y0, x1, y1 = win
        col, alpha = paint.eval(X[y0:y1, x0:x1], Y[y0:y1, x0:x1])
        a = (alpha * cov)[..., None]
        img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + col * a
    return np.clip(img, 0.0, 1.0)


def _bayer(h, w):
    return np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]


def to_rgb888(img) -> np.ndarray:
    d = _bayer(*img.shape[:2])[..., None]
    return np.clip(np.floor(img * 255 + d), 0, 255).astype(np.uint8)


def to_rgb565(img):
    """Ordered-dithered RGB565 codes, and the 8-bit image they display as."""
    d = _bayer(*img.shape[:2])
    r = np.clip(np.floor(img[..., 0] * 31 + d), 0, 31).astype(np.uint16)
    g = np.clip(np.floor(img[..., 1] * 63 + d), 0, 63).astype(np.uint16)
    b = np.clip(np.floor(img[..., 2] * 31 + d), 0, 31).astype(np.uint16)
    codes = (r << 11) | (g << 5) | b
    shown = np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)
    return codes, shown.astype(np.uint8)


# --------------------------------------------------------------------------
# SVG backend


class Defs:
    def __init__(self):
        self.items = []

    def add(self, template: str) -> str:
        gid = f"d{len(self.items) + 1}"
        self.items.append(template.replace("{id}", gid))
        return gid


def render_svg(scene, title: str, credit: str) -> str:
    defs, body = Defs(), []
    clips = {}
    fill, op_ = scene.background.svg(defs)
    body.append(f'<rect width="{scene.w}" height="{scene.h}" fill="{fill}"/>')
    for op in scene.ops:
        if op[0] == "fill":
            _, shape, paint, clip = op
            color, opacity = paint.svg(defs)
            attrs = f'fill="{color}"' + (f' fill-opacity="{num(opacity)}"' if opacity != 1 else "")
            if clip is not None:
                if id(clip) not in clips:
                    clips[id(clip)] = defs.add(
                        '<clipPath id="{id}">' + clip.svg_tag.replace("{attrs}", "") + "</clipPath>"
                    )
                attrs += f' clip-path="url(#{clips[id(clip)]})"'
            body.append(shape.svg_tag.replace("{attrs}", attrs))
        else:
            _, pts, width, paint, _ = op
            color, opacity = paint.svg(defs)
            p = " ".join(f"{num(x)},{num(y)}" for x, y in pts)
            body.append(
                f'<polyline points="{p}" fill="none" stroke="{color}"'
                + (f' stroke-opacity="{num(opacity)}"' if opacity != 1 else "")
                + f' stroke-width="{num(width)}" stroke-linecap="round" stroke-linejoin="round"/>'
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.w}" height="{scene.h}" '
        f'viewBox="0 0 {scene.w} {scene.h}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{title}</title>\n'
        f"<!-- {credit} -->\n"
        "<defs>\n" + "\n".join(defs.items) + "\n</defs>\n" + "\n".join(body) + "\n</svg>\n"
    )


# --------------------------------------------------------------------------
# The picture


PALETTE = {
    "space_top": "#03040b",
    "space_bottom": "#0c1436",
    "nebula_violet": "#40227a",
    "nebula_teal": "#0f4f73",
    "moon_light": "#fbf6ea",
    "moon_mid": "#e6dec9",
    "moon_limb": "#c9c0aa",
    "moon_dark": "#1a1d2c",
    "crater": "#a9a08a",
    "glow": "#8fa6ff",
    "orbit": "#9db4ff",
    "title_top": "#ffffff",
    "title_bottom": "#c3cfeb",
    "accent": "#7fdcff",
    "wave": "#5fd0ff",
}
STAR_COLOURS = ["#ffffff", "#dfe8ff", "#cddcff", "#fff1dc", "#ffe6c7"]


def add_backdrop(scene, nebulae):
    scene.layer = BACKDROP
    for cx, cy, r, colour, alpha in nebulae:
        scene.fill(
            Circle(cx, cy, r),
            Radial(cx, cy, r, [(0, colour, alpha), (0.45, colour, alpha * 0.45), (1, colour, 0)]),
        )


def add_moon(scene, rng, cx, cy, r, orbit, station_t):
    """Moon with earthshine, craters, an orbit ring and a small station.
    orbit = (rx, ry, tilt_degrees). Returns the box of moon + orbit + station."""
    P = PALETTE
    scene.layer = MOON
    glow_r = r * 1.9
    scene.fill(
        Circle(cx, cy, glow_r),
        Radial(cx, cy, glow_r, [(0, P["glow"], 0.30), (0.52, P["glow"], 0.12), (1, P["glow"], 0)]),
    )
    rx, ry, tilt = orbit
    ct, st = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))

    def orbit_pt(t):
        x, y = rx * math.cos(t), ry * math.sin(t)
        return (cx + x * ct - y * st, cy + x * st + y * ct)

    n = 240
    back = [orbit_pt(math.pi + math.pi * i / n) for i in range(n + 1)]  # upper half: behind
    front = [orbit_pt(math.pi * i / n) for i in range(n + 1)]  # lower half: in front
    w = max(1.0, r / 60)
    b1 = scene.stroke(back, w, Solid(P["orbit"], 0.35))

    # disc: the dark side shows faint earthshine and hides the stars behind it
    scene.fill(Circle(cx, cy, r), Solid(P["moon_dark"]))
    shadow_dist, shadow_angle = r * 0.62, math.radians(-38)
    lit = crescent(cx, cy, r, shadow_dist, shadow_angle)
    shx, shy = cx + shadow_dist * math.cos(shadow_angle), cy + shadow_dist * math.sin(shadow_angle)
    lx, ly = cx - r * 0.45 * math.cos(shadow_angle), cy - r * 0.45 * math.sin(shadow_angle)
    scene.fill(
        lit,
        Radial(lx, ly, r * 1.25, [(0, P["moon_light"], 1), (0.55, P["moon_mid"], 1), (1, P["moon_limb"], 1)]),
    )
    # maria and craters, clipped to the lit part
    for _ in range(4):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0.2, 0.75) * r
        scene.fill(
            Circle(cx + d * math.cos(a), cy + d * math.sin(a), rng.uniform(0.18, 0.32) * r),
            Solid(P["crater"], 0.16),
            clip=lit,
        )
    craters, tries = 0, 0
    while craters < int(10 + r / 6) and tries < 2000:
        tries += 1
        a, d = rng.uniform(0, 2 * math.pi), math.sqrt(rng.random()) * 0.9 * r
        cr = rng.uniform(0.025, 0.085) * r
        x, y = cx + d * math.cos(a), cy + d * math.sin(a)
        if math.hypot(x - shx, y - shy) < r + cr * 0.5:  # keep craters on the lit side
            continue
        craters += 1
        scene.fill(Circle(x, y, cr), Solid(P["crater"], 0.42), clip=lit)
        # a lighter rim on the side facing the light
        scene.fill(Circle(x - cr * 0.25, y + cr * 0.25, cr * 0.55), Solid(P["moon_light"], 0.35), clip=lit)

    b2 = scene.stroke(front, w, Solid(P["orbit"], 0.8))
    # the station: a hub with two panels along the orbit's tangent
    sx, sy = orbit_pt(station_t)
    ex, ey = orbit_pt(station_t + 0.01)
    ang = math.atan2(ey - sy, ex - sx)
    u, v = (math.cos(ang), math.sin(ang)), (-math.sin(ang), math.cos(ang))
    k = max(1.0, r / 32)
    scene.fill(
        Circle(sx, sy, 7 * k),
        Radial(sx, sy, 7 * k, [(0, P["accent"], 0.55), (1, P["accent"], 0)]),
    )
    panels = []
    for side in (-1, 1):
        c0 = 2.6 * k
        c1 = c0 + 5.5 * k
        hwid = 1.5 * k
        quad = [
            (sx + side * c0 * u[0] + s * hwid * v[0], sy + side * c0 * u[1] + s * hwid * v[1])
            for s in (-1, 1)
        ] + [
            (sx + side * c1 * u[0] + s * hwid * v[0], sy + side * c1 * u[1] + s * hwid * v[1])
            for s in (1, -1)
        ]
        shape = polygon(quad)
        panels.append(shape.bbox)
        scene.fill(shape, Solid(P["accent"]))
    hub = Circle(sx, sy, 1.9 * k)
    scene.fill(hub, Solid("#ffffff"))
    station_box = union(hub.bbox, *panels)
    if math.hypot(sx - cx, sy - cy) < r + 7 * k:
        raise SystemExit("station overlaps the moon; move station_t")
    return union((cx - r, cy - r, cx + r, cy + r), b1, b2, station_box), (cx, cy, r)


def add_wave(scene, x0, x1, yc, amp, width):
    """A frequency-modulated sine: carrier swept by a slower modulator."""
    n = 900
    pts = []
    for i in range(n + 1):
        u = i / n
        env = math.sin(math.pi * u) ** 0.8
        phase = 2 * math.pi * 11 * u + 3.2 * math.sin(2 * math.pi * 1.5 * u)
        pts.append((x0 + (x1 - x0) * u, yc - amp * env * math.sin(phase)))
    fade = [(0, PALETTE["wave"], 0), (0.18, PALETTE["wave"], 1), (0.82, PALETTE["wave"], 1), (1, PALETTE["wave"], 0)]
    glow = [(o, c, a * 0.22) for o, c, a in fade]
    scene.stroke(pts, width * 3.2, Linear(x0, yc, x1, yc, glow))
    return scene.stroke(pts, width, Linear(x0, yc, x1, yc, fade))


def add_stars(scene, rng, count, rmax, sparkles, keepout_rects, keepout_discs, edge, sparkle_keepout=()):
    """Seeded starfield, painted under the moon and the text. Stars stay out
    of the given rectangles and discs; sparkles also out of sparkle_keepout."""
    scene.layer = STARS
    placed, tries = 0, 0
    stars = []
    while placed < count and tries < count * 50:
        tries += 1
        x, y = rng.uniform(edge, scene.w - edge), rng.uniform(edge, scene.h - edge)
        big = placed < sparkles
        r = rmax * 1.0 if big else 0.32 + (rmax - 0.32) * rng.random() ** 5
        reach = (6.5 * r if big else 2.5 * r) + 1
        rects = list(keepout_rects) + (list(sparkle_keepout) if big else [])
        if any(b[0] - reach < x < b[2] + reach and b[1] - reach < y < b[3] + reach for b in rects):
            continue
        if any(math.hypot(x - dx, y - dy) < dr + reach for dx, dy, dr in keepout_discs):
            continue
        if x - reach < 1 or y - reach < 1 or x + reach > scene.w - 1 or y + reach > scene.h - 1:
            continue
        colour = rng.choice(STAR_COLOURS)
        alpha = 1.0 if big else 0.35 + 0.65 * rng.random()
        stars.append((x, y, r, colour, alpha, big))
        placed += 1
    for x, y, r, colour, alpha, big in stars:
        if big or r > rmax * 0.7:
            gr = r * (6 if big else 3.5)
            scene.fill(Circle(x, y, gr), Radial(x, y, gr, [(0, colour, 0.45), (0.35, colour, 0.12), (1, colour, 0)]))
        if big:
            L, waist = r * 6.5, r * 0.55  # a four-point sparkle
            pts = []
            for i in range(8):
                ang = math.pi / 4 * i
                d = L if i % 2 == 0 else waist
                pts.append((x + d * math.cos(ang), y + d * math.sin(ang)))
            scene.fill(polygon(pts), Solid(colour, 0.85))
        scene.fill(Circle(x, y, r), Solid(colour, alpha))
    return len(stars)


def banner(face) -> tuple[Scene, dict]:
    W, H = 1280, 320
    P = PALETTE
    rng = random.Random(SEED)
    scene = Scene(W, H, Linear(0, 0, 0, H, [(0, P["space_top"], 1), (1, P["space_bottom"], 1)]))
    add_backdrop(
        scene,
        [
            (1090, 30, 430, P["nebula_violet"], 0.55),
            (610, 360, 420, P["nebula_teal"], 0.45),
            (300, -40, 260, P["nebula_violet"], 0.30),
        ],
    )

    # moon on the left
    moon_box, moon_disc = add_moon(scene, rng, cx=190, cy=160, r=92, orbit=(142, 30, -12), station_t=0.13 * math.pi)

    # text block on the right: name, waveform, tagline
    left, right = 400, W - 56
    size = 300.0
    x0, _, x1, _ = face.ink(NAME, size)
    size *= (right - left) / (x1 - x0)
    cap = face.cap_px(size)
    tag_size = size * 0.36
    tag_cap = face.cap_px(tag_size)
    gap, amp, wave_w = 24, 10, 2.4
    block = cap + gap + 2 * amp + wave_w + gap + tag_cap
    top = (H - block) / 2
    base = top + cap
    scene.layer = TEXT
    title = face.place(NAME, size, base, left=left)
    scene.fill(title, Linear(0, base - cap, 0, base, [(0, P["title_top"], 1), (1, P["title_bottom"], 1)]))
    tw = title.bbox[2] - title.bbox[0]
    wy = base + gap + amp + wave_w / 2
    wave_box = add_wave(scene, title.bbox[0], title.bbox[2], wy, amp, wave_w)
    tag_base = wy + amp + wave_w / 2 + gap + tag_cap
    track = face.tracking_to_width(TAGLINE, tag_size, tw)
    tag = face.place(TAGLINE, tag_size, tag_base, left=title.bbox[0], tracking_em=track)
    scene.fill(tag, Solid(P["accent"]))

    scene.reserve("moon+orbit", moon_box)
    scene.reserve("title", title.bbox)
    scene.reserve("wave", (wave_box[0], wy - amp - wave_w * 1.6, wave_box[2], wy + amp + wave_w * 1.6))
    scene.reserve("tagline", tag.bbox)
    gaps = check_layout(scene, min_gap=12, margin=20)

    stars = add_stars(
        scene,
        rng,
        count=460,
        rmax=1.45,
        sparkles=7,
        keepout_rects=[grow(scene.boxes[k], 10) for k in ("title", "wave", "tagline")],
        keepout_discs=[(moon_disc[0], moon_disc[1], moon_disc[2] + 4)],
        edge=4,
        sparkle_keepout=[grow(moon_box, 6)] + [grow(scene.boxes[k], 24) for k in ("title", "wave", "tagline")],
    )
    info = {
        "size": (W, H),
        "title_px": round(size, 2),
        "title_cap_px": round(cap, 1),
        "tagline_px": round(tag_size, 2),
        "tagline_cap_px": round(tag_cap, 1),
        "tagline_tracking_em": round(track, 4),
        "stars": stars,
        "gaps": gaps,
        "boxes": {k: tuple(round(v, 1) for v in b) for k, b in scene.boxes.items()},
    }
    return scene, info


def splash(face) -> tuple[Scene, dict]:
    W = H = 240
    P = PALETTE
    rng = random.Random(SEED + 240)
    scene = Scene(W, H, Linear(0, 0, 0, H, [(0, P["space_top"], 1), (1, P["space_bottom"], 1)]))
    add_backdrop(
        scene,
        [(210, 10, 150, P["nebula_violet"], 0.55), (40, 250, 150, P["nebula_teal"], 0.45)],
    )
    moon_box, moon_disc = add_moon(scene, rng, cx=120, cy=56, r=33, orbit=(54, 11, -12), station_t=0.13 * math.pi)

    margin = 12
    name1, name2 = NAME.split(" ")
    size = 200.0
    x0, _, x1, _ = face.ink(name2, size)
    size *= (W - 2 * 22) / (x1 - x0)
    cap = face.cap_px(size)
    tag_size = 14.0
    tag_cap = face.cap_px(tag_size)
    lines = ["INTERGALACTIC", "MODULATION", "STATION"]
    track = 0.06
    gap_title = 9
    gap = 9
    tag_lead = 6
    amp, wave_w = 4, 1.6
    block = 2 * cap + gap_title + gap + 2 * amp + wave_w + gap + 3 * tag_cap + 2 * tag_lead
    top = moon_box[3] + (H - margin - moon_box[3] - block) / 2
    b1 = top + cap
    scene.layer = TEXT
    t1 = face.place(name1, size, b1, center=W / 2)
    b2 = b1 + gap_title + cap
    t2 = face.place(name2, size, b2, center=W / 2)
    grad = Linear(0, b1 - cap, 0, b2, [(0, P["title_top"], 1), (1, P["title_bottom"], 1)])
    scene.fill(t1, grad)
    scene.fill(t2, grad)
    wy = b2 + gap + amp + wave_w / 2
    wave_box = add_wave(scene, t2.bbox[0], t2.bbox[2], wy, amp, wave_w)
    base = wy + amp + wave_w / 2 + gap + tag_cap
    tags = []
    for line in lines:
        tags.append(face.place(line, tag_size, base, center=W / 2, tracking_em=track))
        base += tag_cap + tag_lead
    for t in tags:
        scene.fill(t, Solid(P["accent"]))

    scene.reserve("moon+orbit", moon_box)
    scene.reserve("LUNAR", t1.bbox)
    scene.reserve("MODULATOR", t2.bbox)
    scene.reserve("wave", (wave_box[0], wy - amp - wave_w * 1.6, wave_box[2], wy + amp + wave_w * 1.6))
    for line, t in zip(lines, tags):
        scene.reserve(line, t.bbox)
    gaps = check_layout(scene, min_gap=5, margin=8)

    text_keys = ["LUNAR", "MODULATOR", "wave"] + lines
    stars = add_stars(
        scene,
        rng,
        count=95,
        rmax=1.05,
        sparkles=2,
        keepout_rects=[grow(scene.boxes[k], 5) for k in text_keys],
        keepout_discs=[(moon_disc[0], moon_disc[1], moon_disc[2] + 3)],
        edge=3,
        sparkle_keepout=[grow(moon_box, 4)] + [grow(scene.boxes[k], 12) for k in text_keys],
    )
    info = {
        "size": (W, H),
        "title_px": round(size, 2),
        "title_cap_px": round(cap, 1),
        "tagline_px": tag_size,
        "tagline_cap_px": round(tag_cap, 1),
        "stars": stars,
        "gaps": gaps,
        "boxes": {k: tuple(round(v, 1) for v in b) for k, b in scene.boxes.items()},
    }
    return scene, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--font", type=Path, default=DEFAULT_FONT, help="Audiowide-Regular.ttf (default: %(default)s)")
    ap.add_argument("--out", type=Path, default=HERE, help="output directory (default: %(default)s)")
    ap.add_argument("-v", "--verbose", action="store_true", help="print layout measurements")
    args = ap.parse_args(argv)

    face = Face(args.font)
    args.out.mkdir(parents=True, exist_ok=True)
    credit = "Lunar Modulator banner, generated by assets/branding/render_branding.py. Lettering: Audiowide (c) 2012 Brian J. Bonislawsky DBA Astigmatic, SIL Open Font License 1.1."

    scene, info = banner(face)
    img = render_raster(scene)
    Image.fromarray(to_rgb888(img)).save(args.out / "banner.png", optimize=True)
    (args.out / "banner.svg").write_text(
        render_svg(scene, "Lunar Modulator: INTERGALACTIC MODULATION STATION", credit), encoding="utf-8"
    )
    if args.verbose:
        print("banner", info)

    scene, info = splash(face)
    codes, shown = to_rgb565(render_raster(scene))
    (args.out / "boot-splash-240.rgb565").write_bytes(codes.astype("<u2").tobytes())
    Image.fromarray(shown).save(args.out / "boot-splash-240.png", optimize=True)
    if args.verbose:
        print("splash", info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
