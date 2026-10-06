/* state_json_read.c -- the JSON reader: the tokenizer's events (fm1_json.h)
 * to records (fm1_state.h), streaming, under the context-first rules R1-R4
 * (fm1_state.h; notes/2026-10-06-state-files.md §7.2-§7.3, §16).
 *
 * A context stack mirrors the JSON's containers: what each one is (the
 * document, a sound, a pad, a cable...), its unit, and the members it has
 * seen, so a duplicate key, a member out of context order or a value of the
 * wrong type is refused with its path, and an unknown member is skipped and
 * counted. Records go out as soon as they are known: a parameter as its
 * value is read, a cable or a voice at the end of its object. Text, movy1
 * lines and pattern data go out in pieces, so nothing here holds a whole
 * string. C99, no heap, no recursion, no stdio. MIT licence. */
#include "fm1_state.h"
#include "fm1_num.h"

#include <string.h>

/* ---- Contexts and members --------------------------------------------------- */
enum {
  C_NONE = 0, C_DOC, C_MADE, C_SESSION, C_KEYOBJ, C_SOUNDS, C_UNIT, C_PARAMS, C_PADS, C_PAD,
  C_INSERTS, C_MFXS, C_MASTER, C_CHAIN, C_DX7S, C_DX7, C_OPS, C_OP, C_GLOBALS, C_MOD, C_RACK,
  C_MODULE, C_MPARAMS, C_MDATA, C_CABLES, C_CABLE, C_REF, C_TARGET, C_LINES, C_VIEW, C_SETTINGS
};

enum {
  M_NONE = 0,
  M_SCHEMA, M_LUNAR, M_KIND, M_MADE, M_NAME, M_TITLE, M_ABOUT, M_AUTHOR, M_LICENCE, M_SESSION,
  M_SOUNDS, M_SOUND, M_MASTER, M_CHAIN, M_DX7, M_MOD, M_SET, M_CLIP, M_SETTINGS, M_VIEW,
  M_BY, M_VERSION, M_COMMIT,
  M_CURRENT, M_OCTAVE, M_TRANSPOSE, M_KEY, M_ROOT, M_SCALE,
  M_ENGINE, M_ON, M_PARAMS, M_PADS, M_LEVEL, M_INSERTS, M_MIDI_FX,
  M_SLOT, M_VNAME, M_OPS, M_GLOBALS,
  M_SEED, M_RACK, M_CABLES, M_POS, M_MKIND, M_DATA, M_DVERSION, M_HEX,
  M_FROM, M_VIA, M_TO, M_AMOUNT, M_OFFSET, M_POLARITY, M_CURVE, M_VOICE, M_LOCK,
  M_SOURCE, M_MODULE, M_PORT, M_UNIT, M_PARAM, M_GATE,
  M_MODE, M_VSOUND, M_PAGE, M_VUNIT, M_TRACK, M_BAR, M_PANEL, M_VPOS, M_VSLOT, M_ENTRY,
  M_METRONOME, M_COUNT_IN_CLICK, M_FULL_VELOCITY, M_MIDI_IN_CHANNEL,
  M_UNKNOWN,
  M_PNAME,          /* a resolved parameter key (C_PARAMS, C_PAD, C_MPARAMS) */
  M_COUNT
};

static const char *const kMember[M_COUNT] = {
  "",
  "$schema", "lunar", "kind", "made", "name", "title", "about", "author", "licence", "session",
  "sounds", "sound", "master", "chain", "dx7", "mod", "set", "clip", "settings", "view",
  "by", "version", "commit",
  "current", "octave", "transpose", "key", "root", "scale",
  "engine", "on", "params", "pads", "level", "inserts", "midi_fx",
  "slot", "name", "ops", "globals",
  "seed", "rack", "cables", "pos", "kind", "data", "version", "hex",
  "from", "via", "to", "amount", "offset", "polarity", "curve", "voice", "lock",
  "source", "module", "port", "unit", "param", "gate",
  "mode", "sound", "page", "unit", "track", "bar", "panel", "pos", "slot", "entry",
  "metronome", "count_in_click", "full_velocity", "midi_in_channel",
  "?", "?"
};

/* The members of each object context, in canonical order (the schemas'). */
static const uint8_t kDoc[] = { M_SCHEMA, M_LUNAR, M_KIND, M_MADE, M_NAME, M_TITLE, M_ABOUT,
  M_AUTHOR, M_LICENCE, M_SESSION, M_SOUNDS, M_SOUND, M_MASTER, M_CHAIN, M_DX7, M_MOD, M_SET,
  M_CLIP, M_SETTINGS, M_VIEW, 0 };
static const uint8_t kMade[] = { M_BY, M_VERSION, M_COMMIT, 0 };
static const uint8_t kSession[] = { M_CURRENT, M_OCTAVE, M_TRANSPOSE, M_KEY, 0 };
static const uint8_t kKey[] = { M_ROOT, M_SCALE, 0 };
static const uint8_t kUnit[] = { M_ENGINE, M_ON, M_PARAMS, M_PADS, M_LEVEL, M_INSERTS, M_MIDI_FX, 0 };
static const uint8_t kDx7[] = { M_SLOT, M_VNAME, M_OPS, M_GLOBALS, 0 };
static const uint8_t kMod[] = { M_SEED, M_RACK, M_CABLES, 0 };
static const uint8_t kModule[] = { M_POS, M_MKIND, M_PARAMS, M_DATA, 0 };
static const uint8_t kData[] = { M_DVERSION, M_HEX, 0 };
static const uint8_t kCable[] = { M_SLOT, M_ON, M_FROM, M_VIA, M_TO, M_AMOUNT, M_OFFSET,
  M_POLARITY, M_CURVE, M_VOICE, M_LOCK, 0 };
static const uint8_t kRef[] = { M_SOURCE, M_MODULE, M_PORT, 0 };
static const uint8_t kTarget[] = { M_UNIT, M_MODULE, M_PARAM, M_GATE, 0 };
static const uint8_t kView[] = { M_MODE, M_VSOUND, M_PAGE, M_VUNIT, M_TRACK, M_BAR, M_PANEL,
  M_VPOS, M_VSLOT, M_ENTRY, 0 };
static const uint8_t kSettings[] = { M_METRONOME, M_COUNT_IN_CLICK, M_FULL_VELOCITY,
  M_MIDI_IN_CHANNEL, 0 };

static const uint8_t *members_of(unsigned ctx) {
  switch (ctx) {
    case C_DOC: return kDoc;
    case C_MADE: return kMade;
    case C_SESSION: return kSession;
    case C_KEYOBJ: return kKey;
    case C_UNIT: return kUnit;
    case C_DX7: return kDx7;
    case C_MOD: return kMod;
    case C_MODULE: return kModule;
    case C_MDATA: return kData;
    case C_CABLE: return kCable;
    case C_REF: return kRef;
    case C_TARGET: return kTarget;
    case C_VIEW: return kView;
    case C_SETTINGS: return kSettings;
    default: return NULL;
  }
}

static int is_array_ctx(unsigned ctx) {
  switch (ctx) {
    case C_SOUNDS: case C_PADS: case C_INSERTS: case C_MFXS: case C_MASTER: case C_CHAIN:
    case C_DX7S: case C_OPS: case C_OP: case C_GLOBALS: case C_RACK: case C_CABLES: case C_LINES:
      return 1;
    default:
      return 0;
  }
}

/* Members of the document by kind, beyond the head. */
static int doc_member_ok(unsigned m, unsigned kind) {
  const unsigned P = 1u << FM1_STATE_PROJECT, S = 1u << FM1_STATE_SOUND, F = 1u << FM1_STATE_FX,
                 MO = 1u << FM1_STATE_MODS, CL = 1u << FM1_STATE_CLIP, SE = 1u << FM1_STATE_SETTINGS;
  unsigned ok;
  switch (m) {
    case M_SESSION: case M_SOUNDS: case M_MASTER: case M_SET: ok = P; break;
    case M_SOUND: ok = S; break;
    case M_CHAIN: ok = F; break;
    case M_DX7: ok = P | S; break;
    case M_MOD: ok = P | S | F | MO; break;
    case M_CLIP: ok = CL; break;
    case M_SETTINGS: ok = SE; break;
    case M_VIEW: ok = P | S | F | MO | CL; break;
    default: ok = P | S | F | MO | CL | SE; break;
  }
  return (ok >> kind) & 1u;
}

/* FM6 voice fields' largest values, VCED order: 6 x 21 per operator, then 19. */
static const uint8_t kOpMax[21] = { 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 3, 3, 7, 3, 7, 99,
                                    1, 31, 99, 14 };
static const uint8_t kGlobMax[19] = { 99, 99, 99, 99, 99, 99, 99, 99, 31, 7, 1, 99, 99, 99, 99, 1, 5,
                                      7, 48 };
static const char *const kRoots[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                        "A#", "B" };
static const char *const kPolarity[4] = { "auto", "uni", "bi", "inv" };
static const char *const kCurves[8] = { "lin", "square", "cube", "root", "cbrt", "exp", "log", "s" };
static const char *const kModes[FM1_VIEW_MODES] = { "home", "fx", "glo", "seq", "session", "song",
                                                    "rack", "matrix", "chain" };
static const char *const kPanels[4] = { "track", "set", "clip", "step" };

/* ---- Small helpers ------------------------------------------------------------ */
static fm1_state_frame_t *top(fm1_state_json_reader_t *r) { return &r->frame[r->depth - 1u]; }

static void set_what(fm1_state_report_t *rep, const char *what) {
  size_t n = strlen(what);
  if (n >= sizeof(rep->what)) n = sizeof(rep->what) - 1u;
  memcpy(rep->what, what, n);
  rep->what[n] = '\0';
}

static void append(char *dst, size_t cap, size_t *len, const char *s, size_t n) {
  size_t i;
  for (i = 0; i < n && *len + 1 < cap; ++i) {
    const unsigned char c = (unsigned char)s[i];
    dst[(*len)++] = (char)(c >= 0x20 && c < 0x7F ? c : '?');
  }
  dst[*len] = '\0';
}

