"""Advance widths for the diagrams' text, so a layout can size boxes and the
checker can find every word's box without a font renderer.

The diagrams name IBM Plex Sans first (the manual's face, SIL OFL 1.1; the
PDF's build installs it), then Helvetica Neue and Arial, which a browser
without Plex falls back to. Each width here is the largest of the three
faces' advance widths for that character, at weight 400 (Plex Regular,
Helvetica Neue, Arial) and 600 (Plex SemiBold, Helvetica Neue Bold, Arial
Bold), in thousandths of an em, without kerning: so a line measured here is
never narrower than it is set in any of them. Read with fontTools from IBM
Plex Sans 6.1.1 (Ubuntu 24.04's fonts-ibm-plex) and macOS 26's Helvetica
Neue and Arial, 2026-10-06. Arial's widths are Liberation Sans's, which
Linux uses in its place. A character missing here counts as a full em.

MIT licence, like the rest of this repository.
"""
from __future__ import annotations

# Glyph extents for a line set at size s, from its baseline: the tallest
# ascender and the deepest descender of the three faces, rounded up.
ASCENT = 0.81
DESCENT = 0.22

_CHARS_400 = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~–—→←↑↓↔×·…’‘“”≥≤±÷°½¼µ•√≈'
_WIDTHS_400 = (
    278, 284, 426, 713, 598, 1000, 694, 278, 335, 335, 450, 600, 278, 399, 278, 383,
    600, 600, 600, 600, 600, 600, 600, 600, 600, 600, 292, 292, 600, 600, 600, 557,
    1016, 667, 685, 723, 723, 667, 611, 778, 723, 400, 519, 667, 557, 871, 723, 778,
    667, 778, 723, 667, 611, 723, 667, 944, 667, 667, 611, 317, 383, 317, 600, 565,
    600, 557, 593, 537, 593, 557, 324, 574, 568, 250, 250, 527, 272, 873, 568, 574,
    593, 593, 367, 500, 351, 568, 500, 768, 518, 500, 500, 343, 314, 343, 600, 588,
    1000, 1000, 1000, 820, 820, 1000, 600, 334, 1000, 278, 278, 475, 474, 600, 600, 600,
    600, 468, 872, 847, 577, 396, 600, 600,
)
_CHARS_600 = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~–—→←↑↓↔×·…’‘“”≥≤±÷°½¼µ•√≈'
_WIDTHS_600 = (
    278, 334, 475, 656, 600, 1000, 723, 278, 337, 337, 556, 600, 298, 407, 298, 437,
    600, 600, 600, 600, 600, 600, 600, 600, 600, 600, 334, 334, 600, 600, 600, 611,
    976, 723, 723, 741, 741, 667, 611, 778, 741, 423, 557, 723, 611, 907, 741, 778,
    667, 778, 723, 667, 611, 741, 667, 949, 667, 667, 648, 334, 437, 334, 600, 559,
    600, 574, 611, 574, 611, 574, 350, 611, 611, 278, 278, 574, 294, 906, 611, 611,
    611, 611, 393, 557, 374, 611, 557, 819, 557, 557, 519, 390, 376, 390, 600, 588,
    1000, 1000, 1000, 876, 876, 1000, 600, 350, 1000, 292, 292, 517, 517, 600, 600, 600,
    600, 470, 889, 892, 593, 420, 600, 600,
)

_TABLES = {
    400: dict(zip(_CHARS_400, _WIDTHS_400)),
    600: dict(zip(_CHARS_600, _WIDTHS_600)),
}


def text_width(text: str, size: float, weight: int = 400) -> float:
    """The width of `text` set at `size` units in `weight` (400 or 600)."""
    table = _TABLES[600 if weight >= 500 else 400]
    return sum(table.get(ch, 1000) for ch in text) * size / 1000.0


def missing(text: str) -> list[str]:
    """Characters of `text` the tables do not know (each measured as an em)."""
    return sorted({ch for ch in text if ch not in _TABLES[400]})
