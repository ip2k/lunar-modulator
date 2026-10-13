# SPDX-License-Identifier: MIT
"""Lossless build-time adaptation of the pinned HAL's binary small font.

The vendored input remains unchanged. Reject non-binary alpha rather than
silently degrading a future font. Large-font antialiasing is left intact.
"""
import re


def small_pixels(header):
    match = re.search(r'static const uint8_t FONT_S_DATA\[9120\] = \{(.*?)\};',
                      header, re.S)
    if not match:
        raise ValueError('Pinned small-font data declaration changed')
    data = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', match[1]))
    if len(data) != 9120:
        raise ValueError('Pinned small-font length changed')
    pixels = [n for x in data for n in (x >> 4, x & 15)]
    if any(n not in (0, 15) for n in pixels):
        raise ValueError('Small font has non-binary alpha')
    return match, pixels


def compact_header(header):
    match, pixels = small_pixels(header)
    packed = [sum((pixels[i + b] != 0) << (7 - b) for b in range(8))
              for i in range(0, len(pixels), 8)]
    rows = [', '.join('0x%02x' % x for x in packed[i:i + 24])
            for i in range(0, len(packed), 24)]
    declaration = ('/* Losslessly packed from pinned FONT_S_DATA. */\n'
                   'static const uint8_t FONT_S_DATA[2280] = {\n    ' +
                   ',\n    '.join(rows) + '\n};')
    header = header[:match.start()] + declaration + header[match.end():]
    offsets = re.search(r'static const uint16_t FONT_S_OFF\[95\] = \{(.*?)\};', header)
    if not offsets or [int(x) for x in offsets[1].split(',')] != list(range(0, 9120, 96)):
        raise ValueError('Pinned small-font offsets changed')
    header = header[:offsets.start()] + ('static const uint16_t FONT_S_OFF[95] = {' +
             ', '.join(str(x) for x in range(0, 2280, 24)) + '};') + header[offsets.end():]
    # Width/height are part of the contiguous bit indexing contract.
    widths = re.search(r'FONT_S_BW\[95\] = \{(.*?)\};', header)
    if not widths or [int(x) for x in widths[1].split(',')] != [12] * 95:
        raise ValueError('Pinned small-font widths changed')
    if 'FONT_S = { 16, 2, 32, 126,' not in header:
        raise ValueError('Pinned small-font metrics changed')
    return header


def compact_gfx(source):
    old = '''uint32_t v = gd[gy * bpr + gx / 2u];
                v = (gx & 1u) ? (v & 15u) : (v >> 4);'''
    new = '''uint32_t v;
                if (f == &FONT_S) {
                    uint32_t bit = gy * w + gx;
                    v = ((gd[bit >> 3] >> (7u - (bit & 7u))) & 1u) * 15u;
                } else {
                    v = gd[gy * bpr + gx / 2u];
                    v = (gx & 1u) ? (v & 15u) : (v >> 4);
                }'''
    if source.count(old) != 1:
        raise ValueError('Pinned glyph decoder changed')
    return source.replace(old, new)
