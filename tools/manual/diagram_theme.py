"""The look of the manual's diagrams (diagrams.py): colours by meaning, type
and line styles, as one Theme that a page of another colour can swap.

Colours mean what they mean on the FM-1's screen (notes/2026-10-06-ui-audit.md
§5, and sim/web/PALETTE.md where the palette lane keeps the map): foam is
modulation and live signal, iris selection and editing, gold held and locked,
love refusal and recording, and each of the four sounds has a hue of its own.
Words are in the theme's ink, but for a frame's title, which takes its role's
tone; a colour is never the only cue, since line styles, labels and the
sounds' numbers carry the same meaning.

The screen draws on Rosé Pine Moon, the manual on Rosé Pine Dawn, so the
diagrams use Dawn counterparts, derived the way sim/web/tools/palette.py
derives the screen's own hues: as OKLCH targets passed through sRGB.

- **Roles** (mod, select, held, refuse): Dawn's own token (manual.css) at its
  hue and chroma, darkened in OKLCH to the lightest tone that carries text,
  4.5:1 on Dawn's base, its surface and the role's own tint. Dawn's tokens
  themselves reach only 2.1:1 (gold) to 3.8:1 (love) on base.
- **Sounds** S1 to S4: the hue angles palette.py gives Moon's nebula, nova,
  aurora and comet, at a Dawn lightness and chroma chosen for each. They are
  marks only (a sound's name is ink), so they need 3:1; their lightness is
  spread so that they stay as far apart as palette.py asks of Moon's: 20
  CIEDE2000 between any two, and 9 under protanopia, deuteranopia and
  tritanopia.
- **Tints**, the fills behind a role's boxes: the same hue at OKLCH lightness
  0.965 and a little chroma, where ink reads at 8:1.

tests/test_manual_diagrams.py checks every rule above, and that the hues
match palette.py's when that file is in the tree. MIT licence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ---- colour science (the formulas palette.py uses) ---------------------------


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 255.0 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def luminance(rgb) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    """WCAG 2 contrast of two sRGB triples or hex strings."""
    a = hex_rgb(a) if isinstance(a, str) else a
    b = hex_rgb(b) if isinstance(b, str) else b
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def oklch(rgb) -> tuple[float, float, float]:
    rgb = hex_rgb(rgb) if isinstance(rgb, str) else rgb
    r, g, b = (_lin(c) for c in rgb)
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l_, m_, s_))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def oklch_rgb(L: float, C: float, h: float):
    """OKLCH to 8-bit sRGB, or None outside the sRGB gamut (Ottosson's matrices)."""
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    if any(v < -1e-6 or v > 1 + 1e-6 for v in lin):
        return None
    return tuple(int(round(_gam(min(1.0, max(0.0, v))))) for v in lin)


def in_gamut(L: float, C: float, h: float):
    """OKLCH to sRGB, lowering the chroma in steps of 0.001 until it fits."""
    c = C
    while c > 0:
        rgb = oklch_rgb(L, c, h)
        if rgb is not None:
            return rgb
        c -= 0.001
    return oklch_rgb(L, 0.0, h)


# ---- Rosé Pine Dawn, as manual/theme/manual.css has it --------------------------

DAWN = {
    "base": "#faf4ed", "surface": "#fffaf3", "overlay": "#f2e9e1", "muted": "#9893a5",
    "subtle": "#797593", "text": "#464261", "love": "#b4637a", "gold": "#ea9d34",
    "rose": "#d7827e", "pine": "#286983", "foam": "#56949f", "iris": "#907aa9",
    "highlight-low": "#f4ede8", "highlight-med": "#dfdad9", "highlight-high": "#cecacd",
}

# The screen's roles, by the Dawn token each takes its hue and chroma from.
ROLE_TOKENS = {"mod": "foam", "select": "iris", "held": "gold", "refuse": "love"}

# The four sounds: Moon's hue angles from sim/web/tools/palette.py (DERIVED,
# palette v2, 2026-10-06), and the Dawn lightness and chroma of each.
SOUND_HUES = {"s1": ("nebula", 256), "s2": ("nova", 52), "s3": ("aurora", 166), "s4": ("comet", 122)}
SOUND_LC = {"s1": (0.52, 0.13), "s2": (0.64, 0.14), "s3": (0.58, 0.11), "s4": (0.48, 0.11)}

TEXT_MIN, MARK_MIN = 4.5, 3.0
TINT_L, TINT_C = 0.965, 0.022
WASH_L, WASH_C = 0.982, 0.012      # a group's fill: lighter than a box's


def text_tone(token: str, backgrounds: list[str]) -> str:
    """Dawn's `token` at its own hue and chroma, at the lightest OKLCH
    lightness (in steps of 0.001) whose contrast is at least TEXT_MIN on every
    background."""
    L0, C, h = oklch(DAWN[token])
    L = min(L0, 0.999)
    while L > 0:
        rgb = in_gamut(L, C, h)
        if all(contrast(rgb, bg) >= TEXT_MIN for bg in backgrounds):
            return rgb_hex(rgb)
        L -= 0.001
    raise ValueError(token)


@dataclass(frozen=True)
class Role:
    stroke: str          # lines, borders, arrowheads
    fill: str            # the fill of a box in this role
    wash: str            # the fill of a group frame in this role
    text: str            # words set in this role's colour (always >= 4.5:1)


@dataclass(frozen=True)
class Kind:
    """How a connection of one kind is drawn."""
    width: float
    dash: str            # "" for solid
    cap: str             # stroke-linecap
    role: str            # its colour unless the edge names another
    legend: str          # what the legend calls it


@dataclass(frozen=True)
class Theme:
    name: str
    page: str            # the background the diagram is drawn on
    ink: str             # every word
    font: str
    roles: dict = field(default_factory=dict)
    kinds: dict = field(default_factory=dict)


FONT = "IBM Plex Sans, Helvetica Neue, Arial, sans-serif"

KINDS = {
    "audio": Kind(2.4, "", "butt", "audio", "audio"),
    "notes": Kind(1.6, "0.1 3.6", "round", "neutral", "notes"),
    "mod": Kind(1.6, "6 3.5", "butt", "mod", "modulation cable"),
    "gate": Kind(1.6, "0.1 3.6", "round", "mod", "gate cable"),
    "press": Kind(1.3, "", "butt", "ink", "button press"),
    "event": Kind(1.3, "1.5 3", "butt", "ink", "by itself"),
    "refused": Kind(1.6, "6 3.5", "butt", "refuse", "refused"),
    "link": Kind(1.0, "", "butt", "neutral", ""),
}


def derive() -> dict:
    """The derived colours, role -> (stroke, fill, wash), worked out afresh
    by the rules in this module's docstring."""
    page = DAWN["surface"]
    out = {}
    for role, token in ROLE_TOKENS.items():
        _, _C, h = oklch(DAWN[token])
        tint = rgb_hex(in_gamut(TINT_L, TINT_C, h))
        wash = rgb_hex(in_gamut(WASH_L, WASH_C, h))
        out[role] = (text_tone(token, [DAWN["base"], page, tint, wash]), tint, wash)
    for role, (_name, h) in SOUND_HUES.items():
        L, C = SOUND_LC[role]
        out[role] = (rgb_hex(in_gamut(L, C, h)), rgb_hex(in_gamut(TINT_L, TINT_C, h)),
                     rgb_hex(in_gamut(WASH_L, WASH_C, h)))
    return out


# derive()'s results, written down so that every machine draws the same bytes
# (a libm that rounds one cube root differently could move a colour by one
# step); tests/test_manual_diagrams.py checks that derive() still gives them.
DERIVED = {
    "mod": ("#3a7983", "#e4f8fc", "#f0fcfe"),
    "select": ("#7c6694", "#f7f0ff", "#fbf7ff"),
    "held": ("#9d6200", "#fef1e4", "#fff8f1"),
    "refuse": ("#a6566e", "#ffeff2", "#fff7f8"),
    "s1": ("#3069b2", "#edf4fe", "#f6f9ff"),
    "s2": ("#cd702f", "#fff0e8", "#fff7f3"),
    "s3": ("#228f6b", "#e6f9f0", "#f2fcf7"),
    "s4": ("#53670e", "#f1f6e6", "#f8fbf2"),
}


def dawn() -> Theme:
    page = DAWN["surface"]
    ink = DAWN["text"]
    roles = {
        "neutral": Role(DAWN["subtle"], DAWN["highlight-low"], DAWN["base"], ink),
        "ink": Role(ink, DAWN["highlight-low"], DAWN["base"], ink),
        "audio": Role(ink, DAWN["highlight-low"], DAWN["base"], ink),
        "empty": Role(DAWN["subtle"], page, page, ink),
    }
    for role, (stroke, fill, wash) in DERIVED.items():
        # a role's words take its tone; a sound's name stays ink (marks only)
        roles[role] = Role(stroke, fill, wash, stroke if role in ROLE_TOKENS else ink)
    roles["live"] = roles["mod"]               # one meaning: live signal and modulation
    return Theme("dawn", page, ink, FONT, roles, dict(KINDS))


THEME = dawn()
