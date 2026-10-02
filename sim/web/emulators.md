# Emulating the FM-1: what exists, and what each route would take

Survey for the owner's question (docs/13 §10, answer 4): "If there's an
emulator for the FM-1 or we can make one with a virtual screen output that
runs in a browser, that might be awesome." Checked 2026-10-01 against the
local clones under `reference/` and the web.

**Short answer.** There is no public emulator of the FM-1, of the AC791N, or
of the pi32v2 CPU. Baud Girl has a private one. JieLi has (or had) an
internal QEMU target for pi32v2 that was never published. What can be built
in days, and now has been, is a *virtual FM-1 for our own firmware*: its
portable layers compiled to WebAssembly behind a drawn panel
([README.md](README.md)). A full-system emulator that boots stock firmware
in a browser is a project of months.

## 1. What exists

| What | Status | Use to us | Confidence |
| --- | --- | --- | --- |
| **Baud Girl's FM-1 emulator** | Private. The FM-1+VA install page says a beta "passed its tests on an emulator of the FM-1"; the installer's code comments name `tools/emu/…` (notes/2026-09-29 §1). FM-1+VA is a binary patch of V15, so it must execute pi32v2 code with enough peripherals to run the stock image | The most relevant prior art by far. Asking for it is the owner's call (notes/2026-09-29, "Contact") | [reported] install page, 2026-10-01; code comments |
| **Public FM-1 emulators** | None. Searches find Web MIDI editors and librarians (Benny Sparra's FM1 Editor, DXcompanion), which send patches to a real unit | None | [reported] web search 2026-10-01 |
| **AL-255's "simulator"** (FM-1-RE, branch `with-custom-firmware`, `firmware/host/sim_main.cpp`) | A *host build*, not an emulator: their demo firmware's portable C++ (`demo_render`, `demo_midi_note`, the basic synth) compiled for the desktop with stub runtime functions, writing a WAV. The same branch builds the synth as ALSA, JACK, LV2 and VST hosts and renders their pi32v2 Dexed port natively | The same idea as our `fm1-render` and this virtual FM-1; nothing to reuse | [verified] local clone at `628fcaf`; `main` no longer carries `firmware/` |
| **kagaimiq's tools** (jielie, jl-uboot-tool, jl-misctools) | Documentation (chip families, pi32v2 registers and opcode tables in `cpu/pi32v2.md`, BR25 mask ROM and interrupts), a USB loader dumper/flasher, and package unpackers. No emulator. ("Emulation" in jielie is the CPU's debug mode, `rete`/`EMUEXCPT`) | The ISA tables an interpreter would start from | [verified] local clones |
| **ghidra-jieli** (SLEIGH) | kagaimiq's original: pi32v2 "very early stage", last push 2024-02, mis-splits the `80 ff` long-call prefix (FM-1-RE docs/04, 0.23 % of instructions differ from the vendor objdump). Forks: quarkslab (one commit, 2026-03, "most instructions"), **edco** (2026-09-16: claims "mature" pi32v2 coverage and an `ac7911b8` (WL82) variant with the memory map, 73 interrupt vectors and 627 peripheral registers) | Ghidra can run any SLEIGH-described CPU in its p-code emulator, so a correct module is an instruction-level emulator for free: slow, desktop-only, peripherals by hand. Good for running single stock routines | original and AL-255's measurement [reported]; edco's claims [reported], not checked here |
| **QEMU** | No pi32 or pi32v2 target upstream. JieLi's toolchain team built one: a public gist of their build notes (2018–2021, paths under `/home/jieli/toolchains`) configures `qemu --target-list=pi32v2-softmmu`. Its source has not been published, and the public Linux toolchain ships no QEMU | Evidence that JieLi emulates its own CPU; ask JieLi only if a commercial relationship ever exists | gist [verified] read 2026-10-01; toolchain contents [reported] FM-1-RE docs/04 |
| **Unicorn** | ARM, AArch64, M68K, MIPS, PowerPC, RISC-V, SPARC, S390x, TriCore, x86. Nothing JieLi | None | [reported] Unicorn README |

