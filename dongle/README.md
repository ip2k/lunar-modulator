# USB_KEY dongle (Raspberry Pi Pico)

Hardware, firmware and simulator for putting the FM-1's JieLi AC791N into its
mask-ROM USB download mode through the USB-C port. The specification, wiring,
bill of materials and bench procedure are in
[`docs/10-usb-key-dongle.md`](../docs/10-usb-key-dongle.md). **Status: this
dongle has not yet run against an FM-1.**

**Off the critical path (owner, 2026-10-26).** The `USB_KEY` route itself
works on the owner's unit: on 2026-10-26 FM-1-transporter (kurogedelic, MIT)
on a Raspberry Pi Pico 2 W, with this project's RP2350 patch
(`tools/fm1-transporter/`), keyed it into `UBOOT1.00` with D+ as the clock,
then took two identical dumps and wrote stock V15 back with read-back
[verified: [docs/17](../docs/17-pico2w-recovery.md)]. docs/17 is the
project's approved recovery route for that unit. Its push-pull wiring is an
exception to docs/10 E1/E2 for that route only; E1/E2 (open-drain, series
resistors) still bind this dongle. The dongle stays useful for other owners
and as the open-drain design (docs/07 §4, D2).

Scope: the FM-1 only. The AC79 dev kit needs no `USB_KEY` dongle; it enters
its loader with its onboard UPDATE (K1) and RESET (K2) buttons and has a UART
debug header.

Related work: czietz's MicroPython version for a bare Pico, from issue #2 on
this repository.
- It reaches UBOOT mode on FM-1s, about one power-on in two. czietz and
  masanaohayashi both used it, and masanaohayashi also backed up and wrote
  firmware with it [reported].
- It clocks the key on D+ (our polarity A) and fakes the SOFs with a 1 kHz
  square wave. The FM-1 is then moved by hand to the PC.

docs/10 §1.1 covers:
- what these reports show, and how the tool differs from this design;
- why fixed polarity A (now the default) is the better first attempt;
- the relay-free minimal build (docs/10 §3).

## Layout

| Path | What |
| --- | --- |
| `firmware/usb_key.pio` | PIO programs: open-drain key bit-bang (`usb_key`) and 1 ms pulse train (`sof_pulse`) |
| `firmware/main.c` | control flow: self-test → key → ACK → SOF → hand-over; USB CDC console; LED/button |
| `firmware/config.h` | all pins and timing parameters (shared with the simulator) |
| `firmware/CMakeLists.txt` | pico-sdk 2.x build |
| `sim/jieli_rom.py` | behavioural model of the ROM's key receiver, acknowledge and SOF calibration |
| `sim/dongle.py` | the firmware's control logic in Python, driven by the emulated PIO waveforms |
| `sim/pio_waveform.py` | assembles `usb_key.pio` and runs it in `rp2040-pio-emulator` |
| `sim/cosim.py` | shared open-drain bus, microsecond co-simulation |
| `../tests/test_usb_key_pio.py`, `../tests/test_dongle_model.py` | the test suite |

## Build

CI builds the UF2 on every push (workflow `dongle-firmware`, artifact
`usb_key_dongle-uf2`). Locally:

```bash
git clone --depth 1 --branch 2.1.1 https://github.com/raspberrypi/pico-sdk ~/pico-sdk
git -C ~/pico-sdk submodule update --init lib/tinyusb        # for the USB console
export PICO_SDK_PATH=~/pico-sdk                               # needs arm-none-eabi-gcc + cmake
cmake -S dongle/firmware -B dongle/firmware/build && cmake --build dongle/firmware/build -j
# hold BOOTSEL, plug the Pico in, copy dongle/firmware/build/usb_key_dongle.uf2 to RPI-RP2
```

CI uses Ubuntu 24.04 with this SDK pin. Pico SDK 2.1.1's host `pioasm` has a
[reported GCC 15 compatibility issue](https://github.com/raspberrypi/pico-sdk/issues/2448)
in its fixed-width integer headers; upgrading the host compiler and SDK needs
separate validation.

## Use

1. Wire it as in docs/10 §3 (2.2 kΩ pull-ups from GP16 to D+ and from GP19
   to D−, each on its own pin, 100 Ω series
   resistors, DPDT relay with the PC on the normally-closed contacts).
2. Plug the Pico into the PC; open the serial console (115200). `SELFTEST ok`
   must appear with nothing on the TARGET port yet.
3. Connect the HOST port to a **Linux** PC and the FM-1 (off) to TARGET, then
   switch the FM-1 on. Watch for `ACK polarity=…`, the SOF lines and `DONE`.
4. On the PC: `python3 reference/jl-uboot-tool/jldevfind.py` should list a
   `UBOOT1.00` device. Use read-only commands first. docs/08 Phase 2's gate
   is met (2026-10-26), but any write is still a docs/07 §4 experiment with
   its own image, ranges and recovery plan.

**Polarity:** the default is fixed A, the D+ clock reported working on two
FM-1s (docs/10 §1.1).
- Button held at boot: fixed polarity B (D− clock).
- To try both, build with `DEFAULT_POLARITY_MODE` set to `POLARITY_ALTERNATE`
  in `config.h`.

**Button:** a short press after a result restarts.

**LED:** 1 Hz keying, 3 fast blinks ACK, solid DONE, 5 Hz FAILED, 10 Hz
FAULT.

Without the relay (docs/10 §3, minimal build): when the console says `DONE`,
unplug the FM-1 from the dongle and plug it into the PC, with its power switch
left on and its battery charged.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/test_usb_key_pio.py tests/test_dongle_model.py -v
```
