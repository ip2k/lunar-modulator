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
