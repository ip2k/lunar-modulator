# Troubleshooting

Find the symptom, then try the remedies in order.

## The simulator

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| No sound after **Power on** | The browser blocked audio, or the computer's output is muted | Click **Power on** again; check the computer's volume and output device; turn [[MASTER]] up |
| The simulator does not start | The page was opened as a file, not from a web address | Open it from the project's website, or serve it locally (chapter 2) |
| An engine cannot be chosen and the screen says why | The browser runs audio faster than 47,872 Hz, which Macro, Macro Heavy and Six-Op FM refuse | Set the computer's audio output to 44.1 kHz and reload. Shapes, Sophie and Test Sine work at 48 kHz too |
| Sophie is silent | Sophie plays only MIDI notes 36 to 51 | Press [[OCT-]] twice (chapter 5) |
| A note keeps sounding | A key release was lost, for example when the window lost focus | Press <kbd>Esc</kbd>, or send CC 123 from a MIDI keyboard |
| **Connect MIDI input** finds nothing | The browser has no MIDI access, or the keyboard was connected later | Allow MIDI when asked, connect the keyboard, then click the button again |
| Crackles or dropouts | The computer is busy, or a phone is too slow | Close other tabs; on a phone, try a computer |
| [[ENV]], [[SAVE]], [[SEQ]] and others show a message | They are not in the simulator yet | See chapter 3 for which buttons work |

!!! outline "To be written"
    - Screenshots of the refusal message and the global page.
    - Browser-specific notes once Firefox and Safari are tested.

## The desktop tools

!!! outline "To be written"
    - `make -C engines` fails: the compiler needs C++11; on macOS install
      the command-line tools.
    - `fm1-render` refuses an engine at a rate: the Plaits-based engines
      refuse rates above 47,872 Hz.
    - A parameter name is not found: names are as in chapter 5's tables, in
      any case.

## The FM-1

The FM-1 does not run Lunar Modulator, so problems with the instrument
itself are for M-VAVE's manual and support. Chapter 10 describes the
firmware the FM-1 has now.
