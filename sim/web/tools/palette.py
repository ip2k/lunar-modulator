#!/usr/bin/env python3
"""Check the virtual FM-1's palette: the screen's (src/fm1_look.h) and the
page's (www/style.css), against one semantic colour map (sim/web/PALETTE.md).

    python3 sim/web/tools/palette.py [REPO_ROOT]            # check; exit 1 on a failure
    python3 sim/web/tools/palette.py --report [REPO_ROOT]   # PALETTE.md's tables, Markdown
    python3 sim/web/tools/palette.py --swatch DIR [REPO_ROOT]
                                     # DIR/palette.ppm: the screen's colours in the
                                     # 5x9 font at x2, as seen and under three CVDs

The tokens are Rosé Pine Moon's (RP_*, --rp-*) and Lunar Modulator's own
hues (LM_*, --lm-*), derived in OKLCH at Moon's accent lightness and chroma
(DERIVED below). The roles (C_* in the header, --select and the like in the
stylesheet) name what a colour means; ROLES is the map both files must
implement. What is checked:

1. The two files agree: every token the header defines has the same value in
   style.css, every --lm- token is in the header, and pine, which fails as
   text and as a mark, is not in the header at all.
2. Each derived hue is its OKLCH target passed through sRGB and the screen's
   RGB565 round trip, so it is a fixed point of that trip: the page and the
   screen show the same colour. It lies within Moon's accent span (lightness
   widened by 0.03 each side, chroma as is).
3. Contrast (WCAG 2), after the RGB565 round trip exactly as app.js expands
   it (`((p >> 11) & 31) * 255 / 31` into a Uint8ClampedArray): every colour
   meets 4.5:1 as text on each background USES says it is drawn on, and 3:1
   as a mark.
4. CIEDE2000 between every two colours the screen draws with different
   meanings, the lower of the screen's and the page's value: the sound
   colours at least 20 from each other and from love, at least 15 from every
   other colour; any pair under 20 is in JUSTIFIED, with the reason.
5. The sound colours simulated for protanopia, deuteranopia and tritanopia
   (Machado, Oliveira and Fernandes 2009, severity 1, on linear RGB) stay at
   least CVD_FLOOR apart; the S1-S4 number on screen is the non-colour cue.
6. The roles: every C_* role in ROLES is defined in the header as its token,
   the page's role variables match, the page's focus ring is the selection
   colour, and the stylesheet names an accent token (love, gold, rose, foam,
   iris, pine, every --lm-) only to define its role, so every other rule says
   what the colour means rather than which hue it is.

Pure Python, no dependencies. MIT licence, like the rest of this repository.
"""
import itertools
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

# ---- colour science --------------------------------------------------------


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 255.0 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def u8_clamp(x):
    """ECMAScript ToUint8Clamp, as a Uint8ClampedArray stores a number: clamp,
    then round half to even."""
    if x != x:
        return 0
    x = min(255.0, max(0.0, x))
    f = math.floor(x)
    if f + 0.5 < x:
        return f + 1
    if x < f + 0.5:
        return f
    return f + 1 if f % 2 else f


def rgb565(rgb):
    """fm1_tft.h's FM1_RGB565: the top 5, 6 and 5 bits."""
    r, g, b = rgb
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def expand565(p):
    """app.js's drawScreen: each field scaled to 0-255 into a Uint8ClampedArray."""
    return (u8_clamp(((p >> 11) & 31) * 255 / 31), u8_clamp(((p >> 5) & 63) * 255 / 63),
            u8_clamp((p & 31) * 255 / 31))


def screen(rgb):
    """The colour the page's canvas shows for an sRGB triple the firmware draws."""
    return expand565(rgb565(rgb))


def luminance(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def oklab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l_, m_, s_))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklch(rgb):
    L, a, b = oklab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def oklch_linear(L, C, h):
    """OKLCH to linear sRGB, unclamped (Björn Ottosson's matrices)."""
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def oklch_rgb(L, C, h):
    """OKLCH to 8-bit sRGB, or None outside the sRGB gamut."""
    lin = oklch_linear(L, C, h)
    if any(v < -1e-6 or v > 1 + 1e-6 for v in lin):
        return None
    return tuple(int(round(_gam(min(1.0, max(0.0, v))))) for v in lin)


