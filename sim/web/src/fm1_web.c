/* fm1_web.c -- the WebAssembly face of the virtual FM-1: one fm1_app_t and
 * flat functions the AudioWorklet (www/worklet.js) and the Node parity test
 * (test/parity.mjs) call. No Emscripten runtime is used; the module is built
 * standalone and these names are exported as they are.
 *
 * Unit numbers (fm1_app.h, FM1_APP_UNITS): 0 is Sound 1, 1 and 2 the
 * effect slots in order (the master bus), 3..5 sound units 1..3 and 6..13
 * the inserts (fm1w_sound_unit, fm1w_insert_unit give them).
 * C99. MIT licence, like the rest of this repository.
 */
#include "fm1_app.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fm1_app_state.h"
#include "fm1_meta.h"

static fm1_app_t g_app;

/* Multi-sound (fm1_app.h's fm1_app_unit_*): sound units by
 * number 0..3, the user's Sounds 1..4. */
int fm1w_sound_unit(int sound) { return fm1_app_sound_unit(sound); }
int fm1w_insert_unit(int sound, int slot) { return fm1_app_insert_unit(sound, slot); }
int fm1w_unit_current(void) { return fm1_app_unit_current(&g_app); }
int fm1w_unit_set_current(int sound) { return fm1_app_unit_set_current(&g_app, sound); }
float fm1w_unit_level(int sound) { return fm1_app_unit_level(&g_app, sound); }
void fm1w_unit_set_level(int sound, float percent) { fm1_app_unit_set_level(&g_app, sound, percent); }
void fm1w_unit_note_on(int sound, int note, int velocity) {
  fm1_app_unit_note_on(&g_app, sound, note, velocity);
}
void fm1w_unit_note_off(int sound, int note) { fm1_app_unit_note_off(&g_app, sound, note); }
int fm1w_unit_route(int track, int sound) { return fm1_app_unit_route(&g_app, track, sound); }
unsigned fm1w_ram_budget(void) { return FM1_APP_RAM_BUDGET; }

/* The arpeggiator (engine API v3's MIDI effects): a sound's arp on or off,
 * and its parameters by index (the catalogue lists it, kind "midi_fx").
 * fm1w_mfx_select puts another MIDI effect, by its catalogue index, in the
 * sound's MIDI-FX slot; fm1w_arp_* then reach that one. */
int fm1w_mfx_select(int sound, int index) {
  const int k = index - (int)fm1_engine_count;
  if (k < 0 || k >= (int)fm1_midi_fx_count) return -1;
  return fm1_app_mfx_select(&g_app, sound, fm1_midi_fxs[k]->engine.id);
}
int fm1w_arp_on(int sound) { return fm1_app_arp_on(&g_app, sound); }
int fm1w_arp_set_on(int sound, int on) { return fm1_app_arp_set_on(&g_app, sound, on); }
void fm1w_arp_set_param(int sound, int index, float value) {
  fm1_app_arp_set_param(&g_app, sound, index, value);
}
float fm1w_arp_get_param(int sound, int index) { return fm1_app_arp_get_param(&g_app, sound, index); }

/* Text in and out: JavaScript writes a script line, a set or a state file
 * here and passes its length, and reads a saved file back. 256 KiB, the
 * largest file kind's cap (a project, fm1_state_caps.h; a set an 8-track
 * instance exports is 53,208 B at most, docs/15 §2.7); EXPORTED_FUNCTIONS
 * cannot export data, so the address and size come from functions. */
static char g_text[FM1_STATE_CAP_PROJECT];

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

