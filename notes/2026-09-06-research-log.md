# 2026-09-06 — research log (session 1, no hardware)

Environment: a cloud Claude Code sandbox with no USB, no ALSA, and an egress
proxy that blocked several sites. Repositories were cloned read-only through
the proxy. The user's FM-1 and the `M-UPGRADE-FM1.app` disk image were on the
user's MacBook and were **not** reachable from the sandbox.

## What was done

1. Web search for the FM-1, its teardown and firmware; found aroum/fm1-custom-fw
   and, through it, AL-255/FM-1-RE, kagaimiq's JieLi corpus, probonopd's
   SMK-37 Pro gist, fm1-editor.com, the AC79 SDK.
2. Cloned and read: aroum (README, scripts, all five PCB photos),
   AL-255 (`README`, `TODO_aug2.md`, `docs/architecture.md`,
   `docs/03-dx7-core-identification.md`, `docs/04-toolchain-and-vendoring.md`,
   `docs/reversing/01-hardware-map.md`, `docs/io/01-boot.md` (head),
   `05-midi.md` (head), `06-usb.md` (head), `07-input.md`, `08-display.md`,
   `09-storage.md` (head), `02-rtos.md` (head), `04-synth-engine.md` (head),
   `11-ota-protocol.md`, `tools/README.md`, `firmware-images/*`; branch
   `with-custom-firmware`: `10-rebuild-guide.md`, `05-reconstruction-plan.md`,
   `TODO_Aug1.md`, `firmware/Makefile`, `firmware/link.ld`,
   `tools/legacy-uboot/README.md`, file list), kagaimiq/jielie (`isp/*`,
   `chips/index.md`, `cpu/index.md`, `cpu/pi32v2.md` head, `datafmt/newfw.md`
   head, `misc/usb-ids.md`), jl-uboot-tool (`README`, `docs/how-to-enter-uboot.md`,
   `what-is-uboot.md`, `usb-protocol.md` head, `data/chips.yaml`,
   `data/usb-loaders.yaml`), jl-misctools (file list), schwung-movy
   (`README`, `DESIGN.md`, `IMPLEMENTATION.md`, `module.json`, `engine/`
   layout and line counts), and a blobless clone of
   jeffreywugz/fw-AC79_AIoT_SDK (`README`, `Makefile`, `cpu/wl82/*` listing,
   `cpu/wl82/tools/isd_config.ini`, `download.bat`, `WL82.h` head,
   `demo_hello`, `doc/` listing).
3. Own checks on AL-255's unpacked V13/V14 images: located the msfa algorithm
   table (`tools/check_msfa_table.py`), listed build stamps and feature
   strings, decoded parts of `isd_config.ini` (`SDRAM_SIZE = 0`), confirmed
   `uboot.boot` size 14384 and SHA-256 `730e54f0…d3ef`, and measured the
   `.fwsc` trailer geometry (`JLUFW` at end−16 in both versions;
   `AC791N` at `0x424`) used by `tools/extract_fwsc_from_updater.py`.
4. Tested the extractor on synthetic updaters built from the V13/V14 packages
   (single slice, fat binary with a decoy trailer): byte-identical carves.
5. Attempted to create `ip2k/mvave-fm1-open-firmware` via the GitHub
   integration: `403 Resource not accessible by integration`. Fallback: orphan
   branch on `ip2k/busybar-dual-timer`. (The repository was published under
   that name later on 2026-09-06 and renamed `ip2k/lunar-modulator`, with the
   project, on 2026-10-01.)

## Numbers worth keeping

| Item | Value |
| --- | --- |
| V13 `FM-1.fwsc` | 704084 B; `app.bin` 583068 B; identity `FM-1_009` |
| V14 `FM-1.fwsc` | 704052 B, sha256 `a1adca99…62d3`; `app.bin` sha256 `54a32371…0443`, +1888 B vs V13; identity `FM-1_014` |
| `uboot.boot` | 14384 B, sha256 `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`, = AC79 SDK `AC79NN_SDK_V1.1.9_2023-08-01` |
| msfa table | V13 `0x8C46C`, V14 `0x8CBCC`; algs 4/6 first byte `0x41` |
| OTA loader | `usb_hid_ota.bin`, 19969 B packed / 23324 B unpacked, load `0x01C0A800`; `ota.bin` at fwsc `0xA6F34` (V13) |
| Chip key | `0x980F` (SFC cipher); header key `0xFFFF` |
| Stack tops | `0x01C14BB4` (main), `0x01C15BB4` (system) |
| RAM use | `.data` 0x9E7C + `.bss` 0x17380 |
| Update-lib stamps | `INCLUDE_UPDATE-$0c1663e`, `UPDATE-*modified*-tanchiquan-@20230817-$2374938` |
| wl82 USB loader | `wl82loader.bin` @ `0x1C02000`, protocol v2, MengLi cipher (jl-uboot-tool) |
| Ableton Move | quad Cortex-A72 1.5 GHz, 2 GB RAM, 64 GB |

## Blocked from the sandbox (need a human or a local session)

cuvave.com, m.media-amazon.com (manual PDF), manuals.plus, synthanatomy.com,
fwradar.com, elektronauts.com, gearspace.com, reddit.com, fm1-editor.com,
kagaimiq.github.io, gitee.com, madushan.caas.lk. PDF rendering tools were not
installed, so the AC7911B datasheet in the SDK was fetched but not read.

## Judgement calls

- Reported AL-255's "LQFP48" over the SMK-37 community's "QFN48": the FM-1
  photo shows leads.
- Called the algorithm 4/6 `0x41` variant "Dexed-family" [inferred]; the copy
  of `fm_core.cpp` in AL-255's branch still has msfa's `0xC1`, so the stock
  firmware's table did not come from that exact file. Verify upstream.
- Did not copy aroum's photos (no license); linked instead.
- Created the repository private-by-intent; the user decides when to publish.