def lab(rgb):
    """CIELAB (D65) of an sRGB triple."""
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def ciede2000(lab1, lab2):
    """CIEDE2000 (Sharma, Wu and Dalal 2005), kL = kC = kH = 1."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    cbar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0
    dl, dc = L2 - L1, c2p - c1p
    dh = 0.0
    if c1p * c2p:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    d_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lbp, cbp = (L1 + L2) / 2, (c1p + c2p) / 2
    if not c1p * c2p:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dtheta = 30 * math.exp(-((hbp - 275) / 25) ** 2)
    rc = 2 * math.sqrt(cbp ** 7 / (cbp ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lbp - 50) ** 2 / math.sqrt(20 + (lbp - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (d_h / sh) ** 2 + rt * (dc / sc) * (d_h / sh))


def delta_e(rgb1, rgb2):
    return ciede2000(lab(rgb1), lab(rgb2))


# Machado, Oliveira and Fernandes (2009), "A physiologically-based model for
# simulation of color vision deficiency", IEEE TVCG 15(6), table 1 at severity
# 1.0; applied to linear RGB and clipped.
MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}


def simulate(rgb, kind):
    lin = [_lin(c) for c in rgb]
    out = [min(1.0, max(0.0, sum(m * v for m, v in zip(row, lin)))) for row in MACHADO[kind]]
    return tuple(int(round(_gam(v))) for v in out)


# ---- the palette's rules ---------------------------------------------------

BACKGROUNDS = ("base", "surface", "overlay", "highlight-med")
TEXT_MIN, MARK_MIN = 4.5, 3.0

# Moon's accents, whose lightness and chroma the derived hues share. Pine is
# left out: it fails as text and as a mark (the audit, §3).
ACCENTS = ("love", "gold", "rose", "foam", "iris")
L_MARGIN = 0.03

# Lunar Modulator's own hues: name -> the OKLCH target (L, C, h in degrees).
# Each is passed through sRGB and the RGB565 round trip; the result is the
# token. Space-themed names; the order is the sounds' (SOUNDS).
DERIVED = {
    "nebula": (0.72, 0.14, 256),   # blue, a reflection nebula
    "nova": (0.72, 0.14, 52),      # orange, a flaring star
    "aurora": (0.78, 0.13, 166),   # green, oxygen's aurora line
    "comet": (0.86, 0.13, 122),    # yellow-green, a comet's coma
}
SOUNDS = ("nebula", "nova", "aurora", "comet")   # S1-S4

# Where the screen draws each colour as text and as marks (bars, fills, ticks,
# outlines), by background. A colour not listed for a background is never
# drawn on it in that form.
ALL = BACKGROUNDS
USES = {
    "text": {"text": ALL, "mark": ALL},
    "subtle": {"text": ("base", "surface"), "mark": ALL},
    "muted": {"text": (), "mark": ("base",)},
    "love": {"text": ("base", "surface"), "mark": ALL},
    "gold": {"text": ALL, "mark": ALL},
    "rose": {"text": ("base", "surface", "overlay"), "mark": ("base", "surface", "overlay")},
    "foam": {"text": ALL, "mark": ALL},
    "iris": {"text": ALL, "mark": ALL},
    "pine": {"text": (), "mark": ()},
}
for _s in SOUNDS:   # the title bar's "S2", the Mix page's labels and bars, FX's tag
    USES[_s] = {"text": ("base", "surface", "overlay"), "mark": ALL}

# The semantic map: role -> token. Header macros are C_<ROLE> in capitals
# with '_' for '-'; the page's variables are --<role>. A role absent from
# PAGE_ROLES is the screen's alone.
ROLES = {
    "select": "iris",      # selection and the value being edited
    "held": "gold",        # held and locked
    "live": "foam",        # live signal: scope, meters, PLAY, trig ticks
    "mod": "foam",         # modulation: a modulated label, its bracket, MATRIX's sources
    "refuse": "love",      # refusal, recording, over the limit
    "context": "rose",     # the context line under the title bar, a list's title
    "hint": "text",        # hints, and modulation's live tick
    "label": "subtle",     # labels, secondary text, idle states, a list's place
    "sound-1": "nebula",
    "sound-2": "nova",
    "sound-3": "aurora",
    "sound-4": "comet",
}
PAGE_ROLES = ("select", "held", "live", "refuse", "context",
              "sound-1", "sound-2", "sound-3", "sound-4")
# One meaning per accent: roles that share a token must be one meaning.
SHARED = {"foam": {"live", "mod"}}   # "live signal and modulation"

# The colours the screen draws with a meaning; every two are kept apart.
SCREEN = ("subtle", "text", "iris", "gold", "foam", "love", "rose") + SOUNDS
SOUND_MIN, SOUND_OTHER_MIN, NEAR = 20.0, 15.0, 20.0
CVD_FLOOR = 9.0

# Pairs under NEAR (20) and why each is acceptable. The checker fails on any
# other pair under 20, so a new close pair needs a reason here.
JUSTIFIED = {
    ("love", "rose"): "Moon's own pair: rose is never on a line where love can appear "
                      "(the audit, §3)",
    ("subtle", "iris"): "Moon's own pair: selection is a filled bar or chip with base text "
                        "on it, never iris text beside subtle text",
    ("text", "iris"): "Moon's own pair: iris marks selection as a fill under base text, "
                      "not as text beside text",
    ("gold", "nova"): "S2's colour against held: 0.11 apart in OKLCH lightness and 24 "
                      "degrees of hue, and a sound colour always comes with its S-number",
    ("rose", "nova"): "S2's colour against context: nova has 1.4 times rose's chroma, 27 "
                      "degrees of hue away, and the S-number goes with it",
    ("foam", "nebula"): "S1's colour against modulation: nebula has 2.6 times foam's chroma, "
                        "37 degrees of hue away, and the S-number goes with it",
}


# ---- reading the two files -------------------------------------------------

def _token_name(prefix, name):
    return prefix.lower(), name.lower().replace("_", "-")


def read_header(text):
    tokens, roles = {}, {}
    for pre, name, r, g, b in re.findall(
            r"^#define\s+(RP|LM)_([A-Z0-9_]+)\s+FM1_RGB565\(\s*0x([0-9a-fA-F]{2})\s*,"
            r"\s*0x([0-9a-fA-F]{2})\s*,\s*0x([0-9a-fA-F]{2})\s*\)", text, re.M):
        tokens[_token_name(pre, name)] = (int(r, 16), int(g, 16), int(b, 16))
    for role, pre, name in re.findall(r"^#define\s+C_([A-Z0-9_]+)\s+(RP|LM)_([A-Z0-9_]+)\s*(?:/\*.*)?$",
                                      text, re.M):
        roles[role.lower().replace("_", "-")] = _token_name(pre, name)
    return tokens, roles


def read_css(text):
    root = re.search(r":root\s*\{(.*?)\n\}", text, re.S)
    body = root.group(1) if root else ""
    tokens = {(p, n): hex_rgb(h) for p, n, h in
              re.findall(r"--(rp|lm)-([a-z0-9-]+)\s*:\s*#([0-9a-fA-F]{6})\s*;", body)}
    variables = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", body))
    return tokens, variables


def _resolve(variables, value, depth=0):
    m = re.fullmatch(r"\s*var\(--([a-z0-9-]+)\)\s*", value)
    if not m or depth > 8:
        return value.strip()
    name = m.group(1)
    if re.match(r"(rp|lm)-", name):
        return name
    return _resolve(variables, variables.get(name, ""), depth + 1)


def load(root=ROOT):
    root = Path(root)
    header = (root / "sim/web/src/fm1_look.h").read_text(encoding="utf-8")
    css = (root / "sim/web/www/style.css").read_text(encoding="utf-8")
    return header, css


def palette(header, css):
    """name -> {'page': sRGB, 'screen': the round trip} from both files (the
    header's value where it has one)."""
    htok, _ = read_header(header)
    ctok, _ = read_css(css)
    out = {}
    for (pre, name), rgb in list(ctok.items()) + list(htok.items()):
        out[name] = {"family": pre, "page": rgb, "screen": screen(rgb)}
    return out


def moon_envelope(pal):
    lch = [oklch(pal[a]["page"]) for a in ACCENTS]
    return (min(L for L, _, _ in lch) - L_MARGIN, max(L for L, _, _ in lch) + L_MARGIN,
            min(C for _, C, _ in lch), max(C for _, C, _ in lch))


def pair_de(pal, a, b):
    return min(delta_e(pal[a]["screen"], pal[b]["screen"]), delta_e(pal[a]["page"], pal[b]["page"]))


def check(header, css):
    """Every rule above; returns the list of failures (empty when all hold)."""
    fail = []
    htok, hroles = read_header(header)
    ctok, cvars = read_css(css)

    # 1. the two files agree
    for key, rgb in htok.items():
        if key not in ctok:
            fail.append(f"--{key[0]}-{key[1]} is in fm1_look.h but not in style.css")
        elif ctok[key] != rgb:
            fail.append(f"{key[1]}: fm1_look.h {rgb_hex(rgb)} but style.css {rgb_hex(ctok[key])}")
    for key in ctok:
        if key[0] == "lm" and key not in htok:
            fail.append(f"--lm-{key[1]} is in style.css but not in fm1_look.h")
    if ("rp", "pine") in htok:
        fail.append("RP_PINE is in fm1_look.h: pine fails as text and as a mark (keep it off the screen)")
    pal = palette(header, css)
    need = set(SCREEN) | set(BACKGROUNDS) | set(DERIVED)
    for name in sorted(need - set(pal)):
        fail.append(f"{name} is in neither file")
    if fail:
        return fail

    # 2. derived hues: target -> sRGB -> RGB565 round trip, within Moon's span
    lo_l, hi_l, lo_c, hi_c = moon_envelope(pal)
    for name, (L, C, h) in DERIVED.items():
        rgb = oklch_rgb(L, C, h)
        if rgb is None:
            fail.append(f"{name}: OKLCH {L} {C} {h} is outside sRGB")
            continue
        want = screen(rgb)
        if pal[name]["family"] != "lm":
            fail.append(f"{name} must be an LM_ token, Lunar Modulator's own")
        if pal[name]["page"] != want:
            fail.append(f"{name}: OKLCH {L} {C} {h} gives {rgb_hex(want)} after RGB565, "
                        f"the files say {rgb_hex(pal[name]['page'])}")
        if screen(pal[name]["page"]) != pal[name]["page"]:
            fail.append(f"{name}: {rgb_hex(pal[name]['page'])} changes in the RGB565 round trip")
        aL, aC, _ = oklch(pal[name]["page"])
        if not (lo_l <= aL <= hi_l and lo_c <= aC <= hi_c):
            fail.append(f"{name}: L {aL:.3f} C {aC:.3f} is outside Moon's accents "
                        f"(L {lo_l:.3f}-{hi_l:.3f}, C {lo_c:.3f}-{hi_c:.3f})")

    # 3. contrast after the round trip
    for name, use in USES.items():
        for kind, need_ratio in (("text", TEXT_MIN), ("mark", MARK_MIN)):
            for bg in use[kind]:
                r = contrast(pal[name]["screen"], pal[bg]["screen"])
                if r < need_ratio:
                    fail.append(f"{name} as {kind} on {bg}: {r:.2f}:1, under {need_ratio}:1")

    # 4. CIEDE2000 between the screen's colours
    for a, b in itertools.combinations(SCREEN, 2):
        d = pair_de(pal, a, b)
        sounds = (a in SOUNDS) + (b in SOUNDS)
        if sounds == 2 or (sounds == 1 and "love" in (a, b)):
            if d < SOUND_MIN:
                fail.append(f"{a}-{b}: ΔE00 {d:.1f}, under {SOUND_MIN}")
        elif sounds == 1 and d < SOUND_OTHER_MIN:
            fail.append(f"{a}-{b}: ΔE00 {d:.1f}, under {SOUND_OTHER_MIN}")
        if d < NEAR and (a, b) not in JUSTIFIED and (b, a) not in JUSTIFIED:
            fail.append(f"{a}-{b}: ΔE00 {d:.1f}, under {NEAR} with no reason in JUSTIFIED")

    # 5. the sound colours under colour-vision deficiencies
    for kind in MACHADO:
        for a, b in itertools.combinations(SOUNDS, 2):
            d = delta_e(simulate(pal[a]["screen"], kind), simulate(pal[b]["screen"], kind))
            if d < CVD_FLOOR:
                fail.append(f"{a}-{b} under {kind}: ΔE00 {d:.1f}, under {CVD_FLOOR}")

    # 6. the roles
    by_token = {}
    for role, token in ROLES.items():
        by_token.setdefault(token, set()).add(role)
        got = hroles.get(role)
        if got is None:
            fail.append(f"C_{role.upper().replace('-', '_')} is not defined in fm1_look.h")
        elif got[1] != token:
            fail.append(f"C_{role.upper().replace('-', '_')} is {got[1]}, the map says {token}")
    for token, roles in by_token.items():
        if token in ACCENTS + SOUNDS and len(roles) > 1 and roles != SHARED.get(token):
            fail.append(f"{token} means {sorted(roles)}: one meaning per colour")
    for role in PAGE_ROLES:
        got = _resolve(cvars, cvars.get(role, ""))
        want = f"{pal[ROLES[role]]['family']}-{ROLES[role]}"
        if got != want:
            fail.append(f"style.css --{role} is {got or 'missing'}, the map says --{want}")
    if _resolve(cvars, cvars.get("focus", "")) != "rp-iris":
        fail.append("style.css --focus is not the selection colour (iris)")
    accents = "|".join(sorted({f"rp-{a}" for a in ACCENTS + ("pine",)} |
                              {f"lm-{s}" for s in DERIVED}))
    for lineno, line in enumerate(css.splitlines(), 1):
        for m in re.finditer(rf"var\(--({accents})\)", line):
            role = re.match(r"\s*--([a-z0-9-]+)\s*:", line)
            if not role or role.group(1) not in ROLES:
                fail.append(f"style.css:{lineno}: var(--{m.group(1)}) outside a role's "
                            "definition; name the role (--select, --held, ...)")
    return fail


# ---- the report ------------------------------------------------------------

def report(header, css):
    pal = palette(header, css)
    out = []
    w = out.append
    lo_l, hi_l, lo_c, hi_c = moon_envelope(pal)
    w("**Derived hues** (OKLCH target, its sRGB, the RGB565 fixed point both files use, "
      "and that colour's own OKLCH):\n")
    w("| Name | Sound | Target L, C, h | sRGB | Token | RGB565 | Token's L, C, h |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for i, name in enumerate(SOUNDS):
        L, C, h = DERIVED[name]
        rgb = oklch_rgb(L, C, h)
        tok = pal[name]["page"]
        aL, aC, ah = oklch(tok)
        w(f"| {name} | S{i + 1} | {L:.2f}, {C:.3f}, {h} | `{rgb_hex(rgb)}` | `{rgb_hex(tok)}` | "
          f"`0x{rgb565(tok):04X}` | {aL:.3f}, {aC:.3f}, {ah:.1f} |")
    w(f"\nMoon's accents span L {lo_l + L_MARGIN:.3f}-{hi_l - L_MARGIN:.3f} and C "
      f"{lo_c:.3f}-{hi_c:.3f} (love, gold, rose, foam, iris; pine left out); the check allows "
      f"L {lo_l:.3f}-{hi_l:.3f}.\n")
    w("**Contrast** after the RGB565 round trip (WCAG 2; text needs 4.5:1, marks 3:1). "
      "Bold: under 4.5:1. A dash: never drawn there as text.\n")
    w("| Colour | " + " | ".join(BACKGROUNDS) + " |")
    w("| --- |" + " ---: |" * len(BACKGROUNDS))
    for name in ("text", "subtle", "muted", "love", "gold", "rose", "pine", "foam", "iris") + SOUNDS:
        cells = []
        for bg in BACKGROUNDS:
            r = contrast(pal[name]["screen"], pal[bg]["screen"])
            s = f"{r:.2f}"
            if r < TEXT_MIN:
                s = f"**{s}**"
            if bg not in USES[name]["text"]:
                s += " –"
            cells.append(s)
        w(f"| {name} | " + " | ".join(cells) + " |")
    w("\n**CIEDE2000** between the colours the screen draws with a meaning (the lower of "
      "the screen's and the page's value):\n")
    w("| | " + " | ".join(SCREEN) + " |")
    w("| --- |" + " ---: |" * len(SCREEN))
    for a in SCREEN:
        cells = []
        for b in SCREEN:
            if a == b:
                cells.append("")
                continue
            d = pair_de(pal, a, b)
            cells.append(f"**{d:.1f}**" if d < NEAR else f"{d:.1f}")
        w(f"| {a} | " + " | ".join(cells) + " |")
    w("\n**The sound colours under colour-vision deficiencies** (Machado 2009, severity 1): "
      "each one's simulated colour, then CIEDE2000 between every two.\n")
    w("| | " + " | ".join(SOUNDS) + " | " +
      " | ".join(f"{a}-{b}" for a, b in itertools.combinations(SOUNDS, 2)) + " |")
    w("| --- |" + " --- |" * len(SOUNDS) + " ---: |" * 6)
    for kind in ("none",) + tuple(MACHADO):
        sim = {s: (pal[s]["screen"] if kind == "none" else simulate(pal[s]["screen"], kind))
               for s in SOUNDS}
        ds = [delta_e(sim[a], sim[b]) for a, b in itertools.combinations(SOUNDS, 2)]
        w(f"| {kind} | " + " | ".join(f"`{rgb_hex(sim[s])}`" for s in SOUNDS) + " | " +
          " | ".join(f"**{d:.1f}**" if d < NEAR else f"{d:.1f}" for d in ds) + " |")
    return "\n".join(out) + "\n"


# ---- the swatch: the colours on a 240 x 240 screen ------------------------

def _font():
    sys.path.insert(0, str(HERE))
    from gen_font import SRC, parse   # noqa: E402  (beside this file)
    return parse(SRC.read_text(encoding="utf-8"))


def swatch(header, css):
    """A 240 x 240 picture in the screen's own font: the title bar with the
    four sounds, each sound's name and bar, then one line per role."""
    pal = palette(header, css)
    c = {k: v["screen"] for k, v in pal.items()}
    font = _font()
    W = H = 240
    px = [[c["base"]] * W for _ in range(H)]

    def fill(x, y, w, h, col):
        for yy in range(max(0, y), min(H, y + h)):
            for xx in range(max(0, x), min(W, x + w)):
                px[yy][xx] = col

    def text(x, y, s, col, scale=2):
        for ch in s:
            rows = font.get(ch, [])
            for r, bits in enumerate(rows):        # bit 4 is the leftmost column
                for k in range(5):
                    if bits >> (4 - k) & 1:
                        fill(x + k * scale, y + r * scale, scale, scale, col)
            x += 6 * scale

    fill(0, 0, W, 24, c["overlay"])
    for i, s in enumerate(SOUNDS):
        text(6 + i * 48, 3, f"S{i + 1}", c[s])
    y = 28
    for i, s in enumerate(SOUNDS):
        text(6, y, f"S{i + 1} {s.capitalize()}", c[s])
        fill(6, y + 22, 228, 7, c["highlight-med"])
        fill(6, y + 22, 60 + 40 * i, 7, c[s])
        y += 36
    fill(0, 172, W, 68, c["surface"])
    text(6, 176, "Ctx", c["rose"])
    text(54, 176, "Held", c["gold"])
    text(114, 176, "Mod", c["foam"])
    text(162, 176, "Refuse", c["love"])
    fill(0, 198, W, 2, c["iris"])
    fill(6, 201, 82, 24, c["iris"])         # a chip: 6 px each side, 3 px over the capitals
    text(12, 204, "Select", c["base"])
    text(114, 204, "Label", c["subtle"])
    fill(0, 238, W, 2, c["iris"])
    return px


def sheet(panels, pal, scale=2, gap=24):
    """The panels side by side at x`scale`, each captioned in the screen's
    font, on the page's base."""
    font = _font()
    bg, ink = pal["base"]["page"], pal["subtle"]["page"]
    side = 240 * scale
    W = len(panels) * side + (len(panels) + 1) * gap
    H = side + 3 * gap + 18
    out = [[bg] * W for _ in range(H)]
    for i, (caption, px) in enumerate(panels):
        x0 = gap + i * (side + gap)
        for y in range(side):
            row = px[y // scale]
            dst = out[gap * 2 + 18 + y]
            for x in range(side):
                dst[x0 + x] = row[x // scale]
        cx = x0
        for ch in caption:
            for r, bits in enumerate(font.get(ch, [])):
                for k in range(5):
                    if bits >> (4 - k) & 1:
                        for dy in range(2):
                            for dx in range(2):
                                out[gap + r * 2 + dy][cx + k * 2 + dx] = ink
            cx += 12
    return out


def write_ppm(path, px):
    h, w = len(px), len(px[0])
    with open(path, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (w, h))
        f.write(bytes(v for row in px for p in row for v in p))


def main(argv):
    args = list(argv)
    mode = "check"
    out_dir = None
    if args and args[0] == "--report":
        mode = "report"
        args.pop(0)
    elif args and args[0] == "--swatch":
        mode = "swatch"
        out_dir = Path(args[1])
        args = args[2:]
    root = Path(args[0]) if args else ROOT
    header, css = load(root)
    if mode == "report":
        sys.stdout.write(report(header, css))
        return 0
    if mode == "swatch":
        out_dir.mkdir(parents=True, exist_ok=True)
        px = swatch(header, css)
        write_ppm(out_dir / "palette.ppm", px)
        panels = [("As seen", px)]
        for kind in MACHADO:
            sim = [[simulate(p, kind) for p in row] for row in px]
            write_ppm(out_dir / f"palette-{kind}.ppm", sim)
            panels.append((kind.capitalize(), sim))
        write_ppm(out_dir / "palette-sheet.ppm", sheet(panels, palette(header, css)))
        print(out_dir / "palette-sheet.ppm")
        return 0
    fail = check(header, css)
    for f in fail:
        print(f"palette: {f}")
    if not fail:
        print("palette: every rule holds")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
