# USB_KEY dongle (Raspberry Pi Pico)

Hardware, firmware and simulator for putting the FM-1's JieLi AC791N into its
mask-ROM USB download mode through the USB-C port. The specification, wiring,
bill of materials and bench procedure are in
[`docs/10-usb-key-dongle.md`](../docs/10-usb-key-dongle.md). **Status: not yet
run against an FM-1.**

Related work: czietz's MicroPython version for a bare Pico, from issue #2 on
this repository.
- It reaches UBOOT mode on FM-1s, about one power-on in two. czietz and
  masanaohayashi both used it, and masanaohayashi also backed up and wrote
  firmware with it [reported].
- It clocks the key on D+ (our polarity A) and fakes the SOFs with a 1 kHz
  square wave. The FM-1 is then moved by hand to the PC.

docs/10 §1.1 covers:
- what these reports show, and how the tool differs from this design;
- why fixed polarity A is the better first attempt;
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

## Use

1. Wire it as in docs/10 §3 (2.2 kΩ pull-ups from GP16 to D+ and from GP19
   to D−, each on its own pin, 100 Ω series
   resistors, DPDT relay with the PC on the normally-closed contacts).
2. Plug the Pico into the PC; open the serial console (115200). `SELFTEST ok`
   must appear with nothing on the TARGET port yet.
3. Connect the HOST port to a **Linux** PC and the FM-1 (off) to TARGET, then
   switch the FM-1 on. Watch for `ACK polarity=…`, the SOF lines and `DONE`.
4. On the PC: `python3 reference/jl-uboot-tool/jldevfind.py` should list a
   `UBOOT1.00` device. Read-only commands only until docs/08 Phase 2 exits.

Button: held at boot = fixed polarity B (D− clock); short press after a
result = restart. Fixed polarity A (D+ clock, the likely one) needs
`DEFAULT_POLARITY_MODE` set to `POLARITY_DP_CLOCK` in `config.h`. LED: 1 Hz
keying, 3 fast blinks ACK, solid DONE, 5 Hz FAILED, 10 Hz FAULT.

Without the relay (docs/10 §3, minimal build): when the console says `DONE`,
unplug the FM-1 from the dongle and plug it into the PC, with its power switch
left on and its battery charged.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/test_usb_key_pio.py tests/test_dongle_model.py -v
```
