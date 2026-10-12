/* Project MIDI-learn preferences. C99, MIT. No audio routing semantics. */
#ifndef FM1_STATE_MIDI_H_
#define FM1_STATE_MIDI_H_
#include <stdint.h>
#define FM1_MIDI_MAP_BINDINGS 64u
#define FM1_MIDI_MAP_TARGET 192u
#define FM1_MIDI_MAP_SOURCE 128u
#define FM1_MIDI_MAP_TEXT 4096u
#define FM1_MIDI_MAP_VERSION 1u
#define FM1_MIDI_MAP_NOTE 0u
#define FM1_MIDI_MAP_CC 1u
typedef struct fm1_midi_binding {
  uint16_t target, source; /* offsets into the shared interned text pool */
  uint8_t channel, kind, number, reserved;
} fm1_midi_binding_t;
typedef struct fm1_midi_map {
  uint8_t version, count; /* version zero: no mapping member in the project */
  uint16_t used;
  fm1_midi_binding_t binding[FM1_MIDI_MAP_BINDINGS];
  char text[FM1_MIDI_MAP_TEXT];
} fm1_midi_map_t;
/* Return FM1_STATE_OK, BAD or TOO_BIG. Repeated strings share pool bytes. */
#ifdef __cplusplus
extern "C" {
#endif
unsigned fm1_midi_map_add(fm1_midi_map_t *map, const char *target, const char *source,
                         unsigned channel, unsigned kind, unsigned number);
#ifdef __cplusplus
}
#endif
#endif
