# Arduino MIDI Library

Unmodified sources from https://github.com/FortySevenEffects/arduino_midi_library
at `2d64cc3c2ff85bbee654a7054e36c59694d8d8e4`, MIT. Credit Francois Best and
contributors; retain LICENSE and source notices. inventory.json pins source files.

Lunar uses a custom one-byte receive-only transport and explicit initialization,
without Arduino, allocation, interrupts or a hardware driver. The adapter remains
separate. This import is parser groundwork; it does not enable the FM1 MIDI jack.
