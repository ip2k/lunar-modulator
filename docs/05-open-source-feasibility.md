# 05 — Can the FM-1 run a wholly open-source firmware?

Short answer: **an open application is feasible and most of the hard analysis
is already done; a *wholly* open stack is bounded by JieLi's closed compiler
and libraries, and the whole effort is gated by one unsolved safety problem —
there is no proven way to recover a bricked FM-1.**

## 1. What "open" can mean on this chip

| Level | What runs | What stays closed | Effort | Status |
| --- | --- | --- | --- | --- |
| **L0** | stock M-VAVE firmware | everything | — | shipping |
| **L1 — open application on the vendor stack** | our C/C++ application (synth, UI, MIDI, sequencer) built with the AC79 SDK: Apache-2.0 sources, headers, linker scripts | JieLi's Clang/LLVM 4.0.1 toolchain (binary), the SDK's `.a` libraries you link (`cpu.a`, `system.a`, `fs.a`, `btstack.a`, `btctrler.a`, `audio_server.a`, `ui.a`, …), the mask ROM | months for a usable synth | AL-255 built and linked a demo blob this way; never executed on device |
| **L2 — blob-free application** | own drivers written against the public `WL82.h` register map and kagaimiq's peripheral notes; own RTOS or bare-metal scheduler; msfa engine; USB device stack from the open `usb.h` API or written fresh | toolchain and mask ROM; **Bluetooth** (the controller firmware and stack are closed; BLE-MIDI would need an open BLE stack on JieLi's radio, which nobody has done) | long; realistic without Bluetooth first | not started by anyone |
| **L3 — open toolchain** | a GCC or LLVM backend for pi32v2 | mask ROM only | very long; the ISA is documented (kagaimiq opcode tables, ghidra-jieli SLEIGH, the vendor objdump as an oracle) but nobody has written a compiler backend | not started |
| **L4 — open bootloader** | JieLi's Apache-2.0 `fw-Bootloader` builds `uboot.boot` for wl82 | mask ROM | small once L1 works | available today |

"Wholly open source" in the strict sense means L2 + L3 + L4. Honest framing:
that is a multi-year community project, comparable to what happened around
Allwinner or Espressif chips before mainline support. The pragmatic and still
very valuable goal is **L1 now, L4 early, L2 incrementally, L3 if a contributor
wants a compiler project**. An L1 firmware already gives users: an open synth
they can modify, sound compatibility with stock (same engine, DX7 banks), and a
platform for features M-VAVE will never ship.

## 2. What makes it feasible

1. **The chip is documented enough.** Register map in `WL82.h`, SDK drivers as
   reference code, datasheets in the SDK, the ISA documented by kagaimiq, and
   AL-255's 2062-function map of the stock app showing exactly how the vendor
   drives the DAC, SPI display, key matrix, ADC, USB and flash on this board.
2. **The toolchain exists and runs on Linux.** Closed, but freely downloadable,
   and AL-255 compiled C++11 for pi32v2 with it (`-fno-exceptions -fno-rtti`,
   libc/libm/compiler-rt provided). No Windows needed to compile; the vendor's
   packing tools are Windows executables, but AL-255's `build_fwsc.py`
   re-implements the container in Python and `isd_download` has a Linux
   post-build package.
3. **The synth engine is open.** msfa/Synth_Dexed is the same engine; porting
   is a matter of build flags and a DAC ring buffer, not DSP research.
4. **The update path has no cryptography.** CRC16 only; the chip key is in the
   package. Nothing legal or cryptographic stands between us and the flash.
5. **Headroom.** 12 voices use one core at 240 MHz with 578 KB SRAM barely
   touched; a second core sits idle. More voices, better effects, a real
   sequencer and a richer UI are all within budget.
