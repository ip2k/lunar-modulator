/* seq_cmd.c -- Movy's `cmd` verbs: the text parser and the dispatcher.
 *
 * Derived from Movy's seq-core command.rs (commit 9190e79, MIT, Copyright (c)
 * 2026 megadake). Arguments are parsed as command.rs parses them: each token
 * as an i64 (an optional sign, digits only, no overflow), a token that does
 * not parse counting as absent; then clamped or cast exactly as Movy does,
 * `as u16`/`as i32` truncations included.
 *
 * FM-1 additions: `route <track> <0 midi|1 engine> <channel|slot>`. Movy
 * ignores verbs it does not know, so scripts with it still run there.
 * Not implemented here (stage M4): the undo ring (`usnap`, `uswap`,
 * `ucommit`, `udrop`, `uclr` are accepted and do nothing) and Move's inject
 * capability (`minject` is stored only).
 */
#include "seq_int.h"

typedef struct {
  const char *name;
  uint16_t verb;
} verb_name_t;

static const verb_name_t kVerbs[] = {
  { "play", FM1_SEQ_V_PLAY }, { "stop", FM1_SEQ_V_STOP }, { "link", FM1_SEQ_V_LINK },
  { "minject", FM1_SEQ_V_MINJECT }, { "bpm", FM1_SEQ_V_BPM }, { "swing", FM1_SEQ_V_SWING },
  { "watch", FM1_SEQ_V_WATCH }, { "wlane", FM1_SEQ_V_WLANE }, { "tdrum", FM1_SEQ_V_TDRUM },
  { "mute", FM1_SEQ_V_MUTE }, { "pmute", FM1_SEQ_V_PMUTE }, { "psolo", FM1_SEQ_V_PSOLO },
  { "tog", FM1_SEQ_V_TOG }, { "evel", FM1_SEQ_V_EVEL }, { "elen", FM1_SEQ_V_ELEN },
  { "enudge", FM1_SEQ_V_ENUDGE }, { "etrn", FM1_SEQ_V_ETRN }, { "hold", FM1_SEQ_V_HOLD },
  { "slen", FM1_SEQ_V_SLEN }, { "clen", FM1_SEQ_V_CLEN }, { "cscl", FM1_SEQ_V_CSCL },
  { "ctr", FM1_SEQ_V_CTR }, { "eprob", FM1_SEQ_V_EPROB }, { "econd", FM1_SEQ_V_ECOND },
  { "einv", FM1_SEQ_V_EINV }, { "rec", FM1_SEQ_V_REC }, { "cap", FM1_SEQ_V_CAP },
  { "capclr", FM1_SEQ_V_CAPCLR }, { "capsel", FM1_SEQ_V_CAPSEL },
  { "capdone", FM1_SEQ_V_CAPDONE }, { "metro", FM1_SEQ_V_METRO }, { "cq", FM1_SEQ_V_CQ },
  { "dq", FM1_SEQ_V_DQ }, { "non", FM1_SEQ_V_NON }, { "nof", FM1_SEQ_V_NOF },
  { "del", FM1_SEQ_V_DEL }, { "clipdup", FM1_SEQ_V_CLIPDUP }, { "clipdel", FM1_SEQ_V_CLIPDEL },
  { "clipsel", FM1_SEQ_V_CLIPSEL }, { "launch", FM1_SEQ_V_LAUNCH }, { "song", FM1_SEQ_V_SONG },
  { "songadd", FM1_SEQ_V_SONGADD }, { "stoptrk", FM1_SEQ_V_STOPTRK },
  { "clipcopy", FM1_SEQ_V_CLIPCOPY }, { "clippaste", FM1_SEQ_V_CLIPPASTE },
  { "clipdelat", FM1_SEQ_V_CLIPDELAT }, { "cpy", FM1_SEQ_V_CPY }, { "pst", FM1_SEQ_V_PST },
  { "cpyclr", FM1_SEQ_V_CPYCLR }, { "addp", FM1_SEQ_V_ADDP }, { "loop", FM1_SEQ_V_LOOP },
  { "dbl", FM1_SEQ_V_DBL }, { "ltog", FM1_SEQ_V_LTOG }, { "alabel", FM1_SEQ_V_ALABEL },
  { "abase", FM1_SEQ_V_ABASE }, { "abaseq", FM1_SEQ_V_ABASEQ }, { "aset", FM1_SEQ_V_ASET },
  { "aclr", FM1_SEQ_V_ACLR }, { "aclrs", FM1_SEQ_V_ACLRS }, { "aclrstep", FM1_SEQ_V_ACLRSTEP },
  { "asetr", FM1_SEQ_V_ASETR }, { "usnap", FM1_SEQ_V_USNAP }, { "uswap", FM1_SEQ_V_USWAP },
  { "ucommit", FM1_SEQ_V_UCOMMIT }, { "udrop", FM1_SEQ_V_UDROP }, { "uclr", FM1_SEQ_V_UCLR },
  { "route", FM1_SEQ_V_ROUTE },
};