/* The JSON path of where the reader is: members by name, items by index. */
static void build_path(fm1_state_json_reader_t *r, int with_key) {
  char *p = r->rep->path;
  const size_t cap = sizeof(r->rep->path);
  size_t len = 0;
  unsigned i;
  p[0] = '\0';
  for (i = 1; i < r->depth; ++i) {
    const fm1_state_frame_t *parent = &r->frame[i - 1u], *f = &r->frame[i];
    append(p, cap, &len, "/", 1);
    if (!is_array_ctx(parent->ctx)) {
      const char *nm = kMember[f->member < M_COUNT ? f->member : M_UNKNOWN];
      append(p, cap, &len, nm, strlen(nm));
    } else {
      char t[8];
      unsigned v = f->index, k = 0;
      do { t[k++] = (char)('0' + v % 10u); v /= 10u; } while (v && k < sizeof(t));
      while (k) { --k; append(p, cap, &len, &t[k], 1); }
    }
  }
  if (with_key && r->keylen && r->depth && !is_array_ctx(top(r)->ctx)) {
    append(p, cap, &len, "/", 1);
    append(p, cap, &len, r->key, r->keylen);
  } else if (r->depth && is_array_ctx(top(r)->ctx) && top(r)->items) {
    char t[8];
    unsigned v = top(r)->items - 1u, k = 0;
    append(p, cap, &len, "/", 1);
    do { t[k++] = (char)('0' + v % 10u); v /= 10u; } while (v && k < sizeof(t));
    while (k) { --k; append(p, cap, &len, &t[k], 1); }
  }
  if (!len) append(p, cap, &len, "/", 1);
}

static int refuse(fm1_state_json_reader_t *r, unsigned code, const char *what) {
  if (!r->stop) {
    r->stop = 1;
    r->rep->code = (uint8_t)code;
    set_what(r->rep, what);
    build_path(r, 1);
    r->rep->line = r->tok.line;
    r->rep->col = r->tok.col;
    r->rep->offset = r->tok.offset;
    r->rep->near_at = r->keylen && r->key_at < r->tok.offset ? r->key_at
                                                             : (r->tok.offset ? r->tok.offset - 1u : 0u);
  }
  return 0;
}

static int bad(fm1_state_json_reader_t *r, const char *what) { return refuse(r, FM1_STATE_BAD, what); }

static void skipped(fm1_state_json_reader_t *r, const char *what) {
  fm1_state_report_t *rep = r->rep;
  if (!rep->skipped++) {
    size_t len = 0;
    char keep[sizeof(rep->path)];
    memcpy(keep, rep->path, sizeof(keep));
    build_path(r, 1);
    rep->first_skip[0] = '\0';
    append(rep->first_skip, sizeof(rep->first_skip), &len, rep->path, strlen(rep->path));
    append(rep->first_skip, sizeof(rep->first_skip), &len, ": ", 2);
    append(rep->first_skip, sizeof(rep->first_skip), &len, what, strlen(what));
    memcpy(rep->path, keep, sizeof(keep));
  }
}

static void unknown_engine(fm1_state_json_reader_t *r, const char *id) {
  if (!r->rep->unknown++) {
    size_t len = 0;
    append(r->rep->name, sizeof(r->rep->name), &len, id, strlen(id));
  }
}

static int emit(fm1_state_json_reader_t *r, fm1_rec_t *rec) {
  ++r->rep->records;
  if (!r->sink(r->sctx, rec)) {
    if (!r->stop) {
      r->stop = 1;
      if (r->rep->code == FM1_STATE_OK) r->rep->code = FM1_STATE_STOPPED;
      if (!r->rep->what[0]) set_what(r->rep, "the loader stopped");
    }
    return 0;
  }
  return 1;
}

static void rec_init(fm1_rec_t *rec, unsigned type) {
  memset(rec, 0, sizeof(*rec));
  rec->type = (uint8_t)type;
}

static int push(fm1_state_json_reader_t *r, unsigned ctx, unsigned index, unsigned role,
                unsigned sound, unsigned slot, const void *owner) {
  fm1_state_frame_t *f;
  if (r->depth > FM1_STATE_DEPTH) return refuse(r, FM1_STATE_TOO_BIG, "nested too deep");
  f = &r->frame[r->depth++];
  memset(f, 0, sizeof(*f));
  f->ctx = (uint8_t)ctx;
  f->member = r->depth > 1u && !is_array_ctx(r->frame[r->depth - 2u].ctx) ? r->member : M_NONE;
  f->index = (uint8_t)(index > 255u ? 255u : index);
  f->role = (uint8_t)role;
  f->sound = (uint8_t)sound;
  f->slot = (uint8_t)slot;
  f->owner = owner;
  return 1;
}

static uint32_t hash_key(const char *s, size_t n) {
  uint32_t h = 2166136261u;
  size_t i;
  for (i = 0; i < n; ++i) {
    h ^= (unsigned char)s[i];
    h *= 16777619u;
  }
  return h;
}

/* An unresolved key in the open object at tokenizer depth d: a duplicate
 * of one before it refuses the file (by a 32-bit hash; past 64 such keys on
 * the open path duplicates go unchecked, rather than refuse a file a newer
 * level may write). */
static int unknown_key(fm1_state_json_reader_t *r, const char *s, size_t n, unsigned d) {
  const uint32_t h = hash_key(s, n);
  unsigned i;
  for (i = r->n_unk; i > 0 && r->unk_depth[i - 1u] == d; --i) {
    if (r->unk_hash[i - 1u] == h) return bad(r, "duplicate key");
  }
  if (r->n_unk < 64u) {
    r->unk_hash[r->n_unk] = h;
    r->unk_depth[r->n_unk++] = (uint8_t)d;
  }
  return 1;
}

static void unknown_pop(fm1_state_json_reader_t *r, unsigned d) {
  while (r->n_unk > 0 && r->unk_depth[r->n_unk - 1u] > d) --r->n_unk;
}

/* Unit index for unit_e: sounds 0-3, inserts 4-11, master or chain 12-15. */
static int unit_index(unsigned role, unsigned sound, unsigned slot) {
  switch (role) {
    case FM1_ROLE_SOUND: return sound < 4u ? (int)sound : -1;
    case FM1_ROLE_INSERT: return sound < 4u && slot < 2u ? (int)(4u + 2u * sound + slot) : -1;
    case FM1_ROLE_MASTER: return slot < 4u ? (int)(12u + slot) : -1;
    default: return -1;
  }
}

/* A cable unit code to unit_e's index (-1: the host or none). */
static int code_index(unsigned code) {
  if (code == FM1_MOD_SOUND) return 0;
  if (code >= 17u && code <= 19u) return (int)(code - 16u);
  if (code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 16u && ((code - FM1_MOD_INSERT) & 3u) < 2u) {
    const unsigned k = (code - FM1_MOD_INSERT) / 4u, j = (code - FM1_MOD_INSERT) & 3u;
    return (int)(4u + 2u * k + j);
  }
  if (code == FM1_MOD_FX1) return 12;
  if (code == FM1_MOD_FX2) return 13;
  if (code == FM1_STATE_CHAIN3) return 14;
  if (code == FM1_STATE_CHAIN4) return 15;
  return -1;
}

/* A unit's name in a file of this kind to its code, or -1. */
static int unit_code(unsigned kind, const char *s, size_t n) {
  if (n == 4 && memcmp(s, "host", 4) == 0) return FM1_MOD_HOST;
  if (kind == FM1_STATE_SOUND) {
    if (n == 3 && memcmp(s, "snd", 3) == 0) return FM1_MOD_SOUND;
    if (n == 7 && memcmp(s, "snd.fx", 6) == 0 && (s[6] == '1' || s[6] == '2')) {
      return (int)fm1_mod_insert_unit(0, (unsigned)(s[6] - '1'));
    }
    return -1;
  }
  if (kind == FM1_STATE_FX) {
    static const int kChain[4] = { FM1_MOD_FX1, FM1_MOD_FX2, FM1_STATE_CHAIN3, FM1_STATE_CHAIN4 };
    if (n == 3 && s[0] == 'f' && s[1] == 'x' && s[2] >= '1' && s[2] <= '4') return kChain[s[2] - '1'];
    return -1;
  }
  if (n == 3 && s[0] == 'f' && s[1] == 'x' && (s[2] == '1' || s[2] == '2')) {
    return s[2] == '1' ? FM1_MOD_FX1 : FM1_MOD_FX2;
  }
  if (n >= 4 && memcmp(s, "snd", 3) == 0 && s[3] >= '1' && s[3] <= '4') {
    const unsigned k = (unsigned)(s[3] - '1');
    if (n == 4) return (int)fm1_mod_sound_unit(k);
    if (n == 8 && memcmp(s + 4, ".fx", 3) == 0 && (s[7] == '1' || s[7] == '2')) {
      return (int)fm1_mod_insert_unit(k, (unsigned)(s[7] - '1'));
    }
  }
  return -1;
}

static int is_id(const char *s, size_t n) {
  size_t i;
  if (n < 1 || n > 15 || s[0] < 'a' || s[0] > 'z') return 0;
  for (i = 1; i < n; ++i) {
    const char c = s[i];
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-')) return 0;
  }
  return 1;
}

static int sbuf_is(const fm1_state_json_reader_t *r, const char *s) {
  return !r->sbuf_over && strlen(s) == r->sbuf_n && memcmp(r->sbuf, s, r->sbuf_n) == 0;
}

static int sbuf_pick(const fm1_state_json_reader_t *r, const char *const *names, int n) {
  int i;
  for (i = 0; i < n; ++i) {
    if (sbuf_is(r, names[i])) return i;
  }
  return -1;
}

/* Gathers a short string's pieces; returns 1 at its last piece. */
static int gather(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  uint32_t i;
  if (ev->first) { r->sbuf_n = 0; r->sbuf_over = 0; }
  for (i = 0; i < ev->n; ++i) {
    if (r->sbuf_n < sizeof(r->sbuf) - 1u) r->sbuf[r->sbuf_n++] = ev->s[i];
    else r->sbuf_over = 1;
  }
  r->sbuf[r->sbuf_n] = '\0';
  return ev->last;
}

/* An integer value in [lo, hi]: out of range is clamped (repaired); a
 * fraction, an exponent or another type refuses the file. */
static int int_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev, int64_t lo, int64_t hi,
                     int64_t *out) {
  int64_t v = 0;
  int st;
  if (ev->type != FM1_JSON_NUM) return bad(r, "an integer was expected");
  st = fm1_num_int(ev->s, ev->n, INT64_MIN + 1, INT64_MAX, &v);
  if (st == FM1_NUM_NOT_INT) return bad(r, "a fraction or an exponent where an integer belongs");
  if (st == FM1_NUM_RANGE) { v = ev->s[0] == '-' ? lo : hi; ++r->rep->repaired; }
  else if (st != FM1_NUM_OK) return bad(r, "not a number");
  if (v < lo) { v = lo; ++r->rep->repaired; }
  if (v > hi) { v = hi; ++r->rep->repaired; }
  *out = v;
  return 1;
}

