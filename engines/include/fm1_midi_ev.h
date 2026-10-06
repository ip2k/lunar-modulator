/* fm1_midi_ev.h -- the note event a MIDI effect takes and gives (engine API
 * v3, FM1_KIND_MIDI_FX in fm1_engine.h). Its own header, so the
 * arpeggiator core (engines/midi_fx/fm1_arp.h) shares the type without the
 * rest of the engine API. Plain C99. MIT licence, like the rest of this
 * repository.
 */
#ifndef FM1_MIDI_EV_H_
#define FM1_MIDI_EV_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_midi_ev {
  uint16_t frame;              /* offset in the host's block */
  uint8_t kind;                /* FM1_MIDI_EV_* */
  uint8_t a;                   /* the key */
  uint16_t b;                  /* the velocity (NOTE_ON: 1..127; 0 is a note-off),
                                  or the pedal (SUSTAIN: 0 up, 1 down) */
} fm1_midi_ev_t;

enum {
  FM1_MIDI_EV_NOTE_ON = 1,     /* in, out */
  FM1_MIDI_EV_NOTE_OFF = 2,    /* in, out */
  FM1_MIDI_EV_SUSTAIN = 3,     /* in: the hold pedal, CC 64 */
  FM1_MIDI_EV_STEP = 4,        /* in: one step from a sequencer (an arp's RATE TRG) */
  FM1_MIDI_EV_RESET = 5,       /* in: restart the pattern; the next tick is its first */
  FM1_MIDI_EV_FLUSH = 6,       /* in: a note-off for every note sounding; keys stay */
  FM1_MIDI_EV_PANIC = 7        /* in: FLUSH, and forget every key */
};

#ifdef __cplusplus
}
#endif

#endif /* FM1_MIDI_EV_H_ */