/* FM6's user bank (fm1_app.h, fm1_app_dx7_*): the page's "Load DX7
 * patches" (www/app.js). JavaScript writes a .syx file's bytes into the text
 * buffer, so a file of up to its 64 KiB (FM1_APP_DX7_FILE_MAX), and passes
 * their count; with `play`, the current sound then plays the first voice
 * loaded (fm1_app_dx7_play: it becomes FM6 if it is not). Nothing leaves the
 * module. Returns the voices stored, 0 when the file held none, or -1 for a
 * length past the buffer, -2 without FM6. fm1w_dx7_result's words say what
 * the file held (fm1_dx7_sysex_result_t), for the page's message:
 *   [0] the return value   [1] voices          [2] first slot (0-based)
 *   [3] dumps found        [4] bad checksums   [5] foreign messages
 *   [6] messages cut short [7] dumps of the wrong size
 *   [8] 1 for a raw bank   [9] bytes outside SysEx messages
 *   [10] fm1_app_dx7_play's result (1 when not asked)
 *   [11] the current sound  [12] the length read
 * and fm1w_dx7_name(slot) the name user slot `slot` shows (fm1_app_dx7_name). */
static uint32_t g_dx7_result[13];

int fm1w_dx7_load(unsigned len, int play) {
  fm1_dx7_sysex_result_t r;
  int n, played = 1;
  if (len > sizeof g_text) {
    n = -1;
    memset(&r, 0, sizeof r);
  } else {
    n = fm1_app_dx7_load(&g_app, (const uint8_t *)g_text, len, &r);
    if (n == FM1_APP_DX7_TOO_BIG) n = -1;
    else if (n == FM1_APP_DX7_NO_FM6) n = -2;
    if (n > 0 && play) played = fm1_app_dx7_play(&g_app, r.first_slot);
  }
  g_dx7_result[0] = (uint32_t)n;
  g_dx7_result[1] = r.voices;
  g_dx7_result[2] = r.first_slot;
  g_dx7_result[3] = r.messages;
  g_dx7_result[4] = r.bad_checksums;
  g_dx7_result[5] = r.foreign;
  g_dx7_result[6] = r.truncated;
  g_dx7_result[7] = r.wrong_size;
  g_dx7_result[8] = r.raw;
  g_dx7_result[9] = r.outside;
  g_dx7_result[10] = (uint32_t)played;
  g_dx7_result[11] = (uint32_t)fm1_app_unit_current(&g_app);
  g_dx7_result[12] = len;
  return n;
}

const uint32_t *fm1w_dx7_result(void) { return g_dx7_result; }
const char *fm1w_dx7_name(int slot) { return fm1_app_dx7_name(&g_app, slot < 0 ? 999u : (unsigned)slot); }

/* Modulation (docs/16 MG3). fm1w_mod_reset builds a new, empty runtime
 * with `seed` (fm1_app_mod_reset), and fm1w_mod_text applies the first
 * `len` bytes of the text buffer as one line of fm1-render's --mod format
 * (engines/host/mod_script.h): 1, or 0 for a bad line or no runtime. The
 * parity test plays a scenario's modulation through them; fm1w_init builds
 * the panel's own, from the default rack. */
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

/* The metadata export (fm1_meta.h; stage ED0), as this module writes it:
 * its instance bytes are the 32-bit module's, as its RAM meter counts them,
 * so it is the module, not a desktop build, that writes the page's
 * meta.json (build.sh, test/meta.mjs).
 *
 * fm1w_meta_id: its id, CRC-32 of the export less `made` and `meta_id`. The
 * page's static meta.json carries the same id when it was made from this
 * module, so an editor reads that file only after the two agree. Worked out
 * at the first call (the whole export through a CRC, a few milliseconds: ask
 * from a thread that is not playing, the editor's shadow Worker), then
 * remembered.
 *
 * fm1w_meta_read(offset): bytes offset.. of the export (`made` by
 * "simulator") copied to fm1w_text_buf, as many as fit; returns how many,
 * 0 past the end. Each call writes the whole export again, so a reader
 * takes it a buffer at a time, off the audio thread. Stage A1's fm1w_meta
 * builds on it. */
uint32_t fm1w_meta_id(void) { return fm1_meta_id(); }

typedef struct meta_window {
  uint32_t offset, at, n;       /* the window's start, bytes seen, bytes copied */
} meta_window_t;

static void meta_window_put(void *ctx, const char *bytes, size_t n) {
  meta_window_t *w = (meta_window_t *)ctx;
  for (size_t i = 0; i < n; ++i, ++w->at) {
    if (w->at >= w->offset && w->n < sizeof g_text) g_text[w->n++] = bytes[i];
  }
}