static int bool_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev, uint8_t *out) {
  if (ev->type == FM1_JSON_TRUE) *out = 1;
  else if (ev->type == FM1_JSON_FALSE) *out = 0;
  else return bad(r, "true or false was expected");
  return 1;
}

/* A float value, exact; -0 is 0. */
static int float_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev, float *out) {
  float f;
  int st;
  if (ev->type != FM1_JSON_NUM) return bad(r, "a number was expected");
  st = fm1_num_f32(ev->s, ev->n, &f);
  if (st == FM1_NUM_RANGE) return bad(r, "a number beyond a float32");
  if (st != FM1_NUM_OK) return bad(r, "not a number");
  if (f == 0.0f) f = 0.0f;
  *out = f;
  return 1;
}

/* ---- Text: info members, filtered and capped as they stream ------------------- */
static int text_cap(unsigned key) {
  switch (key) {
    case FM1_INFO_NAME: return 16;
    case FM1_INFO_TITLE: return 80;
    case FM1_INFO_ABOUT: return 240;
    case FM1_INFO_AUTHOR: return 64;
    case FM1_INFO_LICENCE: return 32;
    default: return 64;
  }
}

static int text_flush(fm1_state_json_reader_t *r, int last) {
  fm1_rec_t rec;
  if (!r->out_n && !last) return 1;
  rec_init(&rec, FM1_REC_INFO);
  rec.piece = (uint8_t)((r->piece_out ? 0u : FM1_REC_FIRST) | (last ? FM1_REC_LAST : 0u));
  rec.u.info.key = r->text_key;
  rec.u.info.n = r->out_n;
  rec.u.info.s = r->out;
  r->piece_out = 1;
  r->out_n = 0;
  return emit(r, &rec);
}

/* Filters one piece: control characters and bidi overrides are stripped;
 * the screen's name and `made` keep printable ASCII, a licence SPDX's
 * characters; past the cap the rest is cut. Each removal counts as one
 * repair. */
static int text_piece(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  uint32_t i = 0;
  const int cap = text_cap(r->text_key);
  if (ev->type != FM1_JSON_STR) return bad(r, "text was expected");
  if (ev->first) { r->textlen = 0; r->out_n = 0; r->piece_out = 0; r->sbuf_over = 0; }
  while (i < ev->n) {
    const unsigned char c = (unsigned char)ev->s[i];
    unsigned len = c < 0x80u ? 1u : (c < 0xE0u ? 2u : (c < 0xF0u ? 3u : 4u));
    uint32_t cp = c;
    int keep = 1;
    unsigned k;
    if (i + len > ev->n) len = ev->n - i;     /* never: pieces end on code points */
    if (len > 1) {
      cp = c & (len == 2 ? 0x1Fu : (len == 3 ? 0x0Fu : 0x07u));
      for (k = 1; k < len; ++k) cp = (cp << 6) | ((unsigned char)ev->s[i + k] & 0x3Fu);
    }
    if (cp < 0x20u || cp == 0x7Fu || (cp >= 0x202Au && cp <= 0x202Eu) || (cp >= 0x2066u && cp <= 0x2069u)) {
      keep = 0;
    } else if (r->text_key == FM1_INFO_NAME || r->text_key == FM1_INFO_BY ||
               r->text_key == FM1_INFO_VERSION || r->text_key == FM1_INFO_COMMIT) {
      keep = cp < 0x7Fu;
    } else if (r->text_key == FM1_INFO_LICENCE) {
      keep = (cp >= 'A' && cp <= 'Z') || (cp >= 'a' && cp <= 'z') || (cp >= '0' && cp <= '9') ||
             cp == '.' || cp == '+' || cp == '-';
    }
    if (keep && (int)r->textlen >= cap) {
      keep = 0;
      if (!r->sbuf_over) { r->sbuf_over = 1; ++r->rep->repaired; }
    } else if (!keep) {
      ++r->rep->repaired;
    }
    if (keep) {
      if (r->out_n + len > sizeof(r->out) && !text_flush(r, 0)) return 0;
      memcpy(r->out + r->out_n, ev->s + i, len);
      r->out_n = (uint8_t)(r->out_n + len);
      ++r->textlen;
    }
    i += len;
  }
  if (ev->last) return text_flush(r, 1);
  return 1;
}

/* ---- movy1 lines ---------------------------------------------------------------- */
static int clip_prefix_ok(const char *h) {
  if (h[0] == 'a' && h[1] == 'u') {
    return memcmp(h, "au 0 ", 5) == 0 && h[5] >= '0' && h[5] <= '7' && h[6] == ' ';
  }
  return memcmp(h, "cl 0 0 ", 7) == 0 || memcmp(h, "cp 0 0 ", 7) == 0 ||
         memcmp(h, "lk 0 0 ", 7) == 0 || memcmp(h, "tg 0 0 ", 7) == 0;
}

static int line_piece(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  fm1_rec_t rec;
  uint32_t i;
  if (ev->type != FM1_JSON_STR) return bad(r, "a movy1 line (a string) was expected");
  if (ev->first) {
    r->line_n = 0;
    r->sbuf_n = 0;
    if (f->slot == FM1_LINES_CLIP && r->lines >= 12u) return bad(r, "a clip has at most 12 lines");
  }
  for (i = 0; i < ev->n; ++i) {
    const unsigned char c = (unsigned char)ev->s[i];
    if (c < 0x20u || c == 0x7Fu) return bad(r, "a control character in a movy1 line");
    if (r->sbuf_n < 8u) r->sbuf[r->sbuf_n++] = (char)c;
  }
  r->line_n += ev->n;
  rec_init(&rec, FM1_REC_LINE);
  rec.piece = (uint8_t)((ev->first ? FM1_REC_FIRST : 0u) | (ev->last ? FM1_REC_LAST : 0u));
  rec.u.line.which = f->slot;
  rec.u.line.n = ev->n;
  rec.u.line.s = ev->s;
  if (!emit(r, &rec)) return 0;
  if (ev->last) {
    r->sbuf[r->sbuf_n < 8u ? r->sbuf_n : 7u] = '\0';
    if (f->slot == FM1_LINES_SET && r->lines == 0 && !(r->line_n == 5 && memcmp(r->sbuf, "movy1", 5) == 0)) {
      return bad(r, "a set's first line is movy1");
    }
    if (f->slot == FM1_LINES_CLIP && (r->line_n < 7u || !clip_prefix_ok(r->sbuf))) {
      return bad(r, "a clip line is au, cl, cp, lk or tg at track 0 and slot 0");
    }
    ++r->lines;
    ++r->rep->lines;
  }
  return 1;
}

/* ---- Pattern data --------------------------------------------------------------- */
static int data_flush(fm1_state_json_reader_t *r, fm1_state_frame_t *f, int last) {
  fm1_rec_t rec;
  if (!r->out_n && !last) return 1;
  rec_init(&rec, FM1_REC_DATA);
  rec.slot = f->slot;
  rec.piece = (uint8_t)((r->piece_out ? 0u : FM1_REC_FIRST) | (last ? FM1_REC_LAST : 0u));
  rec.u.data.version = f->flags;
  rec.u.data.n = r->out_n;
  rec.u.data.b = (const uint8_t *)r->out;
  r->piece_out = 1;
  r->out_n = 0;
  return emit(r, &rec);
}

static int hex_piece(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  uint32_t i;
  if (ev->type != FM1_JSON_STR) return bad(r, "pattern data is hex text");
  if (ev->first) { r->out_n = 0; r->piece_out = 0; r->acc_has = 0; r->data_one = 0; }
  for (i = 0; i < ev->n; ++i) {
    const char c = ev->s[i];
    unsigned v;
    if (c >= '0' && c <= '9') v = (unsigned)(c - '0');
    else if (c >= 'a' && c <= 'f') v = (unsigned)(c - 'a' + 10);
    else return bad(r, "pattern data is lower-case hex");
    if (!(r->acc_has & 0x10u)) {
      r->acc_has = (uint8_t)(0x10u | v);
      continue;
    }
    if (r->data_one >= FM1_STATE_DATA_ONE || r->data_total >= FM1_STATE_DATA) {
      return refuse(r, FM1_STATE_TOO_BIG, "too much pattern data");
    }
    if (r->out_n >= sizeof(r->out) && !data_flush(r, f, 0)) return 0;
    r->out[r->out_n++] = (char)(((r->acc_has & 0x0Fu) << 4) | v);
    r->acc_has = 0;
    ++r->data_one;
    ++r->data_total;
  }
  if (ev->last) {
    if (r->acc_has & 0x10u) return bad(r, "pattern data has an odd number of hex digits");
    f->seen |= 1ull << 63;     /* hex given */
    return data_flush(r, f, 1);
  }
  return 1;
}

/* ---- Parameters ------------------------------------------------------------------- */

