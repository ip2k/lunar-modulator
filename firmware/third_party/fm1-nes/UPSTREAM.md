# fm1-nes (Keitark) — the boot_info bridge and the key/encoder tables

`boot_compat.c` and `fm1_keys.{c,h}` here are derived from [fm1-nes](https://github.com/Keitark/fm1-nes)
by Keitark, Apache License 2.0 (`LICENSE` in this directory is that
repository's licence; it has no NOTICE file). These files stay under
Apache-2.0; the rest of Lunar Modulator is MIT. Apache-2.0 code may be
combined with the MIT tree and with JieLi's Apache-2.0 SDK, and does not
carry the GPL's distribution limits (CLAUDE.md, "Project status and
licences").

| Upstream file | Commit | Git blob | Here |
| --- | --- | --- | --- |
| `firmware/nes/boot/boot_compat.c` | `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` (main, 2026-10-03) | `06a5a74468e4ca29bc433f3e166ea2e0cac6dbca` | `boot_compat.c` |
| `firmware/nes/src/fm1_stock_keys.c` | `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` | `b0dae08eb03b599378140c6e41648c53981050d8` | `fm1_keys.c` (key cells, pack, decode) |
| `firmware/usb-diag/peripheral_logic.c` | `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` | `e982fa83f9fd00c01cbe8770a351bc02ce9ed9bc` | `fm1_keys.c` (encoder contacts, names, sampler) |

**`fm1_keys.{c,h}` changes** (Lunar Modulator, 2026-11-08, Apache-2.0 kept):
the 41 key cells and 14 encoder contacts are re-indexed from fm1-nes's
scan-phase labels (high nibble) to the physical 595 column that was selected
when the rows were read, `column = (label + 10) % 11`. That mapping agrees
41/41 with the physical key map of a second, independently written source
(Felucca's GPL-3.0 HAL, used as a fact cross-check only; nothing copied). The
64-bit pressed mask became two 32-bit words, so the SDK-free pi32v2 link needs
no 64-bit helper; `<stdint.h>`/`<string.h>` and `fm1_stock_assign_note_keys`
(fm1-nes's Famicom pad mapping) were dropped; NULL guards were added. The
column pack expression, the encoder A/B combination, the 0x2814/0x4182
direction masks and the two-identical-samples filter are fm1-nes's, unchanged.
The pin and register work around them (595 shifting, LEDs, row pins) is
Lunar's own MIT code in `firmware/board/`. fm1-nes's tables come from stock
`FM-1_010`; re-deriving them from V15 is still open.

**Changes** (Lunar Modulator, 2026-10-05): a longer header comment, named
constants for the 6 stock and 23 SDK hand-off words, and a `defined()` guard
around the `__SDRAM_SIZE__` check. The copy-6, zero-6..22, call-the-real-one
logic and the `--wrap=boot_info_init` mechanism are fm1-nes's, unchanged.

**Not taken:** fm1-nes's `audit_boot.py` (its exact byte pins belong to its
own link), and every file of that repository not listed above. Lunar's own link gate is
`tools/jieli/audit_link.py` (MIT), modelled on it but written here.

The desktop test driver `firmware/boot/boot_compat_test.c` and
`tests/test_boot_compat.py` are Lunar's own (MIT).

The upstream `PROVENANCE.md` says the 6-word hand-off contract comes from its
author's stock analysis; `notes/2026-10-05-softkey-efuse.md` §3 re-checked it
here against both SPLs and the V1.2.x `boot.c` [verified].