/* Rust's char::is_whitespace, over ASCII. */
static int is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\v' || c == '\f' || c == '\r';
}

/* `str::parse::<i64>()`: optional sign, at least one digit, nothing else. */
static int parse_i64(const char *p, size_t n, int64_t *out) {
  size_t i = 0;
  int neg = 0;
  uint64_t v = 0;
  const uint64_t lim_pos = 9223372036854775807ull;
  if (n == 0) return 0;
  if (p[0] == '+' || p[0] == '-') {
    neg = p[0] == '-';
    i = 1;
    if (n == 1) return 0;
  }
  for (; i < n; ++i) {
    const unsigned d = (unsigned)(p[i] - '0');
    if (d > 9) return 0;
    if (v > (lim_pos + (uint64_t)neg - d) / 10u) return 0;
    v = v * 10u + d;
  }
  if (neg) {
    *out = v == lim_pos + 1u ? (int64_t)(-9223372036854775807ll - 1) : -(int64_t)v;
  } else {
    *out = (int64_t)v;
  }
  return 1;
}

int fm1_seq_parse(const char *op, size_t len, fm1_seq_cmd_t *c) {
  size_t i = 0, k, start;
  int tok = -1;
  memset(c, 0, sizeof(*c));
  while (i < len) {
    while (i < len && is_ws(op[i])) ++i;
    if (i >= len) break;
    start = i;
    while (i < len && !is_ws(op[i])) ++i;
    if (tok < 0) {
      c->verb = FM1_SEQ_V_UNKNOWN;
      for (k = 0; k < sizeof(kVerbs) / sizeof(kVerbs[0]); ++k) {
        if (strlen(kVerbs[k].name) == i - start && memcmp(kVerbs[k].name, op + start, i - start) == 0) {
          c->verb = kVerbs[k].verb;
          break;
        }
      }
    } else if ((unsigned)tok < FM1_SEQ_CMD_ARGS) {
      if (parse_i64(op + start, i - start, &c->arg[tok])) c->valid |= 1u << tok;
      if (tok == 2) {
        const size_t m = i - start < FM1_SEQ_LABEL_MAX - 1u ? i - start : FM1_SEQ_LABEL_MAX - 1u;
        memcpy(c->text, op + start, m);
        c->text[m] = '\0';
      }
      c->argc = (uint8_t)(tok + 1);
    }
    ++tok;
  }
  return tok >= 0;
}

/* The `next()` closure of apply_op: one token at a time, absent if it did not
 * parse (the token is consumed either way). */
typedef struct {
  const fm1_seq_cmd_t *c;
  unsigned at;
} args_t;

static int next(args_t *a, int64_t *v) {
  const unsigned i = a->at;
  if (i >= a->c->argc) return 0;
  ++a->at;
  if (!(a->c->valid & (1u << i))) return 0;
  *v = a->c->arg[i];
  return 1;
}

