# FM-1-transporter (kurogedelic), Pico 2 support files

- **Upstream:** <https://github.com/kurogedelic/FM-1-transporter>, pinned at
  `a7fb5e8ac692c528f8ed29e325911a3f4b8111d6`. MIT, Copyright (c) 2026
  kurogedelic; the licence is in [`LICENSE.upstream`](LICENSE.upstream).
- **What is here:**
  - `0001-pico2-reject-false-d-pullups.patch` modifies upstream
    `pio/usb_key.pio` and `src/recovery.c` and stays under upstream's MIT
    licence. Upstream lists the Pico 2 as "builds, untested". Without the
    patch, a Pico 2 W stopped keying within milliseconds even with no target
    powered (docs/17 §5).
  - `fm1t_m5.py` is adapted from upstream `tools/fm1t.py` at `a7fb5e8`
    (identical at `80c5012`) and stays under upstream's MIT licence
    (`LICENSE.upstream`). It is the M5 host tool
    (`notes/2026-11-08-ram-runner-devkit.md` §4.2, docs/19):
    - there is no soft-key path (`uboot`, `ensure_uboot`) and the console
      port is never opened;
    - `ramrun` is fixed to the one approved image, address `0x01C02000` and
      argument 1, and never uploads the loader; the send gate carries the
      image's bytes only, inside `[0x01C02000, 0x01C03040)`, and a lock file
      allows one attempt per run directory;
    - `info`/`dump` only read flash: no `write`, `selftest-write`,
      `runapp` or `wsec`;
    - an allow-list gates every line it sends, and a JSONL receipt records
      every line sent and received;
    - `compare` is deliberately stricter than upstream's: two dumps must be
      byte-identical over the whole 1 MiB, because V15 never runs between
      the M5 dumps.
  - `fm1t_m6.py` is a copy of `fm1t_m5.py` (same licence) with only the
    approved image swapped for M6's (`m6.bin`, build `m6-plan-2`, three
    `memw` chunks inside `[0x01C02000, 0x01C04644)`), its own lock file, a
    refusal of M5's run directory (docs/20), and one hardening from review:
    `memw`/`memr`/`ldr` lengths must be plain decimal with no leading zero,
    because the transporter parses them with `strtoul(..., 0)`, which reads a
    leading `0` as octal. `tests/test_fm1t_m6.py` pins
    every code line on which the two differ. `fm1t_m5.py` was patched with the
    same length rule on 2026-11-10 (owner: "Patch M5 too"), changing only its
    `memw`/`memr`/`ldr` patterns; its new hash awaits the owner's approval.
  - `fm1t_m8.py` (same licence) keeps `fm1t_m6.py`'s port pin, loader pin,
    `info` check, allow-listed `Link` and JSONL receipt, drops `memw`/`jump`,
    and adds the two flash writes of M8 (docs/22): `install` of an
    owner-approved package (none approved yet) and `restore` to stock V15,
    both by `wsec` inside `[0x4000, 0x93000)` only, each sector read back,
    with two identical full reads before and one after. The port is pinned
    to the bench transporter's serial `560A5ACCF298BDCB`. Its lock lives in
    `~/.local/state/fm1t_m8/`, keyed by package hash. `tests/test_fm1t_m8.py`
    extends the M5 fake with the transporter's real `wsec` behaviour.
  - `build.sh`, the research shim and this file are this repository's own
    (MIT).
- **Not here, on purpose:**
  - No built UF2s; `build.sh` makes them.
  - Not JieLi's `wl82loader.bin`; get it from kagaimiq's
    [jl-uboot-tool](https://github.com/kagaimiq/jl-uboot-tool).
  - No firmware package (`.fwsc`); docs/02 §1 names the source and hash.
- **`research-shim/`** stands in for the private `fm-1-research-lab` modules
  that upstream `tools/fm1t.py write` imports:
  - `fm1_ota.require_reviewed` accepts exactly one package, stock V15
    (SHA-256 `db1642b2…db8a`), and refuses everything else.
  - `fm1fw.Firmware` returns that package's raw flash image: type 0,
    `0x93000` bytes at file offset `0x414`.
  - It is narrower than the original, not a replacement for its review of
    other packages.
- **Upstreaming:** the patch is a candidate fix for upstream. Proposing it
  follows the `oss-contributions` house rules and needs the owner's sign-off.
