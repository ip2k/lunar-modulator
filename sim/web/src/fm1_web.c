/* fm1_web.c -- the WebAssembly face of the virtual FM-1: one fm1_app_t and
 * flat functions the AudioWorklet (www/worklet.js) and the Node parity test
 * (test/parity.mjs) call. No Emscripten runtime is used; the module is built
 * standalone and these names are exported as they are.
 *
 * Unit numbers: 0 is the sound, 1 and 2 the effect slots in order.
 * C99. MIT licence, like the rest of this repository.
 */
#include "fm1_app.h"

#include <stdint.h>

static fm1_app_t g_app;

/* Text in: JavaScript writes a script line (later, a whole `movy1` set)
 * here and passes its length. 64 KiB holds the largest set an 8-track
 * instance exports, 53,208 B with every pool full and 256-step clips
 * (docs/15 §2.7); EXPORTED_FUNCTIONS cannot export data, so the address and
 * size come from functions. */
static char g_text[65536];

void fm1w_init(float sample_rate) { fm1_app_init(&g_app, sample_rate); }
int fm1w_default_chain(void) { return fm1_app_default_chain(&g_app); }

const char *fm1w_catalog(void) { return fm1_app_catalog_json(); }
int fm1w_select(int unit, int index) { return fm1_app_select(&g_app, unit, index); }
int fm1w_unit_index(int unit) {
  return unit >= 0 && unit < FM1_APP_UNITS ? g_app.unit[unit].index : -1;
}
void fm1w_set_param(int unit, int index, float value) {
  fm1_app_set_param(&g_app, unit, index, value);
}
float fm1w_get_param(int unit, int index) { return fm1_app_get_param(&g_app, unit, index); }
unsigned fm1w_ram(void) { return (unsigned)fm1_app_ram(&g_app); }
unsigned fm1w_unit_bytes(int unit) {
  return unit >= 0 && unit < FM1_APP_UNITS ? (unsigned)g_app.unit[unit].bytes : 0u;
}

void fm1w_note_on(int note, int velocity) { fm1_app_note_on(&g_app, note, velocity); }
void fm1w_note_off(int note) { fm1_app_note_off(&g_app, note); }
void fm1w_pitch_bend(float semitones) { fm1_app_pitch_bend(&g_app, semitones); }
void fm1w_all_notes_off(void) { fm1_app_all_notes_off(&g_app); }

void fm1w_key(int key, int down, int velocity) { fm1_app_key(&g_app, key, down, velocity); }
void fm1w_button(int button, int down) { fm1_app_button(&g_app, button, down); }
void fm1w_encoder(int encoder, int delta) { fm1_app_encoder(&g_app, encoder, delta); }
void fm1w_master(float position, int show) { fm1_app_master(&g_app, position, show); }

/* Render into the app's buffer and return its address (stereo interleaved
 * float, `frames` <= 64). */
const float *fm1w_render(unsigned frames) { return fm1_app_render(&g_app, frames); }

/* Screen: redraw when needed; the buffer is 240 x 240 RGB565. */
int fm1w_draw(unsigned min_frames) { return fm1_app_draw(&g_app, min_frames); }
const uint16_t *fm1w_screen(void) { return g_app.tft.px; }

/* LEDs: 27 keys, then the 14 buttons; fm1w_leds_changed() reads and clears. */
const uint8_t *fm1w_leds(void) { return g_app.led; }
int fm1w_leds_changed(void) {
  int c = g_app.leds_changed;
  g_app.leds_changed = 0;
  return c;
}
int fm1w_mode(void) { return g_app.mode; }

char *fm1w_text_buf(void) { return g_text; }
unsigned fm1w_text_cap(void) { return (unsigned)sizeof g_text; }

/* The sequencer. fm1w_seq_text applies the first `len` bytes of the text
 * buffer as one script line at the coming block's start and returns the
 * bytes it took (fm1_app_seq_line): fewer than `len` means the rest must
 * wait for the next render. -1 for a length past the buffer. */
int fm1w_seq_text(unsigned len) {
  if (len > sizeof g_text) return -1;
  return (int)fm1_app_seq_line(&g_app, g_text, len);
}

/* A new instance of `tracks` tracks (1..8), then the default route, as
 * fm1-render routes by default: track 0 plays the sound when one is loaded.
 * 0, or -1 for a bad count. */
int fm1w_seq_reset(int tracks) {
  int r = fm1_app_seq_reset(&g_app, tracks);
  if (r == 0) fm1_app_seq_default_route(&g_app);
  return r;
}

/* Events dropped since init (0 unless a note may have hung). */
unsigned fm1w_seq_dropped(void) { return (unsigned)fm1_app_seq_dropped(&g_app); }

/* The lab switch (fm1_app_set_lab): the page turns it on for an address
 * with ?lab or #lab, before fm1w_default_chain, which then loads the demo
 * pattern. Off, the sequencer stays off the panel. */
void fm1w_set_lab(int on) { fm1_app_set_lab(&g_app, on); }

/* Modulation (docs/16 MG3). fm1w_mod_reset builds a new, empty runtime
 * with `seed` (fm1_app_mod_reset), and fm1w_mod_text applies the first
 * `len` bytes of the text buffer as one line of fm1-render's --mod format
 * (engines/host/mod_script.h): 1, or 0 for a bad line or no runtime. The
 * parity test plays a scenario's modulation through them; the lab switch
 * builds the panel's own. */
void fm1w_mod_reset(unsigned seed) { fm1_app_mod_reset(&g_app, seed); }

int fm1w_mod_text(unsigned len) {
  char line[1024];
  if (len >= sizeof line) return 0;
  for (unsigned i = 0; i < len; ++i) line[i] = g_text[i];
  line[len] = '\0';
  return fm1_app_mod_line(&g_app, line, NULL, 0);
}

/* A snapshot of the transport for the page's status line, refreshed by each
 * call: eight 32-bit words, [0] playing, [1] tempo in hundredths of a BPM,
 * [2] recording, [3] the watched track, [4] counting in, [5] following an
 * external clock, [6] and [7] the master tick's low and high halves. */
static uint32_t g_seq_info[8];

const uint32_t *fm1w_seq_info(void) {
  fm1_seq_info_t i;
  const fm1_seq_t *s = fm1_app_seq(&g_app);
  if (!s) {
    for (int k = 0; k < 8; ++k) g_seq_info[k] = 0;
    return g_seq_info;
  }
  fm1_seq_get_info(s, &i);
  g_seq_info[0] = i.playing;
  g_seq_info[1] = i.bpm_x100;
  g_seq_info[2] = i.recording;
  g_seq_info[3] = i.watch_track;
  g_seq_info[4] = i.counting_in;
  g_seq_info[5] = i.following;
  g_seq_info[6] = (uint32_t)i.master_tick;
  g_seq_info[7] = (uint32_t)(i.master_tick >> 32);
  return g_seq_info;
}
