# fm1-nes (Keitark) — the boot_info bridge

`boot_compat.c` here is derived from [fm1-nes](https://github.com/Keitark/fm1-nes)
by Keitark, Apache License 2.0 (`LICENSE` in this directory is that
repository's licence; it has no NOTICE file). This file stays under
Apache-2.0; the rest of Lunar Modulator is MIT. Apache-2.0 code may be
combined with the MIT tree and with JieLi's Apache-2.0 SDK, and does not
carry the GPL's distribution limits (CLAUDE.md, "Project status and
licences").

| Upstream file | Commit | Git blob | Here |
| --- | --- | --- | --- |
| `firmware/nes/boot/boot_compat.c` | `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` (main, 2026-10-03) | `06a5a74468e4ca29bc433f3e166ea2e0cac6dbca` | `boot_compat.c` |

**Changes** (Lunar Modulator, 2026-10-05): a longer header comment, named
constants for the 6 stock and 23 SDK hand-off words, and a `defined()` guard
around the `__SDRAM_SIZE__` check. The copy-6, zero-6..22, call-the-real-one
logic and the `--wrap=boot_info_init` mechanism are fm1-nes's, unchanged.

**Not taken:** fm1-nes's `audit_boot.py` (its exact byte pins belong to its
own link), and every other file of that repository. Lunar's own link gate is
`tools/jieli/audit_link.py` (MIT), modelled on it but written here.

The desktop test driver `firmware/boot/boot_compat_test.c` and
`tests/test_boot_compat.py` are Lunar's own (MIT).

The upstream `PROVENANCE.md` says the 6-word hand-off contract comes from its
author's stock analysis; `notes/2026-10-05-softkey-efuse.md` §3 re-checked it
here against both SPLs and the V1.2.x `boot.c` [verified].