/* A key of a params object: what it names. */
static int params_key(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  const fm1_param_t *table = NULL;
  unsigned n = 0;
  const char *owner = NULL;
  int i;
  r->pidx = 0xFFu;
  r->key_uid = 0;
  r->member = M_UNKNOWN;
  if (f->ctx == C_MPARAMS) {
    const fm1_mod_kind_t *k = (const fm1_mod_kind_t *)f->owner;
    if (k) { table = k->params; n = k->n_params; owner = k->id; }
  } else {
    const fm1_engine_t *e = (const fm1_engine_t *)f->owner;
    if (e) { table = e->params; n = e->n_params; owner = e->id; }
  }
  i = table ? fm1_state_param_find(r->nm, owner, table, n, r->key, r->keylen) : -1;
  if (i >= 0) {
    const int focus = f->ctx == C_MPARAMS ? 0 : fm1_state_param_focus((const fm1_engine_t *)f->owner, (unsigned)i);
    if (i < 64 && ((f->seen >> i) & 1u)) return bad(r, "duplicate key: two keys name one parameter");
    if (i < 64) f->seen |= 1ull << i;
    if (f->ctx == C_PARAMS && focus == 2) {
      skipped(r, "a per-pad value outside pads");
      return 1;
    }
    if (f->ctx == C_PAD && focus != 2) {
      skipped(r, "not a per-pad value");
      return 1;
    }
    r->pidx = (uint8_t)i;
    r->key_uid = table[i].uid;
    r->member = M_PNAME;
    return 1;
  }
  if (!unknown_key(r, r->key, r->keylen, ev->depth)) return 0;
  if (r->keylen >= 2 && r->key[0] == '#') {
    /* "#UID" this build cannot name (an engine or kind it lacks, or a
     * parameter a newer build added): kept by uid, so the file passes
     * through unchanged; an applier drops what its engine does not have. */
    unsigned uid = 0;
    size_t k;
    int ok = r->key[1] != '0' && r->keylen <= 5;
    for (k = 1; ok && k < r->keylen; ++k) {
      if (r->key[k] < '0' || r->key[k] > '9') ok = 0;
      else uid = uid * 10u + (unsigned)(r->key[k] - '0');
    }
    if (ok && uid >= 1u && uid <= FM1_PARAM_UID_MAX) {
      r->key_uid = (uint16_t)uid;
      r->member = M_PNAME;
      return 1;
    }
  }
  skipped(r, table ? "a name this build does not resolve" : "a name for an engine this build lacks");
  return 1;
}

static int param_value(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  fm1_rec_t rec;
  const fm1_param_t *p = NULL;
  if (r->pidx != 0xFFu) {
    if (f->ctx == C_MPARAMS) p = &((const fm1_mod_kind_t *)f->owner)->params[r->pidx];
    else p = &((const fm1_engine_t *)f->owner)->params[r->pidx];
  }
  if (ev->type == FM1_JSON_STR && !gather(r, ev)) return 1;   /* wait for the last piece */
  rec_init(&rec, FM1_REC_PARAM);
  rec.role = f->ctx == C_MPARAMS ? (uint8_t)FM1_ROLE_MODULE : f->role;
  rec.sound = f->sound;
  rec.slot = f->slot;
  rec.u.param.uid = r->key_uid;
  rec.u.param.focus = f->ctx == C_PAD ? f->index : (uint8_t)FM1_FOCUS_NONE;
  if (!p) {
    float v;
    if (ev->type == FM1_JSON_STR) {
      skipped(r, "a value by name for a parameter this build cannot name");
      return 1;
    }
    if (!float_value(r, ev, &v)) return 0;
    rec.u.param.vtype = FM1_VAL_F32;
    rec.u.param.bits = fm1_num_bits(v);
    return emit(r, &rec);
  }
  if (p->type == FM1_PARAM_ENUM) {
    const int count = (int)(p->max - p->min) + 1;
    int k;
    if (ev->type == FM1_JSON_STR) {
      k = r->sbuf_over ? -1 : fm1_state_entry_find(p, r->sbuf, r->sbuf_n);
      if (k < 0) {
        skipped(r, "not an entry of the list");
        return 1;
      }
    } else {
      int64_t v;
      if (!int_value(r, ev, 0, count - 1, &v)) return 0;
      k = (int)v;
    }
    rec.u.param.vtype = FM1_VAL_INDEX;
    rec.u.param.bits = (uint32_t)k;
  } else {
    float v, c;
    if (!float_value(r, ev, &v)) return 0;
    c = fm1_param_clamp(p, v);
    if (fm1_num_bits(c) != fm1_num_bits(v)) ++r->rep->repaired;
    if (c == 0.0f) c = 0.0f;
    rec.u.param.vtype = FM1_VAL_F32;
    rec.u.param.bits = fm1_num_bits(c);
  }
  return emit(r, &rec);
}

/* ---- Keys ------------------------------------------------------------------------- */
#define TOP_SOUNDS 0x01u
#define TOP_MASTER 0x02u
#define TOP_MOD 0x04u
#define TOP_UNITS 0x08u

static int on_key(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  fm1_state_frame_t *f = top(r);
  const uint8_t *mm;
  unsigned i;
  r->keylen = (uint8_t)(ev->n < FM1_STATE_KEY ? ev->n : FM1_STATE_KEY);
  memcpy(r->key, ev->s, r->keylen);
  r->key_at = r->tok.offset >= ev->n + 1u ? r->tok.offset - ev->n - 1u : 0u;   /* its opening quote */
  if (f->ctx == C_PARAMS || f->ctx == C_PAD || f->ctx == C_MPARAMS) return params_key(r, f, ev);
  mm = members_of(f->ctx);
  r->member = M_UNKNOWN;
  for (i = 0; mm && mm[i]; ++i) {
    const char *name = kMember[mm[i]];
    if (strlen(name) == ev->n && memcmp(name, ev->s, ev->n) == 0) {
      r->member = mm[i];
      break;
    }
  }
  if (r->member == M_UNKNOWN) {
    if (f->ctx == C_DOC && r->top < 2) {
      return r->top == 0 ? refuse(r, FM1_STATE_NOT_LUNAR, "a Lunar Modulator file opens with lunar")
                         : bad(r, "context first: kind follows lunar");
    }
    if (!unknown_key(r, ev->s, ev->n, ev->depth)) return 0;
    skipped(r, "a member this build does not know");
    return 1;
  }
  if ((f->seen >> i) & 1u) return bad(r, "duplicate key");
  f->seen |= 1ull << i;
  switch (f->ctx) {
    case C_DOC:
      if (r->top == 0 && r->member != M_LUNAR && r->member != M_SCHEMA) {
        return refuse(r, FM1_STATE_NOT_LUNAR, "a Lunar Modulator file opens with lunar");
      }
      if (r->member == M_SCHEMA && r->top != 0) return bad(r, "context first: $schema comes before lunar");
      if (r->top == 1 && r->member != M_KIND) return bad(r, "context first: kind follows lunar");
      if (r->top >= 2 && !doc_member_ok(r->member, r->kind)) {
        return bad(r, "not a member of this kind of file");
      }
      if ((r->member == M_SOUNDS || r->member == M_MASTER || r->member == M_SOUND ||
           r->member == M_CHAIN) && (r->seen_top & TOP_MOD)) {
        return bad(r, "context first: mod comes after the units its cables name");
      }
      break;
    case C_UNIT:
      if ((r->member == M_PARAMS || r->member == M_PADS) && !(f->seen & 1u)) {
        return bad(r, "context first: a unit's engine comes before its params and pads");
      }
      if ((r->member == M_ON && f->role != FM1_ROLE_MFX) ||
          ((r->member == M_PADS || r->member == M_LEVEL || r->member == M_INSERTS ||
            r->member == M_MIDI_FX) && f->role != FM1_ROLE_SOUND)) {
        f->seen &= ~(1ull << i);
        r->member = M_UNKNOWN;
        if (!unknown_key(r, ev->s, ev->n, ev->depth)) return 0;
        skipped(r, "not a member of this unit");
      }
      break;
    case C_MODULE:
      if ((r->member == M_PARAMS || r->member == M_DATA) && (f->seen & 3u) != 3u) {
        return bad(r, "context first: a module's pos and kind come before its params and data");
      }
      break;
    case C_MDATA:
      if (r->member == M_HEX && !(f->seen & 1u)) {
        return bad(r, "context first: pattern data's version comes before its hex");
      }
      break;
    case C_MOD:
      if (r->member == M_RACK && (f->seen & 4u)) return bad(r, "context first: rack comes before cables");
      break;
    default:
      break;
  }
  return 1;
}

/* ---- Values in objects ---------------------------------------------------------------- */
static int want_obj(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  return ev->type == FM1_JSON_OBJ ? 1 : bad(r, "an object was expected");
}
static int want_arr(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  return ev->type == FM1_JSON_ARR ? 1 : bad(r, "an array was expected");
}