unsigned fm1w_meta_read(unsigned offset) {
  fm1_meta_build_t b;
  meta_window_t w = { offset, 0, 0 };
  fm1_meta_build_default(&b);
  b.by = "simulator";
  fm1_meta_write(&b, meta_window_put, &w);
  return w.n;
}

/* ---- Saved state (stage A1, fm1_app_state.h) ------------------------------------
 * For the page (stage W1) and the editor's shadow Worker (ED13). Kinds are
 * fm1_state.h's codes: 1 project, 2 sound, 3 effects, 4 mod rack, 5 clip,
 * 6 settings, 7 set.
 *
 * fm1w_state_save(kind, arg, binary): the file in the text buffer, its
 *   length returned; -1 refused (fm1w_state_report says why), -2 larger than
 *   the buffer. arg: a sound's unit 0-3; effects -1 the master, 0-3 that
 *   sound's inserts; a clip track * 8 + slot.
 * fm1w_state_check(kind, into, slot, flags, len): pass 1 over the buffer's
 *   first len bytes (JSON, binary or a .movy1 set): 1 when the load would go
 *   ahead, 0 refused; nothing changes. kind 0 takes the file's. into and
 *   slot: a sound's target, an effects chain's (-1 the master), a clip's
 *   track and slot. flags: 1 load without what is unknown or does not fit,
 *   2 replace a clip, 4 no banner on the device screen.
 * fm1w_state_load(...): the same, then pass 2: 1 loaded, 0 refused (nothing
 *   changed). Send binary from a page that parsed JSON elsewhere
 *   (fm1w_state_pack), so the audio thread never reads JSON (ED13).
 * fm1w_state_pack(len): JSON in the buffer to the binary container, in the
 *   buffer; its length, or -1 (the report says why).
 * fm1w_state_report(): the last report as JSON text: code, kind, message
 *   (the page's words), screen (two lines), percent, ram, budget, counts,
 *   where (line, col, path, near) and skips.
 * fm1w_save_gen(): SAVE presses so far; fm1w_store_ready(on) says a store
 *   answers them; fm1w_saved(ok) shows its result on the screen (the reason
 *   for a refusal in the buffer, NUL-terminated). Nothing reaches a device. */
static fm1_app_state_report_t g_state_rep;
static char g_state_json[1536];
static uint32_t g_out_n;
static int g_out_over;

static void out_put(void *ctx, const char *b, size_t n) {
  (void)ctx;
  if (g_out_n + n > sizeof g_text) {
    g_out_over = 1;
    return;
  }
  memcpy(g_text + g_out_n, b, n);
  g_out_n += (uint32_t)n;
}

static void opts_of(fm1_app_load_opts_t *o, int kind, int into, int slot, unsigned flags) {
  fm1_app_load_opts_init(o);
  o->kind = kind > 0 ? (unsigned)kind : 0u;
  o->into = into;
  o->slot = slot;
  o->flags = flags;
}

int fm1w_state_save(int kind, int arg, int binary) {
  memset(&g_state_rep, 0, sizeof g_state_rep);
  g_out_n = 0;
  g_out_over = 0;
  if (!fm1_app_state_save(&g_app, (unsigned)kind, arg, binary, out_put, NULL, &g_state_rep.r)) return -1;
  return g_out_over ? -2 : (int)g_out_n;
}

int fm1w_state_check(int kind, int into, int slot, unsigned flags, unsigned len) {
  fm1_app_load_opts_t o;
  fm1_app_state_mem_t m = { (const uint8_t *)g_text, len };
  if (len > sizeof g_text) return 0;
  opts_of(&o, kind, into, slot, flags);
  return fm1_app_state_check(&g_app, fm1_app_state_mem_read, &m, len, &o, &g_state_rep);
}