## 2. Route A: a full-system emulator running stock (or FM-1+VA) firmware

What it would have to model [inferred unless marked]:

- **The CPU.** pi32v2: 16 registers usable as 64-bit pairs, 16-, 32- and
  48-bit instructions, parallel issue (`a # b`), hardware loops (`rep`),
  delayed branches (`j.f`, `call.f`), saturating, SIMD and MAC instructions
  and an FPU. Sources: jielie's opcode tables, the SLEIGH modules, and JieLi's
  `objdump` as the decoding oracle (CLAUDE.md trap 4). Thousands of lines and
  a test corpus of decoded instructions.
- **Speed.** The stock app clocks its one core at 240 MHz of a possible
  320 (docs/01 §1, §5); nothing has measured how much of that it uses. An
  emulator that keeps up in the worst case must therefore run up to 240
  million guest cycles a second, fewer if it skips the idle loop, which a
  worst-case estimate cannot count on. An interpreter in WebAssembly manages
  perhaps 50–300 million guest instructions a second on a fast desktop, so
  dependable real time needs a dynamic recompiler to WebAssembly.
  Non-real-time (render to a buffer, then play) is easier.
- **Peripherals**, from WL82.h (AC79 SDK, Apache-2.0) and AL-255's notes:
  clocks and PLL, timers, the interrupt controller, the flash controller and
  XIP cache (SPI0, `0x11C00`; SFC `0x40200`), the TFT on SPI1 (`0x11D00`; an
  ST7789 command decoder drawing to a canvas), DMA, the audio DAC's DMA ring,
  SARADC, the GPIO key matrix and the two 74HC595 LED registers, UART MIDI,
  the USB device (USB-MIDI could bridge to Web MIDI), Bluetooth (stub), the
  idle second core. [reported: docs/01 §2–4]
- **Boot.** The mask ROM has not been dumped, so boot is high-level: load
  `uboot.boot`'s state, map `app.bin` at `0x02000000` and jump.
- **The firmware.** M-VAVE's `.fwsc`, unpacked. It cannot be redistributed,
  so a published page could only run images the user supplies.

What it buys: trying patched images (as Baud Girl does, and as a hook build
on stock V15 would, docs/11 §6) before anything touches the unit, and seeing
stock's own UI. **Effort: months.** Worth it only if Baud Girl shares theirs,
or if patching stock firmware becomes the plan.

**Cheaper variant: Ghidra's p-code emulator** with a good SLEIGH module
(edco's fork, once its decoding is checked against `objdump`). Days to set
up, desktop only, far from real time: useful to run individual stock
functions with chosen inputs, not to play.

## 3. Route B: a virtual FM-1 for our own firmware (built)

The open firmware is being written portable: engines behind a C API
(engines/), a sequencer core in C (docs/13), and a UI that draws a 240 × 240
RGB565 frame buffer. Compiling those layers to WebAssembly and putting a
panel around them gives a virtual FM-1 that runs in real time in any modern
browser. The hardware boundary is small: notes and panel events in, stereo
blocks, a frame buffer and LED states out. See [README.md](README.md).

What it shows: the sound of every engine and effect, exactly (byte for byte
against the native renderer, section "Parity" in the README), the screen as
the firmware draws it, the panel logic, the RAM a chain takes with 32-bit
pointers. What it cannot show: pi32v2 timing and CPU load, FPU edge cases
(denormals, divide-by-zero traps), the drivers (SPI, DMA, ADC, USB), or
anything about stock firmware.

## 4. Route C, in between: a pi32v2 instruction-set simulator for our code

An interpreter for the CPU alone, no peripherals, running our engines as
JieLi's clang compiles them, would count instructions per 64-frame block
before the AC79 dev board arrives (stage B), and would catch code generation
problems. Weeks of work [inferred], and stage B's dev board answers the same
question with real cycles. Not recommended unless the board is delayed.