static int doc_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  fm1_rec_t rec;
  switch (r->member) {
    case M_SCHEMA:
      if (ev->type != FM1_JSON_STR) return bad(r, "$schema is a string");
      return 1;
    case M_LUNAR:
      if (ev->type != FM1_JSON_STR) return refuse(r, FM1_STATE_NOT_LUNAR, "lunar is the format level, \"1.0\"");
      if (!gather(r, ev)) return 1;
      {
        unsigned major = 0, minor = 0, k = 0, digits = 0;
        int ok = r->sbuf_n >= 3 && !r->sbuf_over;
        while (ok && k < r->sbuf_n && r->sbuf[k] >= '0' && r->sbuf[k] <= '9') {
          major = major * 10u + (unsigned)(r->sbuf[k++] - '0');
          if (++digits > 3) ok = 0;
        }
        if (!digits || k >= r->sbuf_n || r->sbuf[k] != '.') ok = 0;
        ++k;
        digits = 0;
        while (ok && k < r->sbuf_n && r->sbuf[k] >= '0' && r->sbuf[k] <= '9') {
          minor = minor * 10u + (unsigned)(r->sbuf[k++] - '0');
          if (++digits > 3) ok = 0;
        }
        if (!digits || k != r->sbuf_n) ok = 0;
        if (!ok) return refuse(r, FM1_STATE_NOT_LUNAR, "lunar is the format level, \"1.0\"");
        r->rep->major = (uint8_t)major;
        r->rep->minor = (uint8_t)minor;
        if (major != FM1_STATE_MAJOR || minor > FM1_STATE_MINOR) {
          return refuse(r, FM1_STATE_TOO_NEW, "made with a newer Lunar Modulator");
        }
        r->level_minor = (uint8_t)minor;
        r->top = 1;
      }
      return 1;
    case M_KIND:
      if (ev->type != FM1_JSON_STR) return bad(r, "kind is a string");
      if (!gather(r, ev)) return 1;
      {
        const unsigned k = r->sbuf_over ? 0u : fm1_state_kind_code(r->sbuf, r->sbuf_n);
        if (sbuf_is(r, "metadata")) return bad(r, "the metadata export is not a state to load");
        if (k == FM1_STATE_KIND_NONE || k == FM1_STATE_SET || k == FM1_STATE_DX7BANK) {
          return bad(r, "not a kind of file this build knows");
        }
        r->kind = (uint8_t)k;
        r->rep->kind = (uint8_t)k;
        r->top = 2;
        rec_init(&rec, FM1_REC_HEAD);
        rec.u.head.kind = (uint8_t)k;
        rec.u.head.major = FM1_STATE_MAJOR;
        rec.u.head.minor = r->level_minor;
        return emit(r, &rec);
      }
    case M_MADE:
      return want_obj(r, ev) && push(r, C_MADE, 0, 0, 0, 0, NULL);
    case M_NAME: r->text_key = FM1_INFO_NAME; return text_piece(r, ev);
    case M_TITLE: r->text_key = FM1_INFO_TITLE; return text_piece(r, ev);
    case M_ABOUT: r->text_key = FM1_INFO_ABOUT; return text_piece(r, ev);
    case M_AUTHOR: r->text_key = FM1_INFO_AUTHOR; return text_piece(r, ev);
    case M_LICENCE: r->text_key = FM1_INFO_LICENCE; return text_piece(r, ev);
    case M_SESSION:
      if (!want_obj(r, ev)) return 0;
      rec_init(&r->acc, FM1_REC_SESSION);
      return push(r, C_SESSION, 0, 0, 0, 0, NULL);
    case M_SOUNDS:
      r->seen_top |= TOP_SOUNDS | TOP_UNITS;
      return want_arr(r, ev) && push(r, C_SOUNDS, 0, 0, 0, 0, NULL);
    case M_SOUND:
      r->seen_top |= TOP_UNITS;
      return want_obj(r, ev) && push(r, C_UNIT, 0, FM1_ROLE_SOUND, 0, 0, NULL);
    case M_MASTER:
      r->seen_top |= TOP_MASTER | TOP_UNITS;
      return want_arr(r, ev) && push(r, C_MASTER, 0, 0, 0, 0, NULL);
    case M_CHAIN:
      r->seen_top |= TOP_UNITS;
      return want_arr(r, ev) && push(r, C_CHAIN, 0, 0, 0, 0, NULL);
    case M_DX7:
      return want_arr(r, ev) && push(r, C_DX7S, 0, 0, 0, 0, NULL);
    case M_MOD:
      if (!want_obj(r, ev)) return 0;
      r->seen_top |= TOP_MOD;
      if (!push(r, C_MOD, 0, 0, 0, 0, NULL)) return 0;
      rec_init(&rec, FM1_REC_MOD);
      return emit(r, &rec);
    case M_SET:
    case M_CLIP:
      if (!want_arr(r, ev)) return 0;
      r->lines = 0;
      return push(r, C_LINES, 0, 0, 0, r->member == M_SET ? FM1_LINES_SET : FM1_LINES_CLIP, NULL);
    case M_SETTINGS:
      return want_obj(r, ev) && push(r, C_SETTINGS, 0, 0, 0, 0, NULL);
    case M_VIEW:
      if (!want_obj(r, ev)) return 0;
      rec_init(&r->acc, FM1_REC_VIEW);
      r->acc.u.view.mode = 0xFF;
      return push(r, C_VIEW, 0, 0, 0, 0, NULL);
    default:
      return bad(r, "unexpected member");
  }
}

static int unit_value(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  fm1_rec_t rec;
  switch (r->member) {
    case M_ENGINE: {
      const fm1_engine_t *e;
      int ix;
      if (ev->type != FM1_JSON_STR) return bad(r, "engine is an id");
      if (!gather(r, ev)) return 1;
      if (r->sbuf_over || !is_id(r->sbuf, r->sbuf_n)) return bad(r, "engine is an id of a-z, 0-9 and -");
      e = fm1_state_engine(r->nm, f->role, r->sbuf);
      if (!e) unknown_engine(r, r->sbuf);
      f->owner = e;
      ix = unit_index(f->role, f->sound, f->slot);
      if (ix >= 0) r->unit_e[ix] = e;
      rec_init(&rec, FM1_REC_UNIT);
      rec.role = f->role;
      rec.sound = f->sound;
      rec.slot = f->slot;
      memcpy(rec.u.unit.id, r->sbuf, r->sbuf_n + 1u);
      ++r->rep->units;
      return emit(r, &rec);
    }
    case M_ON:
      rec_init(&rec, FM1_REC_ON);
      rec.role = f->role;
      rec.sound = f->sound;
      rec.slot = f->slot;
      if (!bool_value(r, ev, &rec.u.on)) return 0;
      return emit(r, &rec);
    case M_PARAMS:
      return want_obj(r, ev) && push(r, C_PARAMS, 0, f->role, f->sound, f->slot, f->owner);
    case M_PADS: {
      const fm1_engine_t *e = (const fm1_engine_t *)f->owner;
      if (!want_arr(r, ev)) return 0;
      if (e && !e->pad_count) {
        skipped(r, "pads of an engine that is not a pad kit");
        r->skip = (uint8_t)(ev->depth + 1u);
        return 1;
      }
      return push(r, C_PADS, 0, f->role, f->sound, f->slot, f->owner);
    }
    case M_LEVEL: {
      float v;
      if (!float_value(r, ev, &v)) return 0;
      if (!(v >= 0.0f)) { v = 0.0f; ++r->rep->repaired; }
      if (v > 100.0f) { v = 100.0f; ++r->rep->repaired; }
      rec_init(&rec, FM1_REC_LEVEL);
      rec.role = FM1_ROLE_SOUND;
      rec.sound = f->sound;
      rec.u.level = fm1_num_bits(v);
      return emit(r, &rec);
    }
    case M_INSERTS:
      return want_arr(r, ev) && push(r, C_INSERTS, 0, 0, f->sound, 0, NULL);
    case M_MIDI_FX:
      return want_arr(r, ev) && push(r, C_MFXS, 0, 0, f->sound, 0, NULL);
    default:
      return bad(r, "unexpected member");
  }
}

static int cable_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  fm1_mod_slot_t *s = &r->acc.u.cable.s;
  int64_t v;
  uint8_t b;
  int16_t q;
  int st, k;
  switch (r->member) {
    case M_SLOT:
      if (!int_value(r, ev, 1, 32, &v)) return 0;
      if ((r->cable_slots >> (v - 1)) & 1u) return bad(r, "two cables in one matrix slot");
      r->cable_slots |= 1u << (v - 1);
      r->acc.slot = (uint8_t)(v - 1);
      r->acc_has |= 1u;
      return 1;
    case M_ON:
      if (!bool_value(r, ev, &b)) return 0;
      s->flags = (uint8_t)(b ? (s->flags | FM1_MOD_SLOT_ON) : (s->flags & ~FM1_MOD_SLOT_ON));
      return 1;
    case M_FROM:
    case M_VIA:
      if (r->member == M_VIA && ev->type == FM1_JSON_NULL) { s->via = FM1_MOD_NONE; return 1; }
      if (!want_obj(r, ev)) return 0;
      r->ref_which = r->member == M_FROM ? 0 : 1;
      r->ref_has = 0;
      r->ref_source = -1;
      r->ref_module = 0;
      r->ref_port_idx = 0;
      r->ref_port[0] = '\0';
      if (r->member == M_FROM) r->acc_has |= 2u;
      return push(r, C_REF, 0, 0, 0, 0, NULL);
    case M_TO:
      if (!want_obj(r, ev)) return 0;
      r->tgt_has = 0;
      r->tgt_module = 0;
      r->tgt_unit = 0;
      r->tgt_gate_idx = 0;
      r->tgt_param[0] = '\0';
      r->ref_port[0] = '\0';
      r->acc_has |= 4u;
      return push(r, C_TARGET, 0, 0, 0, 0, NULL);
    case M_AMOUNT:
    case M_OFFSET:
      if (ev->type != FM1_JSON_NUM) return bad(r, "a percent was expected");
      st = fm1_num_q14(ev->s, ev->n, &q);
      if (st == FM1_NUM_CLAMPED) ++r->rep->repaired;
      else if (st != FM1_NUM_OK) return bad(r, "not a number");
      if (r->member == M_AMOUNT) { s->amount = q; r->acc_has |= 8u; }
      else s->offset = q;
      return 1;
    case M_POLARITY:
    case M_CURVE:
      if (ev->type != FM1_JSON_STR) return bad(r, "a name was expected");
      if (!gather(r, ev)) return 1;
      if (r->member == M_POLARITY) {
        k = sbuf_pick(r, kPolarity, 4);
        if (k < 0) { skipped(r, "not a polarity"); return 1; }
        s->flags = (uint8_t)((s->flags & ~FM1_MOD_SLOT_POL_MASK) | ((unsigned)k << FM1_MOD_SLOT_POL_SHIFT));
      } else {
        k = sbuf_pick(r, kCurves, 8);
        if (k < 0) { skipped(r, "not a curve"); return 1; }
        s->flags = (uint8_t)((s->flags & ~FM1_MOD_SLOT_CURVE_MASK) | ((unsigned)k << FM1_MOD_SLOT_CURVE_SHIFT));
      }
      return 1;
    case M_VOICE:
      if (!bool_value(r, ev, &b)) return 0;
      s->flags = (uint8_t)(b ? (s->flags | FM1_MOD_SLOT_VOICE) : (s->flags & ~FM1_MOD_SLOT_VOICE));
      return 1;
    case M_LOCK:
      if (!int_value(r, ev, 0, FM1_PARAM_UID_MAX, &v)) return 0;
      s->uid = (uint16_t)v;
      return 1;
    default:
      return bad(r, "unexpected member");
  }
}

static int ref_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  int64_t v;
  switch (r->member) {
    case M_SOURCE:
      if (ev->type != FM1_JSON_STR) return bad(r, "a source's name was expected");
      if (!gather(r, ev)) return 1;
      r->ref_has |= 1u;
      r->ref_source = (int16_t)(r->sbuf_over ? -1 : fm1_state_source_find(r->nm, r->sbuf, r->sbuf_n));
      if (r->ref_source < 0) { skipped(r, "not a source this build has"); r->cable_bad = 1; }
      return 1;
    case M_MODULE:
      if (!int_value(r, ev, 1, 8, &v)) return 0;
      r->ref_has |= 2u;
      r->ref_module = (uint16_t)(v - 1);
      return 1;
    case M_PORT:
      r->ref_has |= 4u;
      if (ev->type == FM1_JSON_NUM) {
        if (!int_value(r, ev, 1, 8, &v)) return 0;
        r->ref_port_idx = (uint16_t)v;
        r->ref_port[0] = '\0';
        return 1;
      }
      if (ev->type != FM1_JSON_STR) return bad(r, "a port's name or number was expected");
      if (!gather(r, ev)) return 1;
      if (r->sbuf_over || r->sbuf_n >= sizeof(r->ref_port)) { skipped(r, "not a port"); r->cable_bad = 1; return 1; }
      memcpy(r->ref_port, r->sbuf, r->sbuf_n + 1u);
      r->ref_port_idx = 0;
      return 1;
    default:
      return bad(r, "unexpected member");
  }
}