6. **Precedent on the platform.** JieLi chips are hacked regularly (kagaimiq's
   tools, the esp8266.ru community, probonopd's SMK-37 Pro notes); the mask-ROM
   USB boot and the SCSI download protocol are understood for many siblings and
   the wl82 loader blob is in hand.

## 3. What blocks it

### 3.1 No proven recovery path (the real blocker)

- Single application bank; an interrupted or bad write leaves nothing to fall
  back to.
- No debug pads, no recovery button; `RESET=PB01_08_0` only resets.
- The stock OTA needs the stock application running; it cannot rescue a device
  whose app does not boot, and it has never accepted a non-stock package.
- JieLi's mask-ROM USB boot mode (`UBOOT1.00`) *should* be reachable through
  the USB connector with the `USB_KEY` signal, and would allow full dump and
  restore with `jl-uboot-tool` (`wl82loader.bin`) or the vendor's
  `isd_download`. **This has never been demonstrated on an FM-1.** Until it
  is, every custom flash risks a permanent brick. docs/07 is the plan to close
  this.

### 3.2 The verifier gate

The stock step-1 verifier refuses rebuilt packages that do not bump the
version identity; a V15-derived package identifying as `FM-1_016` was accepted
and ran (Echomatter, 2026-09-04, docs/03 §5). Baud Girl's FM-1+VA (docs/04)
has since installed `FM-1_020` … `FM-1_092` this way, publicly, with rollback
to V15. The gate is a same-version refusal, and content is not authenticated.
Cable-only installation of an open firmware is therefore **demonstrated** for
a package that carries a new version, keeps the stock flash head (the OTA
loader can rewrite it) and keeps the stock loader path. It is still not a
development workflow: a build that does not boot, or that loses its USB descriptor or
update service, cannot be replaced this way. With mask-ROM access the whole
flash can be written directly.
Explaining the gate becomes much easier once a device can be freely
re-flashed and its RAM inspected (`jlrunner.py` can execute code and read
memory in UBOOT mode).

### 3.3 Closed compiler and libraries

- Compiler: Clang/LLVM 4.0.1 fork, proprietary pi32v2 backend, binary only
  (`pkgman.jieliapp.com`). No source, no mainline support, no Rust.
- Libraries: about 110 `.a` files per CPU in the SDK; the hello-world demo alone
  links `cpu.a`, `event.a`, `system.a`, `cfg_tool.a`, `fs.a`, `common_lib.a`,
  `update.a`. Blob-free means rewriting clock/power/cache init, the scheduler,
  DMA/DAC/USB drivers and flash access from register documentation.
- Redistribution: the SDK repository is Apache-2.0 as a whole, which arguably
  covers the `.a` files, but JieLi's intent for the toolchain is unclear
  (download terms, no license text). Do not vendor the toolchain in a public
  repo; script its download.

### 3.4 Bluetooth

BLE-MIDI is a stock feature. Keeping it at L1 is easy (link the vendor stack);
keeping it at L2 is essentially an open BLE controller project on undocumented
radio hardware. An open firmware may have to ship without Bluetooth first.

### 3.5 Legal and ethical boundaries

- Reverse engineering for interoperability and repair is the purpose here.
  Do not redistribute M-VAVE's `app.bin`/`.fwsc`; link to sources. Do not copy
  M-VAVE's UI assets or fonts.
- The msfa code inside the stock firmware is Apache-2.0; no GPL claim is made
  (docs/02 §5).
- Publish recovery procedures with clear warnings; a bricked €70 synth is the
  most likely outcome of careless experimentation.

## 4. Compute and memory budget (for an L1 synth)

| Resource | Stock use | Available |
| --- | --- | --- |
| CPU | 12 msfa voices + FX + UI on one core at 240 MHz | up to 320 MHz and a second core |
| SRAM | ~135 KB static + heap + 23 KB display strips | 578 KB |
| Flash | 583 KB app in a 1 MB map (VM 340 KB, USR 72 KB) | ~400 KB free if the VM region is shrunk; no room for large sample banks |
| Audio | internal DAC, 44.1 kHz, 64-sample blocks (~1.5 ms) | I2S/SPDIF also on chip, unused on this board |
| USB | USB-MIDI + UAC1 24-bit stereo | full-speed/high-speed device and host |

msfa is integer fixed-point and was designed for 2012 Android phones; at
240 MHz on a DSP-flavoured core, 16–24 voices are plausible, and the FPU can
carry effects in float.

## 5. Verdict

| Question | Answer |
| --- | --- |
| Can custom code run on the FM-1? | **Yes, routinely**: first a version-bumped V15 package (Echomatter, AL-255 PR #2, 2026-09-04), then Baud Girl's public FM-1+VA releases `FM-1_020` … `FM-1_092` (2026-09), all through the stock OTA path. The mask-ROM path remains undemonstrated. |
| Can it be sound-compatible with stock? | Yes: same msfa engine, same DX7 patch format. |
| Can it be fully open source? | The application, bootloader and (with work) drivers can be. The compiler and the Bluetooth stack cannot in any foreseeable timeframe without a dedicated compiler/BLE effort. |
| Is it safe to start hacking on the one device we have? | **Not until recovery is proven.** First milestone is a full flash dump and a byte-identical restore. |
| Is porting schwung-movy the way in? | No; reimplement its ideas in C (docs/06). |
| Biggest unknowns | (1) whether `USB_KEY` works on the AC791N through the FM-1's USB-C port, (2) which encoders use the hardware decoders, and the display pinout. The verifier gate is largely explained (docs/03 §5). |

## 6. Recommended strategy

1. Read-only bench session (docs/09), including capturing the stock updater
   traffic and extracting the V15 package from `M-UPGRADE-FM1.app`.
2. Build a `USB_KEY` dongle (any small MCU) and try to reach `UBOOT1.00`
   through the USB-C port. If it works: dump, restore, dump again. If not: map
   the LQFP48 pins and try `UART_KEY`/ISP or the debug TAP via soldered wires.
3. With recovery proven, port the SDK's `demo_hello` to the FM-1 board and
   flash via mask ROM. Add UART logging over the MIDI TRS jack (it is the UART).
4. Bring up display, keys, knobs, DAC; then msfa; then USB-MIDI; then presets.
5. Design the UI and sequencer with Movy's model as the reference (docs/06).
6. Package the open firmware for the stock OTA path (new version number,
   stock head, stock loader), which Baud Girl's releases show works, so users
   install over plain USB-MIDI like a stock update.
7. Replace `uboot.boot` with a build of JieLi's Apache-2.0 `fw-Bootloader`
   (L4); then start peeling `.a` files off (L2) starting with the ones the
   synth does not need.
8. Coordinate with aroum and AL-255 rather than duplicating them; both were
   active in August 2026.