static int64_t clamp64(int64_t v, int64_t lo, int64_t hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* `x as usize < NUM_TRACKS`: negative values become huge and fail. */
static int track_arg(const fm1_seq_t *s, int64_t v) { return v >= 0 && v < (int64_t)s->n_tracks; }

/* `x as usize`, as a bounded unsigned; huge values are kept huge. */
static unsigned as_index(int64_t v) {
  return v < 0 || v > 0x7FFFFFFF ? 0xFFFFFFFFu : (unsigned)v;
}

/* `d as i32`: the low 32 bits. */
static int32_t as_i32(int64_t v) {
  const uint32_t u = (uint32_t)(uint64_t)v;
  return u <= 0x7FFFFFFFu ? (int32_t)u : (int32_t)(u - 0x80000000u) - 0x7FFFFFFF - 1;
}

static int lane_arg(int64_t p) { return p >= 0 && p < 128 ? (int)p : -1; }

static uint8_t untranspose(const fm1_seq_t *s, unsigned t, uint8_t pitch) {
  const int32_t v = (int32_t)pitch - (t < s->n_tracks ? sq_active_transpose(s, t) : 0);
  return (uint8_t)(v < 0 ? 0 : (v > 127 ? 127 : v));
}

static unsigned active_clip(const fm1_seq_t *s, unsigned t) {
  return sq_clip_no(t, sq_ctracks(s)[t].active);
}

/* clears_capture (command.rs 81-101). */
static int clears_capture(uint16_t v) {
  switch (v) {
  case FM1_SEQ_V_REC: case FM1_SEQ_V_TOG: case FM1_SEQ_V_ADDP: case FM1_SEQ_V_DEL:
  case FM1_SEQ_V_EVEL: case FM1_SEQ_V_ELEN: case FM1_SEQ_V_ENUDGE: case FM1_SEQ_V_ETRN:
  case FM1_SEQ_V_SLEN: case FM1_SEQ_V_EPROB: case FM1_SEQ_V_ECOND: case FM1_SEQ_V_EINV:
  case FM1_SEQ_V_CLEN: case FM1_SEQ_V_CSCL: case FM1_SEQ_V_CTR: case FM1_SEQ_V_CQ:
  case FM1_SEQ_V_DBL: case FM1_SEQ_V_LOOP: case FM1_SEQ_V_LTOG: case FM1_SEQ_V_CPY:
  case FM1_SEQ_V_CPYCLR: case FM1_SEQ_V_PST: case FM1_SEQ_V_CLIPCOPY: case FM1_SEQ_V_CLIPDEL:
  case FM1_SEQ_V_CLIPDELAT: case FM1_SEQ_V_CLIPDUP: case FM1_SEQ_V_CLIPPASTE:
  case FM1_SEQ_V_CLIPSEL: case FM1_SEQ_V_LAUNCH: case FM1_SEQ_V_STOPTRK: case FM1_SEQ_V_SONG:
  case FM1_SEQ_V_SONGADD: case FM1_SEQ_V_ASET: case FM1_SEQ_V_ASETR: case FM1_SEQ_V_ACLR:
  case FM1_SEQ_V_ACLRS: case FM1_SEQ_V_ACLRSTEP:
    return 1;
  default:
    return 0;
  }
}

static int is_undo_verb(uint16_t v) {
  return v == FM1_SEQ_V_USNAP || v == FM1_SEQ_V_USWAP || v == FM1_SEQ_V_UCOMMIT ||
         v == FM1_SEQ_V_UDROP || v == FM1_SEQ_V_UCLR;
}

/* Lane automation (engine.rs 2293-2368). */
static void auto_set(fm1_seq_t *s, int64_t t, int64_t lane, uint16_t s0, uint16_t s1,
                     fm1_seq_val_t val, int audition, int range, sq_out_t *o) {
  if (!track_arg(s, t) || lane < 0 || lane >= 8) return;
  if (range) sq_clip_set_lock_range(s, active_clip(s, (unsigned)t), (uint8_t)lane, s0, s1, val);
  else sq_clip_set_lock(s, active_clip(s, (unsigned)t), (uint8_t)lane, s0, val);
  if (audition && (sq_tracks(s)[t].lanes_assigned & (1u << lane))) {
    sq_emit(o, FM1_SEQ_EV_LOCK, (uint8_t)t, (uint8_t)lane, val);
  }
}

static void apply_op(fm1_seq_t *s, const fm1_seq_cmd_t *c, sq_out_t *o) {
  args_t a;
  /* Set by next() whenever it returns 1; zeroed for GCC's flow analysis. */
  int64_t t = 0, x = 0, y = 0, z = 0, w = 0, v = 0;
  a.c = c;
  a.at = 0;
  if (clears_capture(c->verb)) sq_capture_clear(s);
  switch (c->verb) {
  case FM1_SEQ_V_PLAY:
    /* D12 (FM-1 default): Play while playing restarts at tick 0 (R10); Movy
     * keeps its clock session, so a MIDI clock follower stays a beat out of
     * phase. Close it with a Stop here; the block's Start reopens it. */
    if (!s->lim.compat && s->playing && s->emitting_clock &&
        sq_emit(o, FM1_SEQ_EV_STOP, SQ_NONE, 0, 0)) {
      s->emitting_clock = 0;
    }
    sq_play(s);
    break;
  case FM1_SEQ_V_STOP:
    sq_stop(s, o);
    break;
  case FM1_SEQ_V_LINK:
    if (next(&a, &v)) s->link_enabled = v != 0;
    break;
  case FM1_SEQ_V_MINJECT:
    if (next(&a, &v)) s->move_inject_ok = v != 0;
    break;
  case FM1_SEQ_V_BPM:
    if (next(&a, &v)) sq_set_bpm(s, (uint32_t)clamp64(v, 0, 0xFFFFFFFFll));
    break;
  case FM1_SEQ_V_SWING:
    if (next(&a, &v)) {
      s->swing_pct = (uint32_t)clamp64(v, 50, 80);
      sq_invalidate_all(s);
    }
    break;
  case FM1_SEQ_V_WATCH:
    if (next(&a, &t) && track_arg(s, t)) {
      s->watch_track = (uint8_t)t;
      sq_capture_clear(s);
    }
    break;
  case FM1_SEQ_V_WLANE:
    if (next(&a, &v)) s->watch_lane = (int16_t)lane_arg(v);
    break;
  case FM1_SEQ_V_TDRUM: {
    const int ht = next(&a, &t), hd = next(&a, &v);
    if (ht && hd && track_arg(s, t)) sq_tracks(s)[t].drum = v != 0;
    break;
  }
  case FM1_SEQ_V_MUTE: {
    const int ht = next(&a, &t), hm = next(&a, &v);
    if (ht && hm && track_arg(s, t)) {
      sq_tracks(s)[t].muted = v != 0;
      if (v != 0) sq_flush_track_gates(s, (unsigned)t, o);
    }
    break;
  }
  case FM1_SEQ_V_PMUTE: {
    const int ht = next(&a, &t), hp = next(&a, &x), hm = next(&a, &v);
    if (ht && hp && hm && track_arg(s, t) && x >= 0 && x < 128) {
      sq_set_pad_mute(s, (unsigned)t, (uint8_t)x, v != 0);
      sq_flush_silenced_pad_gates(s, (unsigned)t, o);
    }
    break;
  }
  case FM1_SEQ_V_PSOLO: {
    const int ht = next(&a, &t), hp = next(&a, &x);
    if (ht && hp && track_arg(s, t)) {
      sq_tracks(s)[t].pad_solo = x >= 0 && x < 128 ? (uint8_t)x : SQ_NONE;
      sq_flush_silenced_pad_gates(s, (unsigned)t, o);
    }
    break;
  }
  case FM1_SEQ_V_TOG: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    uint8_t chord[2 * FM1_SEQ_CHORD_MAX];
    unsigned n = 0;
    if (!(ht && hs)) break;
    for (;;) {
      const int hp = next(&a, &y), hv = next(&a, &z);
      if (!(hp && hv)) break;
      if (y >= 0 && y < 128 && n < FM1_SEQ_CHORD_MAX) {
        chord[2 * n] = untranspose(s, as_index(t), (uint8_t)y);
        chord[2 * n + 1] = (uint8_t)clamp64(z, 1, 127);
        ++n;
      }
    }
    if (track_arg(s, t)) {
      sq_clip_toggle_step(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255), chord, n);
      sq_ensure_selected_playing(s, (unsigned)t);
    }
    break;
  }
  case FM1_SEQ_V_EVEL: case FM1_SEQ_V_ELEN: case FM1_SEQ_V_ENUDGE: case FM1_SEQ_V_ETRN: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z),
              hd = next(&a, &w);
    static const int kWhat[] = { SQ_EDIT_VEL, SQ_EDIT_LENGTH, SQ_EDIT_NUDGE, SQ_EDIT_TRANSPOSE };
    if (ht && h0 && h1 && hp && hd && track_arg(s, t)) {
      sq_clip_edit(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                   (uint16_t)clamp64(y, 0, 255), lane_arg(z), kWhat[c->verb - FM1_SEQ_V_EVEL],
                   as_i32(w));
    }
    break;
  }
  case FM1_SEQ_V_HOLD: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs) {
      s->held_track = x < 0 ? -1 : (int32_t)as_index(t);
      s->held_step = x < 0 ? -1 : (int32_t)clamp64(x, 0, 255);
    }
    break;
  }
  case FM1_SEQ_V_SLEN: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z),
              hk = next(&a, &w);
    if (ht && h0 && h1 && hp && hk && track_arg(s, t)) {
      /* `tk.max(1) as u32`; the clip edit reads the low 32 bits back. */
      sq_clip_edit(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                   (uint16_t)clamp64(y, 0, 255), lane_arg(z), SQ_EDIT_SETLEN,
                   as_i32(w < 1 ? 1 : w));
    }
    break;
  }
  case FM1_SEQ_V_CLEN: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs && track_arg(s, t)) {
      sq_clip_set_length(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 65535));
    }
    break;
  }
  case FM1_SEQ_V_CSCL: {
    const int ht = next(&a, &t), hn = next(&a, &x), hd = next(&a, &y);
    if (ht && hn && hd && track_arg(s, t)) {
      sq_clip_t *cl = &sq_clips(s)[active_clip(s, (unsigned)t)];
      cl->scale_num = (uint8_t)clamp64(x, 1, 255);
      cl->scale_den = (uint8_t)clamp64(y, 1, 255);
      sq_scale_limit(s, &cl->scale_num, &cl->scale_den);     /* D8 */
      sq_clip_invalidate(s, active_clip(s, (unsigned)t));
    }
    break;
  }
  case FM1_SEQ_V_CTR: {
    const int ht = next(&a, &t), hv = next(&a, &v);
    if (ht && hv && track_arg(s, t)) {
      sq_clips(s)[active_clip(s, (unsigned)t)].transpose = (int8_t)clamp64(v, -36, 36);
    }
    break;
  }
  case FM1_SEQ_V_EPROB: case FM1_SEQ_V_EINV: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z),
              hv = next(&a, &v);
    if (ht && h0 && h1 && hp && hv && track_arg(s, t)) {
      const int lane = lane_arg(z);
      sq_clip_edit_trig(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                        (uint16_t)clamp64(y, 0, 255), lane < 0 ? SQ_NONE : (uint8_t)lane,
                        c->verb == FM1_SEQ_V_EPROB ? SQ_TRIG_PROB : SQ_TRIG_INV,
                        c->verb == FM1_SEQ_V_EPROB ? (uint8_t)clamp64(v, 0, 100) : (uint8_t)(v != 0),
                        0);
    }
    break;
  }
  case FM1_SEQ_V_ECOND: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z),
              ha = next(&a, &v), hb = next(&a, &w);
    if (ht && h0 && h1 && hp && ha && hb && track_arg(s, t)) {
      const int lane = lane_arg(z);
      sq_clip_edit_trig(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                        (uint16_t)clamp64(y, 0, 255), lane < 0 ? SQ_NONE : (uint8_t)lane,
                        SQ_TRIG_COND, (uint8_t)clamp64(v, 1, 64), (uint8_t)clamp64(w, 1, 64));
    }
    break;
  }
  case FM1_SEQ_V_REC:
    if (next(&a, &t)) sq_toggle_record(s, as_index(t));
    break;
  case FM1_SEQ_V_CAP:
    if (next(&a, &t) && track_arg(s, t)) sq_capture_commit(s, (unsigned)t);
    break;
  case FM1_SEQ_V_CAPCLR:
    sq_capture_clear(s);
    break;
  case FM1_SEQ_V_CAPSEL:
    if (next(&a, &v)) sq_capture_select(s, as_index(v < 0 ? 0 : v));
    break;
  case FM1_SEQ_V_CAPDONE:
    sq_capture_done(s);
    break;
  case FM1_SEQ_V_METRO:
    if (next(&a, &v)) s->metronome = v != 0;
    break;
  case FM1_SEQ_V_CQ: {
    const int ht = next(&a, &t), hv = next(&a, &v);
    if (ht && hv && track_arg(s, t)) {
      sq_clips(s)[active_clip(s, (unsigned)t)].quant = (uint8_t)clamp64(v, 0, 100);
      sq_clip_invalidate(s, active_clip(s, (unsigned)t));
    }
    break;
  }
  case FM1_SEQ_V_DQ:
    if (next(&a, &v)) s->default_quant = (uint8_t)clamp64(v, 0, 100);
    break;
  case FM1_SEQ_V_NON: {
    const int ht = next(&a, &t), hp = next(&a, &x), hv = next(&a, &v);
    if (ht && hp && hv && x >= 0 && x < 128) {
      sq_live_note_on(s, as_index(t), (uint8_t)x, (uint8_t)clamp64(v, 1, 127), s->frame_now);
    }
    break;
  }
  case FM1_SEQ_V_NOF: {
    const int ht = next(&a, &t), hp = next(&a, &x);
    if (ht && hp && x >= 0 && x < 128) sq_live_note_off(s, as_index(t), (uint8_t)x, s->frame_now);
    break;
  }
  case FM1_SEQ_V_DEL: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z);
    if (ht && h0 && h1 && hp) {
      sq_delete_range(s, as_index(t), (uint16_t)clamp64(x, 0, 255), (uint16_t)clamp64(y, 0, 255),
                      lane_arg(z), o);
    }
    break;
  }
  case FM1_SEQ_V_CLIPDUP:
    if (next(&a, &t)) sq_duplicate_clip(s, as_index(t));
    break;
  case FM1_SEQ_V_CLIPDEL:
    if (next(&a, &t) && track_arg(s, t)) sq_delete_clip_at(s, (unsigned)t, sq_tracks(s)[t].active, o);
    break;
  case FM1_SEQ_V_CLIPSEL: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs && track_arg(s, t) && x < (int64_t)FM1_SEQ_SLOTS) {
      sq_tracks(s)[t].active = (uint8_t)(x < 0 ? 0 : x);
    }
    break;
  }
  case FM1_SEQ_V_LAUNCH: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs) sq_launch_clip(s, as_index(t), as_index(x < 0 ? 0 : x));
    break;
  }
  case FM1_SEQ_V_SONG:
    if (next(&a, &x)) sq_song_start(s, as_index(x < 0 ? 0 : x));
    break;
  case FM1_SEQ_V_SONGADD:
    if (next(&a, &x)) sq_song_add(s, as_index(x < 0 ? 0 : x));
    break;
  case FM1_SEQ_V_STOPTRK:
    if (next(&a, &t)) sq_stop_track(s, as_index(t));
    break;
  case FM1_SEQ_V_CLIPCOPY: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs) sq_copy_clip(s, as_index(t), as_index(x < 0 ? 0 : x));
    break;
  }
  case FM1_SEQ_V_CLIPPASTE: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs) sq_paste_clip(s, as_index(t), as_index(x < 0 ? 0 : x), o);
    break;
  }
  case FM1_SEQ_V_CLIPDELAT: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs) sq_delete_clip_at(s, as_index(t), as_index(x < 0 ? 0 : x), o);
    break;
  }
  case FM1_SEQ_V_CPY: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y);
    if (ht && h0 && h1) {
      sq_copy_steps(s, as_index(t), (uint16_t)clamp64(x, 0, 255), (uint16_t)clamp64(y, 0, 255));
    }
    break;
  }
  case FM1_SEQ_V_PST: {
    const int ht = next(&a, &t), hd = next(&a, &x);
    if (ht && hd) sq_paste_steps(s, as_index(t), (uint16_t)clamp64(x, 0, 255));
    break;
  }
  case FM1_SEQ_V_CPYCLR:
    sq_clear_clipboard(s);
    break;
  case FM1_SEQ_V_ADDP: {
    const int ht = next(&a, &t), h0 = next(&a, &x), h1 = next(&a, &y), hp = next(&a, &z),
              hv = next(&a, &v);
    if (ht && h0 && h1 && hp && hv && track_arg(s, t) && z >= 0 && z < 128) {
      sq_clip_add_pitch_range(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                              (uint16_t)clamp64(y, 0, 255), untranspose(s, (unsigned)t, (uint8_t)z),
                              (uint8_t)clamp64(v, 1, 127), s->watch_lane < 0);
    }
    break;
  }
  case FM1_SEQ_V_LOOP: {
    const int ht = next(&a, &t), hs = next(&a, &x), hl = next(&a, &y);
    if (ht && hs && hl && track_arg(s, t) && x >= 0 && y > 0) {
      sq_clip_set_loop(s, active_clip(s, (unsigned)t), (uint16_t)(uint64_t)x, (uint16_t)(uint64_t)y);
    }
    break;
  }
  case FM1_SEQ_V_DBL:
    if (next(&a, &t) && track_arg(s, t)) sq_clip_double(s, active_clip(s, (unsigned)t));
    break;
  case FM1_SEQ_V_LTOG: {
    const int ht = next(&a, &t), hs = next(&a, &x), hp = next(&a, &y), hv = next(&a, &v);
    if (ht && hs && hp && hv && track_arg(s, t) && y >= 0 && y < 128) {
      sq_clip_toggle_pitch(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255),
                           untranspose(s, (unsigned)t, (uint8_t)y), (uint8_t)clamp64(v, 1, 127),
                           s->watch_lane < 0);
      sq_ensure_selected_playing(s, (unsigned)t);
    }
    break;
  }
  case FM1_SEQ_V_ALABEL: {
    const int ht = next(&a, &t), hl = next(&a, &x);
    if (ht && hl && track_arg(s, t) && x >= 0 && x < 8) {
      sq_track_t *tr = &sq_tracks(s)[t];
      tr->lanes_assigned |= (uint8_t)(1u << x);
      memcpy(tr->label[x], c->argc > 2 ? c->text : "", FM1_SEQ_LABEL_MAX);
      tr->label[x][FM1_SEQ_LABEL_MAX - 1] = '\0';
    }
    break;
  }
  case FM1_SEQ_V_ABASE: case FM1_SEQ_V_ABASEQ: {
    const int ht = next(&a, &t), hl = next(&a, &x), hv = next(&a, &v);
    if (ht && hl && hv && track_arg(s, t) && x >= 0 && x < 8) {
      sq_track_t *tr = &sq_tracks(s)[t];
      tr->base[x] = (fm1_seq_val_t)clamp64(v, 0, FM1_SEQ_VAL_MAX);
      if (c->verb == FM1_SEQ_V_ABASE && (tr->lanes_assigned & (1u << x))) {
        sq_emit(o, FM1_SEQ_EV_LOCK, (uint8_t)t, (uint8_t)x, tr->base[x]);
      }
    }
    break;
  }
  case FM1_SEQ_V_ASET: {
    const int ht = next(&a, &t), hl = next(&a, &x), hs = next(&a, &y), hv = next(&a, &v);
    int64_t q = 0;
    if (ht && hl && hs && hv) {
      if (!next(&a, &q)) q = 0;
      auto_set(s, t, x, (uint16_t)clamp64(y, 0, 255), 0, (fm1_seq_val_t)clamp64(v, 0, FM1_SEQ_VAL_MAX),
               q == 0, 0, o);
    }
    break;
  }
  case FM1_SEQ_V_ASETR: {
    const int ht = next(&a, &t), hl = next(&a, &x), h0 = next(&a, &y), h1 = next(&a, &z),
              hv = next(&a, &v);
    int64_t q = 0;
    if (ht && hl && h0 && h1 && hv) {
      if (!next(&a, &q)) q = 0;
      auto_set(s, t, x, (uint16_t)clamp64(y, 0, 255), (uint16_t)clamp64(z, 0, 255),
               (fm1_seq_val_t)clamp64(v, 0, FM1_SEQ_VAL_MAX), q == 0, 1, o);
    }
    break;
  }
  case FM1_SEQ_V_ACLR: {
    const int ht = next(&a, &t), hl = next(&a, &x);
    if (ht && hl && track_arg(s, t) && x >= 0 && x < 8) {
      unsigned k;
      for (k = 0; k < FM1_SEQ_SLOTS; ++k) sq_clip_clear_lane(s, sq_clip_no((unsigned)t, k), (uint8_t)x);
      if (s->lim.compat) {
        /* Movy (engine.rs 2342-2351) unassigns the lane but keeps its base
         * and carried value, which a relabelled lane then resumes from. */
        sq_tracks(s)[t].lanes_assigned &= (uint8_t)~(1u << x);
        sq_tracks(s)[t].label[x][0] = '\0';
      } else {
        sq_release_lane(s, (unsigned)t, (unsigned)x, o);   /* D13, and D6 */
      }
    }
    break;
  }
  case FM1_SEQ_V_ACLRS: {
    const int ht = next(&a, &t), hl = next(&a, &x), hs = next(&a, &y);
    if (ht && hl && hs && track_arg(s, t) && x >= 0 && x < 8) {
      sq_clip_clear_lock(s, active_clip(s, (unsigned)t), (uint8_t)x, (uint16_t)clamp64(y, 0, 255));
      sq_free_unused_lanes(s, (unsigned)t, o);
    }
    break;
  }
  case FM1_SEQ_V_ACLRSTEP: {
    const int ht = next(&a, &t), hs = next(&a, &x);
    if (ht && hs && track_arg(s, t)) {
      sq_clip_clear_step_locks(s, active_clip(s, (unsigned)t), (uint16_t)clamp64(x, 0, 255));
      sq_free_unused_lanes(s, (unsigned)t, o);
    }
    break;
  }
  case FM1_SEQ_V_ROUTE: {
    const int ht = next(&a, &t), hk = next(&a, &x), hi = next(&a, &y);
    if (ht && hk && hi && track_arg(s, t) && x >= 0 && x <= 1 && y >= 0 && y <= 16) {
      const sq_track_t *tr = &sq_tracks(s)[t];
      const uint8_t kind0 = tr->route_kind, index0 = tr->route_index;
      if (!fm1_seq_set_route(s, (uint8_t)t, (uint8_t)x, (uint8_t)y)) {
        ++s->stats.refused;
      } else if (tr->route_kind != kind0 || tr->route_index != index0) {
        /* Routed elsewhere: the track lets go of what it sounds now, where
         * it sounds it (the host sends these note-offs to the old route,
         * fm1_seq_host.h), so no note is left hanging there. */
        sq_flush_track_gates(s, (unsigned)t, o);
      }
    }
    break;
  }
  default:
    /* Unknown verbs, Move-only verbs and the undo ring: nothing (forward
     * compatible, as Movy). */
    break;
  }
}