static int target_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  int64_t v;
  int c;
  switch (r->member) {
    case M_UNIT:
      if (ev->type != FM1_JSON_STR) return bad(r, "a unit's name was expected");
      if (!gather(r, ev)) return 1;
      c = r->sbuf_over ? -1 : unit_code(r->kind, r->sbuf, r->sbuf_n);
      if (c < 0) return bad(r, "not a unit of this kind of file");
      r->tgt_unit = (uint16_t)c;
      r->tgt_has |= 1u;
      return 1;
    case M_MODULE:
      if (!int_value(r, ev, 1, 8, &v)) return 0;
      r->tgt_module = (uint16_t)(v - 1);
      r->tgt_has |= 2u;
      return 1;
    case M_PARAM:
      if (ev->type != FM1_JSON_STR) return bad(r, "a parameter's name was expected");
      if (!gather(r, ev)) return 1;
      if (r->sbuf_over || r->sbuf_n >= sizeof(r->tgt_param) || r->sbuf_n > 24u || r->sbuf_n < 1u) {
        return bad(r, "a parameter's name has 1-24 printable ASCII characters");
      }
      {
        unsigned k;
        for (k = 0; k < r->sbuf_n; ++k) {
          if (r->sbuf[k] < 0x20 || r->sbuf[k] > 0x7E) return bad(r, "a parameter's name has 1-24 printable ASCII characters");
        }
      }
      memcpy(r->tgt_param, r->sbuf, r->sbuf_n + 1u);
      r->tgt_has |= 4u;
      return 1;
    case M_GATE:
      r->tgt_has |= 8u;
      if (ev->type == FM1_JSON_NUM) {
        if (!int_value(r, ev, 1, 8, &v)) return 0;
        r->tgt_gate_idx = (uint16_t)v;
        r->ref_port[0] = '\0';
        return 1;
      }
      if (ev->type != FM1_JSON_STR) return bad(r, "a gate's name or number was expected");
      if (!gather(r, ev)) return 1;
      if (r->sbuf_over || r->sbuf_n >= sizeof(r->ref_port)) { skipped(r, "not a gate"); r->cable_bad = 1; return 1; }
      memcpy(r->ref_port, r->sbuf, r->sbuf_n + 1u);
      r->tgt_gate_idx = 0;
      return 1;
    default:
      return bad(r, "unexpected member");
  }
}

static int view_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  int64_t v;
  int k;
  static const struct { uint8_t member, key; int8_t lo, hi; } kInts[] = {
    { M_VSOUND, FM1_VK_SOUND, 1, 4 }, { M_PAGE, FM1_VK_PAGE, 1, 16 },
    { M_TRACK, FM1_VK_TRACK, 1, 16 }, { M_BAR, FM1_VK_BAR, 1, 64 }, { M_VPOS, FM1_VK_POS, 1, 8 },
    { M_VSLOT, FM1_VK_SLOT, 1, 32 }, { M_ENTRY, FM1_VK_ENTRY, 1, 64 },
  };
  size_t i;
  if (r->member == M_MODE || r->member == M_PANEL || r->member == M_VUNIT) {
    if (ev->type != FM1_JSON_STR) return bad(r, "a name was expected");
    if (!gather(r, ev)) return 1;
    if (r->member == M_MODE) {
      k = sbuf_pick(r, kModes, FM1_VIEW_MODES);
      if (k < 0) return bad(r, "not a view mode");
      r->acc.u.view.mode = (uint8_t)k;
    } else if (r->member == M_PANEL) {
      k = sbuf_pick(r, kPanels, 4);
      if (k < 0) { skipped(r, "not a panel"); return 1; }
      r->acc.u.view.v[FM1_VK_PANEL] = (uint8_t)k;
      r->acc.u.view.has |= 1u << FM1_VK_PANEL;
    } else {
      k = r->sbuf_over ? -1 : unit_code(FM1_STATE_PROJECT, r->sbuf, r->sbuf_n);
      if (k < 0) { skipped(r, "not a unit"); return 1; }
      r->acc.u.view.v[FM1_VK_UNIT] = (uint8_t)k;
      r->acc.u.view.has |= 1u << FM1_VK_UNIT;
    }
    return 1;
  }
  for (i = 0; i < sizeof(kInts) / sizeof(kInts[0]); ++i) {
    if (kInts[i].member != r->member) continue;
    if (!int_value(r, ev, kInts[i].lo, kInts[i].hi, &v)) return 0;
    r->acc.u.view.v[kInts[i].key] = (uint8_t)v;
    r->acc.u.view.has |= (uint16_t)(1u << kInts[i].key);
    return 1;
  }
  return bad(r, "unexpected member");
}

static int object_value(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev) {
  fm1_rec_t rec;
  int64_t v;
  if (r->member == M_UNKNOWN) {
    if (ev->type == FM1_JSON_OBJ || ev->type == FM1_JSON_ARR) r->skip = (uint8_t)(ev->depth + 1u);
    return 1;
  }
  switch (f->ctx) {
    case C_DOC:
      return doc_value(r, ev);
    case C_MADE:
      r->text_key = r->member == M_BY ? FM1_INFO_BY : (r->member == M_VERSION ? FM1_INFO_VERSION : FM1_INFO_COMMIT);
      return text_piece(r, ev);
    case C_SESSION:
      switch (r->member) {
        case M_CURRENT:
          if (!int_value(r, ev, 1, 4, &v)) return 0;
          r->acc.u.session.current = (int8_t)(v - 1);
          return 1;
        case M_OCTAVE:
          if (!int_value(r, ev, -3, 3, &v)) return 0;
          r->acc.u.session.octave = (int8_t)v;
          return 1;
        case M_TRANSPOSE:
          if (!int_value(r, ev, -12, 12, &v)) return 0;
          r->acc.u.session.transpose = (int8_t)v;
          return 1;
        case M_KEY:
          if (!want_obj(r, ev)) return 0;
          r->acc_has = 0;
          return push(r, C_KEYOBJ, 0, 0, 0, 0, NULL);
        default:
          return bad(r, "unexpected member");
      }
    case C_KEYOBJ:
      if (ev->type != FM1_JSON_STR) return bad(r, "a name was expected");
      if (!gather(r, ev)) return 1;
      if (r->member == M_ROOT) {
        const int k = sbuf_pick(r, kRoots, 12);
        if (k < 0) { skipped(r, "not a key root"); return 1; }
        r->acc.u.session.root = (uint8_t)k;
        r->acc_has |= 1u;
      } else {
        size_t i;
        int ok = !r->sbuf_over && r->sbuf_n >= 1u && r->sbuf_n <= 24u && r->sbuf[0] >= 'a' && r->sbuf[0] <= 'z';
        for (i = 1; ok && i < r->sbuf_n; ++i) {
          const char c = r->sbuf[i];
          ok = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-';
        }
        if (!ok) { skipped(r, "not a scale id"); return 1; }
        memcpy(r->acc.u.session.scale, r->sbuf, r->sbuf_n + 1u);
        r->acc_has |= 2u;
      }
      return 1;
    case C_UNIT:
      return unit_value(r, f, ev);
    case C_PARAMS:
    case C_PAD:
    case C_MPARAMS:
      return param_value(r, f, ev);
    case C_DX7:
      switch (r->member) {
        case M_SLOT:
          if (!int_value(r, ev, 1, 32, &v)) return 0;
          r->acc.slot = (uint8_t)(v - 1);
          r->acc_has |= 1u;
          return 1;
        case M_VNAME: {
          size_t i;
          if (ev->type != FM1_JSON_STR) return bad(r, "a voice's name is text");
          if (!gather(r, ev)) return 1;
          for (i = 0; i < 10u; ++i) {
            char c = i < r->sbuf_n ? r->sbuf[i] : ' ';
            if (c < 0x20 || c > 0x7E) { c = ' '; ++r->rep->repaired; }
            r->acc.u.dx7.vced[145 + i] = (uint8_t)c;
          }
          if (r->sbuf_n > 10u || r->sbuf_over) ++r->rep->repaired;
          return 1;
        }
        case M_OPS:
          r->ops_n = 0;
          return want_arr(r, ev) && push(r, C_OPS, 0, 0, 0, 0, NULL);
        case M_GLOBALS:
          r->glob_n = 0;
          return want_arr(r, ev) && push(r, C_GLOBALS, 0, 0, 0, 0, NULL);
        default:
          return bad(r, "unexpected member");
      }
    case C_MOD:
      switch (r->member) {
        case M_SEED:
          if (!int_value(r, ev, 0, 4294967295LL, &v)) return 0;
          rec_init(&rec, FM1_REC_SEED);
          rec.u.seed = (uint32_t)v;
          f->flags |= 1u;
          return emit(r, &rec);
        case M_RACK:
          return want_arr(r, ev) && push(r, C_RACK, 0, 0, 0, 0, NULL);
        case M_CABLES:
          return want_arr(r, ev) && push(r, C_CABLES, 0, 0, 0, 0, NULL);
        default:
          return bad(r, "unexpected member");
      }
    case C_MODULE:
      switch (r->member) {
        case M_POS:
          if (!int_value(r, ev, 1, 8, &v)) return 0;
          if ((r->rack_pos >> (v - 1)) & 1u) return bad(r, "two modules at one rack position");
          r->rack_pos = (uint8_t)(r->rack_pos | (1u << (v - 1)));
          f->slot = (uint8_t)(v - 1);
          f->flags |= 1u;
          break;
        case M_MKIND:
          if (ev->type != FM1_JSON_STR) return bad(r, "kind is an id");
          if (!gather(r, ev)) return 1;
          if (r->sbuf_over || !is_id(r->sbuf, r->sbuf_n)) return bad(r, "kind is an id of a-z, 0-9 and -");
          f->owner = fm1_state_kind(r->nm, r->sbuf);
          if (!f->owner) unknown_engine(r, r->sbuf);
          memcpy(r->acc.u.unit.id, r->sbuf, r->sbuf_n + 1u);
          f->flags |= 2u;
          break;
        case M_PARAMS:
          return want_obj(r, ev) && push(r, C_MPARAMS, 0, FM1_ROLE_MODULE, 0, f->slot, f->owner);
        case M_DATA:
          return want_obj(r, ev) && push(r, C_MDATA, 0, FM1_ROLE_MODULE, 0, f->slot, NULL);
        default:
          return bad(r, "unexpected member");
      }
      if ((f->flags & 3u) == 3u && !(f->flags & 4u)) {
        f->flags |= 4u;
        r->rack_k[f->slot & 7u] = (const fm1_mod_kind_t *)f->owner;
        rec_init(&rec, FM1_REC_MODULE);
        rec.role = FM1_ROLE_MODULE;
        rec.slot = f->slot;
        memcpy(rec.u.unit.id, r->acc.u.unit.id, sizeof(rec.u.unit.id));
        ++r->rep->modules;
        return emit(r, &rec);
      }
      return 1;
    case C_MDATA:
      if (r->member == M_DVERSION) {
        if (!int_value(r, ev, 0, 255, &v)) return 0;
        f->flags = (uint8_t)v;
        return 1;
      }
      return hex_piece(r, f, ev);
    case C_CABLE:
      return cable_value(r, ev);
    case C_REF:
      return ref_value(r, ev);
    case C_TARGET:
      return target_value(r, ev);
    case C_VIEW:
      return view_value(r, ev);
    case C_SETTINGS: {
      uint8_t b;
      rec_init(&rec, FM1_REC_SETTING);
      switch (r->member) {
        case M_METRONOME: rec.u.setting.key = FM1_SET_METRONOME; break;
        case M_COUNT_IN_CLICK: rec.u.setting.key = FM1_SET_COUNT_IN_CLICK; break;
        case M_FULL_VELOCITY: rec.u.setting.key = FM1_SET_FULL_VELOCITY; break;
        default:
          rec.u.setting.key = FM1_SET_MIDI_IN_CHANNEL;
          if (!int_value(r, ev, 0, 16, &v)) return 0;
          rec.u.setting.value = (int32_t)v;
          return emit(r, &rec);
      }
      if (!bool_value(r, ev, &b)) return 0;
      rec.u.setting.is_bool = 1;
      rec.u.setting.value = b;
      return emit(r, &rec);
    }
    default:
      return bad(r, "unexpected value");
  }
}

