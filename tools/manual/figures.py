"""Line drawings of the FM-1 for the manual, as SVG, drawn from measurements.

Geometry in millimetres, the same numbers the virtual FM-1 draws its panel
from (sim/web/www/app.js, branch stage-v1/virtual-fm1): the case is
161.5 x 96.5 mm (M-VAVE's manual, specifications) [reported]; control
centres were measured on the owner's board photo (photos/2026-09-29/3-top.jpg)
at 12.8 px/mm [verified positions; scale inferred, within about 5 %]; the
printed names come from M-VAVE's manual [reported]. Keep the two in step;
tests/test_manual.py compares them when sim/web is in the tree.

Colours are the Rosé Pine Dawn palette (manual/theme/manual.css). The SVG
carries its own styles, so it looks the same inline, as a file and in the
PDF. MIT licence.
"""
from __future__ import annotations

from html import escape

CASE = {"w": 161.5, "h": 96.5, "r": 7.0}
ROW_TOP = 13.2
MASTER = (15.36, ROW_TOP)
KNOBS = [("SELECT", 33.09, ROW_TOP), ("PRESETS", 15.67, 29.88), ("ALGORITHM", 32.94, 29.88),
         ("KNOB1", 92.55, ROW_TOP), ("KNOB2", 110.44, ROW_TOP), ("KNOB3", 128.33, ROW_TOP),
         ("KNOB4", 146.22, ROW_TOP)]
KNOB_R = 3.6
OCT = [("OCT-", 19.34), ("OCT+", 31.38)]
OCT_Y = 43.24
FN_X = [94.70, 104.46, 114.27, 124.15, 134.03, 143.80]
FN_ROWS = [(30.51, ["FX", "SEL", "ENV", "LFO", "EDIT", "GLO"]),
           (40.20, ["HOME", "SAVE", "ARP", "SEQ", "PLAY/STOP", "REC"])]
BEZEL = (43.8, 6.6, 38.0, 36.3)
WHITE_X0, WHITE_PITCH, WHITE_Y, BLACK_Y = 15.97, 8.957, 77.38, 62.15
WHITE = (7.4, 16.0)
BLACK = (6.6, 11.5)
WHITE_STEPS = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]
KEYS = 27
COMBO = ["OP1", "OP2", "OP3", "OP4", "OP5", "OP6", "PIT", "GLO", "MONO", "POLY", ""]
EDGE = [("POWER", 39.3, 7.0, "switch"), ("USB", 53.4, 8.9, "usb"),
        ("MIDI IN", 64.3, 6.0, "jack"), ("OUT", 76.8, 6.0, "jack")]

# Rosé Pine Dawn (rosepinetheme.com/palette, MIT).
INK = "#464261"        # text
PAPER = "#fffaf3"      # surface
TINT = "#f2e9e1"       # overlay
LINE = "#797593"       # subtle
ACCENT = "#286983"     # pine
SCREEN = "#286983"

FONT = 'font-family="IBM Plex Sans, Helvetica Neue, Arial, sans-serif" font-weight="600" text-anchor="middle"'

# Presentation attributes rather than a <style> sheet: every SVG renderer,
# WeasyPrint's included, honours them.
A = {
    "case": f'fill="{PAPER}" stroke="{INK}" stroke-width=".45"',
    "frame": f'fill="none" stroke="{LINE}" stroke-width=".25"',
    "knob": f'fill="{TINT}" stroke="{INK}" stroke-width=".35"',
    "mark": f'stroke="{INK}" stroke-width=".5" stroke-linecap="round"',
    "divider": f'stroke="{INK}" stroke-width=".2"',
    "btn": f'fill="{PAPER}" stroke="{INK}" stroke-width=".3"',
    "white": f'fill="{PAPER}" stroke="{INK}" stroke-width=".3"',
    "black": f'fill="{INK}" stroke="{INK}" stroke-width=".3"',
    "bezel": f'fill="{INK}"',
    "screen": f'fill="{SCREEN}"',
    "print": f'fill="{INK}" font-size="2" {FONT}',
    "label": f'fill="{INK}" font-size="1.55" {FONT}',
    # Smaller than the simulator's 1.35 and set higher on the key, so "MONO"
    # keeps clear of the key's rounded end at print size.
    "combo": f'fill="{PAPER}" font-size="1.15" {FONT}',
    "lead": f'fill="none" stroke="{ACCENT}" stroke-width=".3"',
    "bubble": f'fill="{ACCENT}"',
    "bubble-num": f'fill="{PAPER}" font-size="2.6" font-family="IBM Plex Sans, Helvetica Neue, Arial, sans-serif" font-weight="700" text-anchor="middle"',
    "port": f'fill="{TINT}" stroke="{INK}" stroke-width=".3"',
    "hole": f'fill="{INK}"',
    "edge": f'fill="{PAPER}" stroke="{INK}" stroke-width=".45"',
}

