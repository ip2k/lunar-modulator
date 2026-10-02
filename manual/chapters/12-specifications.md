# Specifications

## The instrument

These are the FM-1's own specifications as far as Lunar Modulator is
concerned. The *source* column says where each figure comes from: measured on
a unit by this project, M-VAVE's documentation, or published analysis by
others who have studied the FM-1.

| Item | Specification | Source |
| --- | --- | --- |
| Processor | JieLi AC791N, a 32-bit pi32v2 core running at 240 MHz (320 MHz maximum) | Measured (chip and firmware strings); clock from others' analysis |
| Memory | 578 KB of RAM on the chip, of which about 514 KB is usable; 1 MB of flash | RAM from the chip maker's documentation; flash size from others' analysis |
| Display | 1.54-inch colour screen, 240 × 240 pixels | Others' analysis and M-VAVE's documentation |
| Keys | 27 keys, F3 to G5, each with a light | Measured |
| Controls | 7 encoders, 1 potentiometer ([[MASTER]]), 14 buttons with lights | Measured; names from M-VAVE's documentation |
| Connectors | USB-C; 3.5 mm stereo audio output; 3.5 mm MIDI input | Measured |
| USB | USB 2.0 full speed, MIDI and audio | Measured, with M-VAVE's firmware |
| Wireless | Bluetooth LE, used by M-VAVE's firmware for MIDI | Others' analysis |
| Battery | Lithium polymer, 3.7 V, 2000 mAh | Measured (cell label) |
| Size | 161.5 × 96.5 mm | M-VAVE's documentation |

## Lunar Modulator

{{status sim desktop}}

| Item | Specification |
| --- | --- |
| Audio | 44,118 Hz, 64-sample blocks (1.45 ms), stereo |
| Engines' own rates | The Plaits-based engines run at 47,872 Hz and Shapes at 96 kHz, each converted to the output rate, so they sound and time as on the modules they come from |
| Sound engines | One at a time; chapter 5 lists them and their voices |
| Effects | Two slots in series, then the limiter (chapter 6) |
| Limiter | Ceiling 0.98 of full scale (−0.18 dBFS), instant attack, about 100 ms release |
| Memory for sounds | About 379 KB on the FM-1 for the engine and both effects, the room M-VAVE's firmware leaves free; the global page shows what a combination takes |
| Sequencer | Chapter 7 |
| Licence | MIT for Lunar Modulator's own code; third-party code under its own licence (chapter 13) |

!!! outline "To be written"
    - Measured CPU load per engine on the FM-1's processor, from the JieLi
      development board (stage B), replacing the desktop estimates.
    - The FM-1 build's voice limits per engine, once memory and CPU are
      measured on the device.
    - Power: battery life with Lunar Modulator, once it runs on the device.