/* ---- Items of arrays --------------------------------------------------------------- */
static int unit_item(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev, unsigned index,
                     unsigned role, unsigned sound, unsigned slot) {
  fm1_rec_t rec;
  if (ev->type == FM1_JSON_OBJ) return push(r, C_UNIT, index, role, sound, slot, NULL);
  if (ev->type != FM1_JSON_NULL) return bad(r, "a unit (an object) or null was expected");
  if (role == FM1_ROLE_SOUND && slot == 0 && sound == 0 && r->kind == FM1_STATE_PROJECT) {
    return bad(r, "Sound 1 is never empty");
  }
  rec_init(&rec, FM1_REC_UNIT);
  rec.role = (uint8_t)role;
  rec.sound = (uint8_t)sound;
  rec.slot = (uint8_t)slot;
  return emit(r, &rec);
}

static int array_item(fm1_state_json_reader_t *r, fm1_state_frame_t *f, const fm1_json_ev_t *ev,
                      unsigned index) {
  int64_t v;
  switch (f->ctx) {
    case C_SOUNDS:
      if (index >= 4u) return bad(r, "a project has four sound units");
      return unit_item(r, ev, index, FM1_ROLE_SOUND, index, 0);
    case C_INSERTS:
      if (index >= 2u) return bad(r, "a sound has two inserts");
      return unit_item(r, ev, index, FM1_ROLE_INSERT, f->sound, index);
    case C_MFXS:
      if (index >= FM1_STATE_MFX) return bad(r, "a sound has at most four MIDI effects");
      return unit_item(r, ev, index, FM1_ROLE_MFX, f->sound, index);
    case C_MASTER:
      if (index >= 2u) return bad(r, "a project has two master slots");
      return unit_item(r, ev, index, FM1_ROLE_MASTER, 0, index);
    case C_CHAIN:
      if (index >= FM1_STATE_CHAIN) return bad(r, "a chain has at most four effects");
      return unit_item(r, ev, index, FM1_ROLE_MASTER, 0, index);
    case C_PADS: {
      const fm1_engine_t *e = (const fm1_engine_t *)f->owner;
      if (index >= FM1_STATE_PADS || (e && index >= e->pad_count)) return bad(r, "more pads than the kit has");
      if (!want_obj(r, ev)) return 0;
      return push(r, C_PAD, index, f->role, f->sound, f->slot, f->owner);
    }
    case C_DX7S:
      if (index >= 32u) return bad(r, "at most 32 FM6 voices");
      if (!want_obj(r, ev)) return 0;
      rec_init(&r->acc, FM1_REC_DX7);
      memset(r->acc.u.dx7.vced + 145, ' ', 10);
      r->acc_has = 0;
      return push(r, C_DX7, index, 0, 0, 0, NULL);
    case C_OPS:
      if (index >= 6u) return bad(r, "a voice has six operators");
      if (!want_arr(r, ev)) return 0;
      return push(r, C_OP, index, 0, 0, index, NULL);
    case C_OP:
      if (index >= 21u) return bad(r, "an operator has 21 values");
      if (!int_value(r, ev, 0, kOpMax[index], &v)) return 0;
      r->acc.u.dx7.vced[f->slot * 21u + index] = (uint8_t)v;
      ++r->ops_n;
      return 1;
    case C_GLOBALS:
      if (index >= 19u) return bad(r, "a voice has 19 global values");
      if (!int_value(r, ev, 0, kGlobMax[index], &v)) return 0;
      r->acc.u.dx7.vced[126u + index] = (uint8_t)v;
      ++r->glob_n;
      return 1;
    case C_RACK:
      if (index >= 8u) return bad(r, "a rack has eight positions");
      if (!want_obj(r, ev)) return 0;
      rec_init(&r->acc, FM1_REC_MODULE);
      return push(r, C_MODULE, index, FM1_ROLE_MODULE, 0, 0, NULL);
    case C_CABLES:
      if (index >= 32u) return bad(r, "a matrix has 32 slots");
      if (!want_obj(r, ev)) return 0;
      rec_init(&r->acc, FM1_REC_CABLE);
      r->acc.u.cable.s.flags = FM1_MOD_SLOT_ON;
      r->acc.u.cable.s.via = FM1_MOD_NONE;
      r->acc_has = 0;
      r->cable_bad = 0;
      return push(r, C_CABLE, index, 0, 0, 0, NULL);
    default:
      return bad(r, "unexpected item");
  }
}

static int on_value(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  fm1_state_frame_t *f;
  if (r->depth == 0) {
    if (ev->type != FM1_JSON_OBJ) return refuse(r, FM1_STATE_NOT_LUNAR, "not a JSON object");
    return push(r, C_DOC, 0, 0, 0, 0, NULL);
  }
  f = top(r);
  if (is_array_ctx(f->ctx)) {
    unsigned index = f->items ? f->items - 1u : 0u;
    if (ev->type != FM1_JSON_STR || ev->first) {
      index = f->items;
      if (f->items < 255u) ++f->items;
    }
    if (f->ctx == C_LINES) return line_piece(r, f, ev);
    return array_item(r, f, ev, index);
  }
  return object_value(r, f, ev);
}

/* ---- The ends of containers ----------------------------------------------------------- */
static int ref_end(fm1_state_json_reader_t *r) {
  fm1_mod_slot_t *s = &r->acc.u.cable.s;
  unsigned code = FM1_MOD_NONE;
  if (r->ref_has == 1u) {
    if (r->ref_source >= 0) code = (unsigned)r->ref_source;
  } else if ((r->ref_has & 3u) == 2u) {
    const fm1_mod_kind_t *k = r->rack_k[r->ref_module & 7u];
    int port = 0;
    if (r->ref_has & 4u) {
      if (r->ref_port_idx) port = r->ref_port_idx - 1;
      else port = k ? fm1_state_port_find(k->out, k->n_out, r->ref_port, strlen(r->ref_port)) : -1;
    }
    if (port < 0 || port > 7) {
      skipped(r, "not an output of that module");
      r->cable_bad = 1;
    } else {
      code = FM1_MOD_SRC_MODULE + 8u * r->ref_module + (unsigned)port;
    }
  } else {
    return bad(r, "a cable's end is a source, or a module and its port");
  }
  if (r->ref_which == 0) s->src = (uint8_t)code;
  else s->via = (uint8_t)code;
  return 1;
}

static int target_end(fm1_state_json_reader_t *r) {
  fm1_mod_slot_t *s = &r->acc.u.cable.s;
  const char *pn = r->tgt_param;
  const size_t pl = strlen(pn);
  int i;
  r->acc.u.cable.name[0] = '\0';
  if (r->tgt_has == (1u | 4u)) {              /* a unit's parameter */
    const fm1_param_t *table = NULL;
    unsigned n = 0;
    const char *owner = NULL;
    s->dst_unit = (uint8_t)r->tgt_unit;
    if (r->tgt_unit == FM1_MOD_HOST) {
      table = r->nm ? r->nm->host : NULL;
      n = r->nm ? r->nm->n_host : 0u;
    } else {
      const int ix = code_index(r->tgt_unit);
      const fm1_engine_t *e = ix >= 0 ? r->unit_e[ix] : NULL;
      if (e) { table = e->params; n = e->n_params; owner = e->id; }
    }
    i = table ? fm1_state_param_find(r->nm, owner, table, n, pn, pl) : -1;
    if (i >= 0) {
      s->dst = table[i].uid;
    } else if (pl >= 2 && pn[0] == '#' && pn[1] != '0' && pl <= 5) {
      unsigned uid = 0;
      size_t k;
      for (k = 1; k < pl && pn[k] >= '0' && pn[k] <= '9'; ++k) uid = uid * 10u + (unsigned)(pn[k] - '0');
      if (k != pl || !uid || uid > FM1_PARAM_UID_MAX) return bad(r, "not a #UID");
      s->dst = (uint16_t)uid;
    } else if (table) {
      skipped(r, r->tgt_unit == FM1_MOD_HOST ? "not a host parameter" : "not a parameter of that unit");
      r->cable_bad = 1;
    } else {
      /* Kept by name: the unit's engine is not in this file or not in this
       * build (a mod rack names a project's units); the applier resolves it. */
      s->dst = 0;
      memcpy(r->acc.u.cable.name, pn, pl + 1u);
    }
    return 1;
  }
  if (r->tgt_has == (2u | 4u)) {              /* a module's parameter */
    const fm1_mod_kind_t *k = r->rack_k[r->tgt_module & 7u];
    s->dst_unit = (uint8_t)(FM1_MOD_MODULE + r->tgt_module);
    i = k ? fm1_state_param_find(r->nm, k->id, k->params, k->n_params, pn, pl) : -1;
    if (i >= 0) {
      s->dst = k->params[i].uid;
    } else if (k) {
      skipped(r, "not a parameter of that module");
      r->cable_bad = 1;
    } else {
      s->dst = 0;
      memcpy(r->acc.u.cable.name, pn, pl + 1u);
    }
    return 1;
  }
  if (r->tgt_has == (2u | 8u)) {              /* a module's gate input */
    const fm1_mod_kind_t *k = r->rack_k[r->tgt_module & 7u];
    int g;
    s->dst_unit = (uint8_t)(FM1_MOD_MODULE + r->tgt_module);
    s->flags |= FM1_MOD_SLOT_GATE_DST;
    if (r->tgt_gate_idx) g = r->tgt_gate_idx - 1;
    else g = k ? fm1_state_port_find(k->gate_in, k->n_gate_in, r->ref_port, strlen(r->ref_port)) : -1;
    if (g < 0) {
      skipped(r, "not a gate of that module");
      r->cable_bad = 1;
    } else {
      s->dst = (uint16_t)g;
    }
    return 1;
  }
  return bad(r, "a cable goes to a unit's parameter, or a module's parameter or gate");
}