int fm1w_state_load(int kind, int into, int slot, unsigned flags, unsigned len) {
  fm1_app_load_opts_t o;
  fm1_app_state_mem_t m = { (const uint8_t *)g_text, len };
  if (len > sizeof g_text) return 0;
  opts_of(&o, kind, into, slot, flags);
  return fm1_app_state_load(&g_app, fm1_app_state_mem_read, &m, len, &o, &g_state_rep);
}

int fm1w_state_pack(unsigned len) {
  /* The file is read whole before a byte of the result is put. */
  fm1_app_state_mem_t m = { (const uint8_t *)g_text, len };
  if (len > sizeof g_text) return -1;
  memset(&g_state_rep, 0, sizeof g_state_rep);
  g_out_n = 0;
  g_out_over = 0;
  if (!fm1_app_state_pack(fm1_app_state_mem_read, &m, out_put, NULL, &g_state_rep.r)) return -1;
  return g_out_over ? -1 : (int)g_out_n;
}

/* A JSON string of s into the report. */
static size_t jstr(char *o, size_t at, size_t cap, const char *s) {
  if (at + 2 >= cap) return at;
  o[at++] = '"';
  for (; *s && at + 8 < cap; ++s) {
    const unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') {
      o[at++] = '\\';
      o[at++] = (char)c;
    } else if (c < 0x20) {
      at += (size_t)snprintf(o + at, cap - at, "\\u%04x", c);
    } else {
      o[at++] = (char)c;
    }
  }
  o[at++] = '"';
  o[at] = '\0';
  return at;
}

const char *fm1w_state_report(void) {
  const fm1_app_state_report_t *r = &g_state_rep;
  char *o = g_state_json;
  const size_t cap = sizeof g_state_json;
  size_t at = 0;
#define KEY(k) (at += (size_t)snprintf(o + at, cap - at, "%s\"" k "\":", at > 1 ? "," : ""))
  at += (size_t)snprintf(o + at, cap - at, "{");
  KEY("code");
  at = jstr(o, at, cap, fm1_state_code_name(r->r.code));
  KEY("kind");
  at = jstr(o, at, cap, fm1_state_kind_name(r->r.kind) ? fm1_state_kind_name(r->r.kind) : "");
  KEY("message");
  at = jstr(o, at, cap, r->message);
  KEY("screen");
  at += (size_t)snprintf(o + at, cap - at, "[");
  at = jstr(o, at, cap, r->screen[0]);
  at += (size_t)snprintf(o + at, cap - at, ",");
  at = jstr(o, at, cap, r->screen[1]);
  at += (size_t)snprintf(o + at, cap - at, "]");
  at += (size_t)snprintf(o + at, cap - at,
                         ",\"percent\":%u,\"ram\":%u,\"budget\":%u,\"sounds\":%u,\"effects\":%u,\"mfx_on\":%u,"
                         "\"modules\":%u,\"cables\":%u,\"voices\":%u,\"tracks\":%u,\"clips\":%u,\"song\":%u,"
                         "\"set\":%u,\"left_out\":%u,\"skipped\":%u,\"repaired\":%u,\"line\":%u,\"col\":%u",
                         r->percent, r->ram, r->budget, r->sounds, r->effects, r->mfx_on, r->modules, r->cables,
                         r->voices, r->tracks, r->clips, r->song, r->set, r->left_out, r->r.skipped,
                         r->r.repaired, r->r.line, r->r.col);
  KEY("path");
  at = jstr(o, at, cap, r->r.path);
  KEY("near");
  at = jstr(o, at, cap, r->r.near);
  KEY("name");
  at = jstr(o, at, cap, r->r.name);
  KEY("what");
  at = jstr(o, at, cap, r->r.what);
  KEY("first_skip");
  at = jstr(o, at, cap, r->r.first_skip);
  if (at + 2 < cap) {
    o[at++] = '}';
    o[at] = '\0';
  }
#undef KEY
  return g_state_json;
}

unsigned fm1w_save_gen(void) { return g_app.save_gen; }
void fm1w_store_ready(int on) { g_app.store_ready = on != 0; }
void fm1w_saved(int ok) {
  g_text[sizeof g_text - 1] = '\0';
  fm1_app_saved(&g_app, ok, ok ? NULL : g_text);
}
