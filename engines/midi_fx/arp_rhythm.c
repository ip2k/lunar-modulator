/* arp_rhythm.c -- the arpeggiator's rhythm tables (fm1_arp.h).
 *
 * Both come from Yarns (Emilie Gillet, MIT), regenerated here rather than
 * vendored:
 * - The 22 rhythm masks are the values Yarns' table generator makes from its
 *   x-o strings (yarns/resources/lookup_tables.py 124-152, XoxTo16BitInt
 *   107-118, at pichenettes/eurorack 08460a6; Yarns ships them as
 *   lut_arpeggiator_patterns in yarns/resources.cc 111-117). Each value
 *   carries its string; tests/test_engine_arp.py rebuilds the values from
 *   the strings and, when reference/mi-eurorack is cloned, compares them with
 *   Yarns' table.
 * - The Euclidean masks are computed, not stored: fm1_arp_euclid_mask()
 *   reimplements the generator's EuclideanPattern (lookup_tables.py 169-188)
 *   on fixed arrays, instead of Yarns' 4,096-byte lut_euclidean. The test
 *   checks all 32 x 32 entries the same way.
 *
 * Yarns' notice, for the masks:
 *
 *   Copyright 2014 Emilie Gillet.
 *
 *   Permission is hereby granted, free of charge, to any person obtaining a
 *   copy of this software and associated documentation files (the
 *   "Software"), to deal in the Software without restriction, including
 *   without limitation the rights to use, copy, modify, merge, publish,
 *   distribute, sublicense, and/or sell copies of the Software, and to
 *   permit persons to whom the Software is furnished to do so, subject to
 *   the following conditions:
 *
 *   The above copyright notice and this permission notice shall be included
 *   in all copies or substantial portions of the Software.
 *
 *   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 *   OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 *   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 *   IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 *   CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 *   TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 *   SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * The rest of this file: MIT licence, like the rest of this repository.
 */
#include "fm1_arp.h"

/* 'o' plays, '-' rests; the first character is bit 0. */
static const uint16_t kPatterns[22] = {
  21845u,  /* o-o- o-o- o-o- o-o- */
  62965u,  /* o-o- oooo o-o- oooo */
  46517u,  /* o-o- oo-o o-o- oo-o */
  54741u,  /* o-o- o-oo o-o- o-oo */
  43861u,  /* o-o- o-o- oo-o -o-o */
  22869u,  /* o-o- o-o- o--o o-o- */
  38293u,  /* o-o- o--o o-o- o--o */
  2313u,   /* o--o ---- o--o ---- */
  37449u,  /* o--o --o- -o-- o--o */
  21065u,  /* o--o --o- -o-- o-o- */
  18761u,  /* o--o --o- o--o --o- */
  54553u,  /* o--o o--- o-o- o-oo */
  27499u,  /* oo-o -oo- oo-o -oo- */
  23387u,  /* oo-o o-o- oo-o o-o- */
  30583u,  /* ooo- ooo- ooo- ooo- */
  28087u,  /* ooo- oo-o o-oo -oo- */
  22359u,  /* ooo- o-o- ooo- o-o- */
  28527u,  /* oooo -oo- oooo -oo- */
  30431u,  /* oooo o-oo -oo- ooo- */
  43281u,  /* o--- o--- o--o -o-o */
  28609u,  /* o--- --oo oooo -oo- */
  53505u,  /* o--- ---- o--- o-oo */
};

uint16_t fm1_arp_pattern_mask(unsigned pattern) {
  if (pattern == 0u || pattern > 22u) return 0xFFFFu;
  return kPatterns[pattern - 1u];
}

/* EuclideanPattern(k, n): start from k groups [1] and n-k groups [0]; while
 * k, merge the first `cut` groups with the `cut` groups after the first k,
 * cut = min(k, groups - k), and keep the rest in order; then flatten. A
 * group is a bit string (first bit in bit 0) and its length. */
uint32_t fm1_arp_euclid_mask(unsigned len, unsigned fill) {
  uint32_t bits[32], nbits[32];
  uint8_t glen[32], nlen[32];
  unsigned groups, k, i, cut, n, pos;
  uint32_t mask = 0u;
  if (len == 0u || len > 32u) return 0u;
  k = fill < len ? fill : len;
  groups = len;
  for (i = 0u; i < len; ++i) {
    bits[i] = i < k ? 1u : 0u;
    glen[i] = 1u;
  }
  while (k) {
    cut = k < groups - k ? k : groups - k;
    n = 0u;
    for (i = 0u; i < cut; ++i) {
      nbits[n] = bits[i] | (bits[k + i] << glen[i]);
      nlen[n] = (uint8_t)(glen[i] + glen[k + i]);
      ++n;
    }
    for (i = cut; i < k; ++i) {
      nbits[n] = bits[i];
      nlen[n] = glen[i];
      ++n;
    }
    for (i = k + cut; i < groups; ++i) {
      nbits[n] = bits[i];
      nlen[n] = glen[i];
      ++n;
    }
    for (i = 0u; i < n; ++i) {
      bits[i] = nbits[i];
      glen[i] = nlen[i];
    }
    groups = n;
    k = cut;
  }
  pos = 0u;
  for (i = 0u; i < groups; ++i) {
    mask |= bits[i] << pos;
    pos += glen[i];
  }
  return mask;
}
