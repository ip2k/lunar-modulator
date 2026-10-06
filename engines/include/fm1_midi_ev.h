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
  uint16_t b;                  /* a note's velocity in the low byte (NOTE_ON: 1..127;
                                  0 is a note-off) and where it came from in the
                                  high byte (FM1_MIDI_SRC_*); the pedal (SUSTAIN:
                                  0 up, 1 down) */
} fm1_midi_ev_t;

/* Where a note came from: b's high byte on NOTE_ON and NOTE_OFF. A host
 * marks the sequencer's notes, so an effect that holds notes can tell them
 * from the ones played (the arp's latch, and what Stop lets go: STOP
 * below); an effect marks what it sends after the notes that caused it.
 * Live notes are 0, so b is the bare velocity, as before the mark. */
enum {
  FM1_MIDI_SRC_LIVE = 0,       /* the keys, MIDI IN, fm1-render's --note */
  FM1_MIDI_SRC_SEQ = 1         /* a sequencer track */
};
#define FM1_MIDI_EV_VEL(b) ((unsigned)(b) & 0xFFu)
#define FM1_MIDI_EV_SRC(b) ((unsigned)(b) >> 8)
#define FM1_MIDI_EV_B(vel, src) ((uint16_t)(((unsigned)(src) << 8) | ((unsigned)(vel) & 0xFFu)))

enum {
  FM1_MIDI_EV_NOTE_ON = 1,     /* in, out */
  FM1_MIDI_EV_NOTE_OFF = 2,    /* in, out */
  FM1_MIDI_EV_SUSTAIN = 3,     /* in: the hold pedal, CC 64 */
  FM1_MIDI_EV_STEP = 4,        /* in: one step from a sequencer (an arp's RATE TRG) */
  FM1_MIDI_EV_RESET = 5,       /* in: restart the pattern; the next tick is its first */
  FM1_MIDI_EV_FLUSH = 6,       /* in: a note-off for every note sounding; keys stay */
  FM1_MIDI_EV_PANIC = 7,       /* in: FLUSH, and forget every key */
  /* 8 is the arpeggiator core's own PARAM (fm1_arp.h) */
  FM1_MIDI_EV_STOP = 9         /* in: the sequencer stopped: forget the keys it gave
                                  (held or latched) and end the notes they started;
                                  the rest play on. An effect that keeps no origin
                                  takes it as FLUSH */
};

#ifdef __cplusplus
}
#endif

#endif /* FM1_MIDI_EV_H_ */
