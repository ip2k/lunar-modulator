/* seq_script.h -- desktop helpers shared by fm1-seq and fm1-render: the
 * timed verb-script reader and the JSON Lines event log (engines/seq.md).
 *
 * Verb script: UTF-8 text, one command per line, "@<absolute_frame> <ops>",
 * where <ops> are Movy `cmd` ops exactly as Movy's command.rs parses them
 * (several may share a line, separated by ';'). Blank lines and lines
 * starting with '#' are ignored, except a header "#! rate=<Hz> block=<frames>
 * tracks=<n> [end=<frames>]" (defaults 44118, 128, 8; `end` is this
 * repository's extension: the run length). A command applies at the start of
 * the first block whose start frame is >= its frame, before that block runs.
 * Test directive (a comment to every other reader): "#?@<frame> <label>"
 * asks fm1-seq for a state dump at that point among the commands.
 *
 * One line is not Movy's: "@<frame> rt <F8|FA|FB|FC>" is MIDI realtime input
 * (clock, start, continue, stop), delivered like a command: before the first
 * block starting at or after <frame>, through fm1_seq_realtime_in at frame 0
 * of that block. The Movy oracle hands it to Engine::on_external_realtime,
 * which is where movy-dsp's on_midi delivers Move's transport.
 *
 * Event log: one JSON object per event, in emission order:
 *   {"block":B,"frame":F,"tick":T,"kind":K,"track":t|null,"a":A|null,"b":B|null}
 * with kind on|off|cc|clock|start|stop|click; a lock is "cc" with
 * a = 102 + lane (Movy's mapping) in both modes.
 *
 * Host code (it allocates); the sequencer core itself never does. MIT.
 */
#ifndef FM1_SEQ_SCRIPT_H_
#define FM1_SEQ_SCRIPT_H_

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "fm1_seq.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  uint64_t frame;
  const char *ops;        /* NUL-terminated, inside the script's text */
  size_t line;
  int snap;               /* a "#?@<frame> <label>" test directive: ops is the label */
} fm1_script_cmd_t;

typedef struct {
  uint32_t rate, block;
  uint8_t tracks;
  uint64_t end;
  int has_rate, has_block, has_tracks, has_end;
  fm1_script_cmd_t *cmds;  /* stably sorted by frame */
  size_t n;
  char *text;
} fm1_script_t;

/* Reads a script. Returns 0 and fills err on a malformed line. */
int fm1_script_load(const char *path, fm1_script_t *out, char *err, size_t errlen);
void fm1_script_free(fm1_script_t *s);

/* Reads a whole file into a NUL-terminated buffer (free() it). */
char *fm1_read_file(const char *path, size_t *len);

/* Applies one script line's ops (fm1_seq_apply_text) or its realtime input
 * ("rt FA"), writing the events to out. Returns how many. */
uint32_t fm1_script_apply(fm1_seq_t *s, const char *ops, fm1_seq_ev_t *out, uint32_t cap);

/* One event-log line. `block_start` is the absolute frame of the block. */
void fm1_script_log_event(FILE *f, uint64_t block, uint64_t block_start, const fm1_seq_ev_t *e);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_SCRIPT_H_ */