# Callouts on the front panel: number, the point the leader starts from (the
# bubble's centre) and the leader's path. Bubbles sit in the margins; leaders
# run in the gaps between controls. Chapter 3's legend explains each number.
CALLOUTS = [
    # left margin, top to bottom
    (1, "MASTER", (-8.0, 13.2), [(-5.8, 13.2), (11.2, 13.2)]),
    (2, "PRESETS", (-8.0, 29.88), [(-5.8, 29.88), (11.5, 29.88)]),
    (3, "ALGORITHM", (-8.0, 36.6), [(-5.8, 36.6), (28.6, 36.6), (30.6, 33.3)]),
    (4, "OCT- and OCT+", (-8.0, 43.24), [(-5.8, 43.24), (12.8, 43.24)]),
    (5, "Keys", (-8.0, 70.0), [(-5.8, 70.0), (9.7, 70.0)]),
    # top margin, left to right
    (6, "SELECT", (33.09, -8.0), [(33.09, -5.8), (33.09, 5.0)]),
    (7, "Screen", (62.8, -8.0), [(62.8, -5.8), (62.8, 6.1)]),
    (8, "KNOB1 to KNOB4", (119.385, -8.0), [(119.385, -5.8), (119.385, 2.9)]),
    # right margin
    (9, "Function buttons", (169.5, 35.35), [(167.3, 35.35), (150.3, 35.35)]),
]
KNOB_BRACKET = (KNOBS[3][1] - KNOB_R, KNOBS[6][1] + KNOB_R, 2.9, 4.1)


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


PANEL_DESC = ("Line drawing of the front panel: MASTER and three navigation encoders at the top "
              "left, the screen in the middle, KNOB1 to KNOB4 at the top right above twelve "
              "function buttons, OCT- and OCT+ at the left, and 27 keys along the bottom. "
              "Numbered callouts match the legend.")
EDGE_DESC = ("The top edge of the case, seen from above with the keys towards you. From left to "
             "right: the POWER slide switch, the USB-C socket, the MIDI IN jack and the audio "
             "OUT jack.")


def _root(vb, title: str, desc: str) -> str:
    """The <svg> element, sized 6 px per millimetre, with its title and description."""
    w, h = vb[2] * 6, vb[3] * 6
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{_f(w)}' height='{_f(h)}' "
            f"viewBox='{' '.join(_f(v) for v in vb)}' role='img'>"
            f"<title>{escape(title)}</title><desc>{escape(desc)}</desc>")


def white_keys() -> dict[int, float]:
    xs, n = {}, 0
    for s in range(KEYS):
        if s in WHITE_STEPS:
            xs[s] = WHITE_X0 + WHITE_PITCH * n
            n += 1
    return xs