static int on_close(fm1_state_json_reader_t *r, const fm1_json_ev_t *ev) {
  fm1_state_frame_t *f;
  fm1_rec_t rec;
  if (r->depth == 0) return bad(r, "unexpected end");
  f = top(r);
  switch (f->ctx) {
    case C_SESSION:
      if (!emit(r, &r->acc)) return 0;
      break;
    case C_KEYOBJ:
      if (r->acc_has == 3u) r->acc.u.session.has_key = 1;
      else if (r->acc_has) skipped(r, "a key needs its root and its scale");
      break;
    case C_UNIT:
      if (!(f->seen & 1u)) return bad(r, "a unit needs its engine");
      break;
    case C_DX7:
      if ((r->acc_has & 1u) == 0 || r->ops_n != 126u || r->glob_n != 19u) {
        return bad(r, "a voice needs its slot, six operators and 19 globals");
      }
      if ((r->dx7_slots >> r->acc.slot) & 1u) return bad(r, "two voices in one FM6 slot");
      r->dx7_slots |= 1u << r->acc.slot;
      ++r->rep->voices;
      if (!emit(r, &r->acc)) return 0;
      break;
    case C_OP:
      if (f->items != 21u) return bad(r, "an operator has 21 values");
      break;
    case C_OPS:
      if (f->items != 6u) return bad(r, "a voice has six operators");
      break;
    case C_GLOBALS:
      if (f->items != 19u) return bad(r, "a voice has 19 global values");
      break;
    case C_MODULE:
      if ((f->flags & 3u) != 3u) return bad(r, "a module needs its pos and kind");
      break;
    case C_MDATA:
      if (!(f->seen & 2u) || !(f->seen >> 63)) return bad(r, "pattern data needs its version and hex");
      break;
    case C_MOD:
      if (!(f->flags & 1u) && (r->kind == FM1_STATE_PROJECT || r->kind == FM1_STATE_MODS)) {
        return bad(r, "a project's or a mod rack's mod needs its seed");
      }
      break;
    case C_REF:
      if (!ref_end(r)) return 0;
      break;
    case C_TARGET:
      if (!target_end(r)) return 0;
      break;
    case C_CABLE:
      if ((r->acc_has & 15u) != 15u) return bad(r, "a cable needs its slot, from, to and amount");
      if (r->cable_bad) break;
      ++r->rep->cables;
      if (!emit(r, &r->acc)) return 0;
      break;
    case C_VIEW:
      if (r->acc.u.view.mode == 0xFF) return bad(r, "a view needs its mode");
      if (!emit(r, &r->acc)) return 0;
      break;
    case C_LINES:
      if (f->slot == FM1_LINES_SET && r->lines == 0) return bad(r, "a set opens with movy1");
      if (f->slot == FM1_LINES_CLIP && r->lines < 2u) return bad(r, "a clip has its cl and cp lines");
      break;
    default:
      break;
  }
  (void)rec;
  --r->depth;
  unknown_pop(r, ev->depth);
  return 1;
}

/* ---- The tokenizer's callback -------------------------------------------------------------- */
static int on_event(void *ctx, const fm1_json_ev_t *ev) {
  fm1_state_json_reader_t *r = (fm1_state_json_reader_t *)ctx;
  if (r->stop) return 0;
  if (r->skip) {
    if (ev->type == FM1_JSON_KEY) return unknown_key(r, ev->s, ev->n, ev->depth);
    if (ev->type == FM1_JSON_OBJ_END || ev->type == FM1_JSON_ARR_END) {
      unknown_pop(r, ev->depth);
      if (ev->depth + 1u == r->skip) r->skip = 0;
    }
    return 1;
  }
  switch (ev->type) {
    case FM1_JSON_KEY: return on_key(r, ev);
    case FM1_JSON_OBJ_END:
    case FM1_JSON_ARR_END: return on_close(r, ev);
    default: return on_value(r, ev);
  }
}

static int tok_fail(fm1_state_json_reader_t *r) {
  if (!r->stop) {
    const unsigned e = r->tok.err;
    r->stop = 1;
    r->rep->code = e == FM1_JSON_EBIG ? FM1_STATE_TOO_BIG : FM1_STATE_BAD;
    set_what(r->rep, e == FM1_JSON_EBIG ? "a JSON cap: depth 8, keys 64 B, numbers 32, strings 16 KiB, "
                                          "64 members, 8,192 items"
                     : e == FM1_JSON_EUTF8 ? "bad UTF-8, a surrogate half, U+0000 or a byte-order mark"
                                           : "not well-formed JSON");
    if (!r->top && e != FM1_JSON_EBIG && r->tok.offset == 0) r->rep->code = FM1_STATE_NOT_LUNAR;
    build_path(r, 0);
    r->rep->line = r->tok.line;
    r->rep->col = r->tok.col;
    r->rep->offset = r->tok.offset;
    r->rep->near_at = r->tok.offset ? r->tok.offset - 1u : 0u;
  }
  return 0;
}

int fm1_state_json_begin(fm1_state_json_reader_t *r, const fm1_state_names_t *nm,
                         fm1_rec_sink_t sink, void *sctx, fm1_state_report_t *rep) {
  memset(r, 0, sizeof(*r));
  fm1_json_init(&r->tok, on_event, r);
  r->nm = nm;
  r->sink = sink;
  r->sctx = sctx;
  r->rep = rep;
  return 1;
}

int fm1_state_json_feed(fm1_state_json_reader_t *r, const uint8_t *b, size_t n) {
  if (r->stop) return 0;
  if (!fm1_json_feed(&r->tok, b, n)) return r->stop ? 0 : tok_fail(r);
  return 1;
}

int fm1_state_json_end(fm1_state_json_reader_t *r) {
  fm1_rec_t rec;
  if (r->stop) return 0;
  if (!fm1_json_end(&r->tok)) {
    if (r->stop) return 0;
    if (r->top < 2 && r->tok.depth == 0 && !r->tok.done && r->frame[0].ctx == C_NONE) {
      return refuse(r, FM1_STATE_NOT_LUNAR, "an empty file, or no JSON object");
    }
    return tok_fail(r);
  }
  if (r->top < 2) return refuse(r, FM1_STATE_NOT_LUNAR, "a Lunar Modulator file opens with lunar and kind");
  {
    const uint64_t s = r->frame[0].seen;   /* frames are popped; seen bits stay */
    unsigned need = 0, i;
    switch (r->kind) {
      case FM1_STATE_PROJECT: need = M_SOUNDS; break;
      case FM1_STATE_SOUND: need = M_SOUND; break;
      case FM1_STATE_FX: need = M_CHAIN; break;
      case FM1_STATE_MODS: need = M_MOD; break;
      case FM1_STATE_CLIP: need = M_CLIP; break;
      case FM1_STATE_SETTINGS: need = M_SETTINGS; break;
      default: break;
    }
    for (i = 0; kDoc[i] && kDoc[i] != need; ++i) {}
    if (need && !((s >> i) & 1u)) {
      r->depth = 0;
      r->keylen = 0;
      return bad(r, "a member this kind of file needs is missing");
    }
  }
  rec_init(&rec, FM1_REC_END);
  return emit(r, &rec);
}

typedef struct {
  fm1_src_read_t rd;
  void *ctx;
} src_t;

int fm1_state_json_read(const fm1_state_names_t *nm, fm1_src_read_t rd, void *rctx,
                        fm1_rec_sink_t sink, void *sctx, fm1_state_report_t *rep) {
  fm1_state_json_reader_t r;
  uint8_t buf[256];
  uint32_t off = 0, got;
  int ok = 1;
  fm1_state_json_begin(&r, nm, sink, sctx, rep);
  while (ok && (got = rd(rctx, off, buf, sizeof(buf))) > 0) {
    if (off + got > fm1_state_kind_cap[FM1_STATE_PROJECT]) {
      refuse(&r, FM1_STATE_TOO_BIG, "larger than any file kind's cap");
      ok = 0;
      break;
    }
    ok = fm1_state_json_feed(&r, buf, got);
    off += got;
    if (ok && r.kind && off > fm1_state_kind_cap[r.kind]) {
      refuse(&r, FM1_STATE_TOO_BIG, "larger than this kind's cap");
      ok = 0;
    }
  }
  if (ok) ok = fm1_state_json_end(&r);
  if (!ok) {
    /* The first 40 characters there, for the report. */
    uint8_t near[40];
    const uint32_t at = rep->near_at;
    const uint32_t n = rd(rctx, at, near, sizeof(near));
    uint32_t i, k = 0;
    for (i = 0; i < n && k < 40u; ++i) {
      const uint8_t c = near[i];
      rep->near[k++] = (char)(c >= 0x20 && c < 0x7F ? c : (c == '\n' || c == '\t' ? ' ' : '?'));
    }
    rep->near[k] = '\0';
  }
  return ok;
}