uint32_t fm1_seq_apply(fm1_seq_t *s, const fm1_seq_cmd_t *c, fm1_seq_ev_t *out, uint32_t cap) {
  sq_out_t o;
  o.s = s;
  o.out = out;
  o.cap = out ? cap : 0;
  o.n = 0;
  o.tick = (uint32_t)s->master_tick;
  o.frame = 0;
  s->panicked = 0;
  apply_op(s, c, &o);
  /* A Movy panic unwinds out of apply_batch: no re-seed, no dirty flag. */
  if (s->panicked) return o.n;
  /* apply_batch: re-seed empty clips after every op; edits mark the set dirty. */
  sq_reseed_empty_clips(s);
  if (!is_undo_verb(c->verb)) s->dirty = 1;
  return o.n;
}

/* apply_batch (command.rs 22-53). */
uint32_t fm1_seq_apply_text(fm1_seq_t *s, const char *batch, size_t len, fm1_seq_ev_t *out,
                            uint32_t cap) {
  size_t i = 0, start;
  uint32_t n = 0;
  if (len > 0 && batch[0] == '#') {
    size_t semi = 1;
    int64_t seq;
    size_t a = 1, b;
    while (semi < len && batch[semi] != ';') ++semi;
    b = semi;
    while (a < b && is_ws(batch[a])) ++a;
    while (b > a && is_ws(batch[b - 1])) --b;
    if (b > a && parse_i64(batch + a, b - a, &seq) && seq >= 0 && seq <= 0xFFFFFFFFll &&
        batch[a] != '-') {
      if (s->has_cmd_seq && s->last_cmd_seq == (uint32_t)seq) return 0;
      s->has_cmd_seq = 1;
      s->last_cmd_seq = (uint32_t)seq;
      i = semi < len ? semi + 1 : len;
    }
  }
  while (i <= len) {
    size_t a, b;
    start = i;
    while (i < len && batch[i] != ';') ++i;
    a = start;
    b = i;
    while (a < b && is_ws(batch[a])) ++a;
    while (b > a && is_ws(batch[b - 1])) --b;
    if (b > a) {
      fm1_seq_cmd_t c;
      fm1_seq_parse(batch + a, b - a, &c);
      n += fm1_seq_apply(s, &c, out ? out + n : NULL, cap > n ? cap - n : 0);
      /* compat: movy-dsp's catch_unwind drops the rest of a panicked batch. */
      if (s->panicked) break;
    }
    ++i;
  }
  return n;
}
