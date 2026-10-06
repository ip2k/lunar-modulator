"""The canonical JSON layout of Lunar Modulator's files, as an executable
reference (notes/2026-10-06-state-files.md §7.2; engines/state/README.md).

This is the test suite's statement of the layout that the C writer (stage
E3), the Python reader (stage P1) and the web editor must produce byte for
byte. It does not know engines: member order inside an object is the order
the object was built in (json.loads keeps a file's order), and the tests
check that order separately.

- UTF-8, no byte-order mark, LF line ends, a final newline.
- Two spaces of indent; ": " after a key; one member or item per line.
- Inline on one line, with ", " between items: an array whose items are all
  numbers, and the value of a member named in INLINE (refs and small
  records whose values are all scalars).
- Empty containers are {} and [].
- Strings: raw UTF-8; only '"', '\\' and U+0000..U+001F are escaped, as
  \\" \\\\ \\b \\f \\n \\r \\t or \\u00XX (lower-case hex); '/' is not
  escaped.
- Numbers: an int is written in plain digits. A float is a float32: the
  writer finds the shortest decimal (at most 9 significant digits) that
  reads back to the same float32 (read exactly, as every reader reads it:
  f32_of), and writes it as ECMAScript's
  Number::toString writes that decimal's double (so a JavaScript writer is
  String(Number(Math.fround(v).toPrecision(p))) for the smallest p that
  round-trips). -0 is written 0. NaN and infinities are never written.
"""
from decimal import Decimal
from fractions import Fraction
import json
import math
import struct

INLINE = frozenset({"made", "key", "data", "from", "via", "to", "view"})


FLT_MAX = 3.4028234663852886e38


def f32(x):
    """x rounded to the nearest float32, as a Python float. Past FLT_MAX by
    less than half its ulp (2^103) that is FLT_MAX, as strtof gives, where
    struct refuses ("3.4028235e+38" is FLT_MAX's shortest decimal)."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(FLT_MAX if abs(x) < FLT_MAX + 2.0 ** 103 else math.inf, x)


def _js_digits(x):
    """ECMAScript Number::toString of a finite double x != 0, from its
    shortest round-trip digits (Python's repr gives the same digits)."""
    sign, digits, exp = Decimal(repr(x)).normalize().as_tuple()
    s = "".join(map(str, digits))
    k = len(s)
    n = exp + k                     # value = 0.s x 10^n
    out = "-" if sign else ""
    if k <= n <= 21:
        return out + s + "0" * (n - k)
    if 0 < n <= 21:
        return out + s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return out + "0." + "0" * (-n) + s
    e = n - 1
    mant = s[0] + ("." + s[1:] if k > 1 else "")
    return out + mant + "e" + ("+" if e > 0 else "-") + str(abs(e))


def f32_of(dec):
    """The float32 nearest to decimal text `dec` in exact arithmetic (ties to
    even), as a Python float; None beyond FLT_MAX. This is what every
    reader does (the C reader's fm1_num_f32 is held to it), so a writer's
    shortest decimal is chosen against it, not against double rounding."""
    fr = Fraction(dec)
    if fr == 0:
        return 0.0
    a = abs(fr)
    e = a.numerator.bit_length() - a.denominator.bit_length() - 24
    while a >= Fraction(2) ** (e + 24):
        e += 1
    while e > -149 and a < Fraction(2) ** (e + 23):
        e -= 1
    e = max(e, -149)
    q = a / Fraction(2) ** e
    m = q.numerator // q.denominator
    r = q - m
    if r > Fraction(1, 2) or (r == Fraction(1, 2) and m % 2):
        m += 1
    if m * Fraction(2) ** e > (2 ** 24 - 1) * Fraction(2) ** 104:
        return None
    x = float(m * Fraction(2) ** e)
    return -x if fr < 0 else x


def number(v):
    """A number's canonical text: ints as they are, floats as float32."""
    if isinstance(v, bool):
        raise TypeError("a bool is not a number")
    if isinstance(v, int):
        return str(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("NaN and infinities are never written")
    v = f32(v)
    if v == 0:
        return "0"
    for p in range(1, 10):
        s = "%.*g" % (p, v)
        if f32_of(s) == v:
            return _js_digits(float(s))
    raise AssertionError("9 digits always round-trip a float32")


def string(s):
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 0x20:
            out.append({8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}.get(o, "\\u%04x" % o))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return string(v)
    return number(v)


def _inline(v):
    if isinstance(v, dict):
        return "{" + ", ".join(string(k) + ": " + _inline(x) for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(_inline(x) for x in v) + "]"
    return _scalar(v)


def _is_inline(key, v):
    if isinstance(v, list):
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    if isinstance(v, dict):
        return key in INLINE and not any(isinstance(x, (dict, list)) for x in v.values())
    return True


def _write(v, key, indent, out):
    if _is_inline(key, v) or not v:
        out.append(_inline(v))
        return
    pad = "  " * (indent + 1)
    if isinstance(v, dict):
        out.append("{\n")
        items = list(v.items())
        for i, (k, x) in enumerate(items):
            out.append(pad + string(k) + ": ")
            _write(x, k, indent + 1, out)
            out.append(",\n" if i + 1 < len(items) else "\n")
        out.append("  " * indent + "}")
    else:
        out.append("[\n")
        for i, x in enumerate(v):
            out.append(pad)
            _write(x, None, indent + 1, out)
            out.append(",\n" if i + 1 < len(v) else "\n")
        out.append("  " * indent + "]")


def dumps(doc):
    """doc in the canonical layout, final newline included."""
    out = []
    _write(doc, None, 0, out)
    return "".join(out) + "\n"


def compact(doc):
    """The form a #lunar= link deflates: the canonical tokens, numbers
    included, with no white space (any valid JSON loads; links need not be
    canonical)."""
    if isinstance(doc, dict):
        return "{" + ",".join(string(k) + ":" + compact(x) for k, x in doc.items()) + "}"
    if isinstance(doc, list):
        return "[" + ",".join(compact(x) for x in doc) + "]"
    return _scalar(doc)


def loads(text):
    """json.loads that refuses duplicate keys, as every reader must."""
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError("duplicate key %r" % k)
            d[k] = v
        return d
    return json.loads(text, object_pairs_hook=pairs)


# ---- Amounts and offsets: percent <-> Q1.14 ------------------------------------
def q14(percent):
    """A cable's amount or offset as the runtime keeps it: q =
    round(percent x 16384 / 100), ties away from zero, in exact arithmetic
    on the file's decimal, after clamping to -100..100."""
    f = Fraction(str(percent))
    f = max(Fraction(-100), min(Fraction(100), f))
    v = f * 16384 / 100
    n = math.floor(abs(v) + Fraction(1, 2))
    return n if v >= 0 else -n


def percent(q):
    """The decimal a writer gives Q1.14 value q: the shortest (at most 3
    decimals) that q14() maps back to q, the nearest one when several of
    that length do; an int when it has no decimals."""
    exact = Fraction(q * 100, 16384)
    for d in range(4):
        s = exact * 10 ** d
        n = math.floor(abs(s) + Fraction(1, 2))
        r = Fraction(n if s >= 0 else -n, 10 ** d)
        if q14(r) == q:
            return int(r) if d == 0 else float(r)
    raise AssertionError("3 decimals always reach a Q1.14 value")