def panel_svg(*, callouts: bool = True, title: str = "The FM-1's front panel") -> str:
    pad_l, pad_t, pad_r, pad_b = (13.0, 13.0, 13.0, 3.0) if callouts else (3.0, 3.0, 3.0, 3.0)
    vb = (-pad_l, -pad_t, CASE["w"] + pad_l + pad_r, CASE["h"] + pad_t + pad_b)
    o = [_root(vb, title, PANEL_DESC),
         f"<rect {A['case']} x='0' y='0' width='{CASE['w']}' height='{CASE['h']}' rx='{CASE['r']}'/>"]

    def knob(name, x, y):
        o.append(f"<text {A['print']} x='{_f(x)}' y='{_f(y - 5.6)}'>{escape(name)}</text>")
        o.append(f"<circle {A['knob']} cx='{_f(x)}' cy='{_f(y)}' r='{KNOB_R}'/>")
        o.append(f"<line {A['mark']} x1='{_f(x)}' y1='{_f(y - KNOB_R + .9)}' "
                 f"x2='{_f(x)}' y2='{_f(y - KNOB_R + 2.2)}'/>")

    knob("MASTER", *MASTER)
    for name, x, y in KNOBS:
        knob(name, x, y)

    bx, by, bw, bh = BEZEL
    o.append(f"<rect {A['bezel']} x='{bx}' y='{by}' width='{bw}' height='{bh}' rx='3'/>")
    o.append(f"<rect {A['screen']} x='{_f(bx + 4.2)}' y='{_f(by + 3.4)}' width='{_f(bw - 8.4)}' "
             f"height='{_f(bh - 8.4)}' rx='.8'/>")

    o.append(f"<rect {A['frame']} x='13.3' y='39.7' width='24.1' height='7.1' rx='2'/>")
    for name, x in OCT:
        o.append(f"<rect {A['btn']} x='{_f(x - 4.5)}' y='{_f(OCT_Y - 2.6)}' width='9' height='5.2' rx='1.4'/>")
        shown = name.replace("-", "−")
        o.append(f"<text {A['label']} x='{_f(x)}' y='{_f(OCT_Y + .55)}'>{escape(shown)}</text>")

    o.append(f"<rect {A['frame']} x='88.7' y='24.6' width='61.1' height='21.5' rx='3'/>")
    for y, ids in FN_ROWS:
        for x, name in zip(FN_X, ids):
            o.append(f"<rect {A['btn']} x='{_f(x - 3.6)}' y='{_f(y - 3.6)}' width='7.2' height='7.2' rx='1.4'/>")
            if name == "PLAY/STOP":
                o.append(f"<text {A['label']} x='{_f(x)}' y='{_f(y - .45)}'>PLAY</text>")
                o.append(f"<line {A['divider']} x1='{_f(x - 2.1)}' x2='{_f(x + 2.1)}' "
                         f"y1='{_f(y + .1)}' y2='{_f(y + .1)}'/>")
                o.append(f"<text {A['label']} x='{_f(x)}' y='{_f(y + 1.85)}'>STOP</text>")
            else:
                o.append(f"<text {A['label']} x='{_f(x)}' y='{_f(y + .55)}'>{escape(name)}</text>")

    o.append(f"<rect {A['frame']} x='10.2' y='54.4' width='145.9' height='33.3' rx='4'/>")
    wx = white_keys()
    black = 0
    for s in range(KEYS):
        is_white = s in wx
        x = wx[s] if is_white else (wx[s - 1] + wx[s + 1]) / 2
        y = WHITE_Y if is_white else BLACK_Y
        w, h = WHITE if is_white else BLACK
        o.append(f"<rect {A['white' if is_white else 'black']} x='{_f(x - w / 2)}' "
                 f"y='{_f(y - h / 2)}' width='{w}' height='{h}' rx='{_f(w / 2)}'/>")
        if not is_white:
            if COMBO[black]:
                o.append(f"<text {A['combo']} x='{_f(x)}' y='{_f(y + h / 2 - 2.3)}'>"
                         f"{escape(COMBO[black])}</text>")
            black += 1

    if callouts:
        x0, x1, y0, y1 = KNOB_BRACKET
        o.append(f"<path {A['lead']} d='M{_f(x0)} {_f(y1)} V{_f(y0)} H{_f(x1)} V{_f(y1)}'/>")
        for n, _what, (cx, cy), path in CALLOUTS:
            d = "M" + " L".join(f"{_f(px)} {_f(py)}" for px, py in path)
            o.append(f"<path {A['lead']} d='{d}'/>")
            o.append(f"<circle {A['bubble']} cx='{_f(cx)}' cy='{_f(cy)}' r='2.2'/>")
            o.append(f"<text {A['bubble-num']} x='{_f(cx)}' y='{_f(cy + .93)}'>{n}</text>")
    o.append("</svg>")
    return "\n".join(o)


def edge_svg(title: str = "The FM-1's top edge") -> str:
    """The connectors on the edge above the screen, seen from above, at the
    same horizontal scale as the front panel, each named underneath."""
    h = 9.0
    vb = (-3.0, -3.0, CASE["w"] + 6.0, h + 12.0)
    o = [_root(vb, title, EDGE_DESC),
         f"<rect {A['edge']} x='0' y='0' width='{CASE['w']}' height='{h}' rx='2.5'/>"]
    cy = h / 2
    for name, x, w, kind in EDGE:
        if kind == "switch":
            o.append(f"<rect {A['port']} x='{_f(x - w / 2)}' y='{_f(cy - 1.4)}' width='{w}' height='2.8' rx='.6'/>")
            o.append(f"<rect {A['bezel']} x='{_f(x - w / 2 + .6)}' y='{_f(cy - .9)}' width='2.6' height='1.8' rx='.4'/>")
        elif kind == "usb":
            o.append(f"<rect {A['port']} x='{_f(x - w / 2)}' y='{_f(cy - 1.3)}' width='{w}' height='2.6' rx='1.3'/>")
            o.append(f"<rect {A['hole']} x='{_f(x - w / 2 + 1.6)}' y='{_f(cy - .35)}' width='{_f(w - 3.2)}' height='.7' rx='.35'/>")
        else:
            o.append(f"<circle {A['port']} cx='{_f(x)}' cy='{_f(cy)}' r='{_f(w / 2 - .4)}'/>")
            o.append(f"<circle {A['hole']} cx='{_f(x)}' cy='{_f(cy)}' r='1.1'/>")
        o.append(f"<text {A['print']} x='{_f(x)}' y='{_f(h + 4.2)}'>{escape(name)}</text>")
    o.append("</svg>")
    return "\n".join(o)


# name: (drawing, caption, alternative text)
FIGURES = {
    "panel": (panel_svg, "Front panel. The numbers match the table below it.", PANEL_DESC),
    "edge": (edge_svg, "The top edge, seen from above with the keys towards you.", EDGE_DESC),
}
