/* seq_tool.c -- fm1-seq: runs the sequencer core alone, for tests.
 *
 *   fm1-seq --sizes
 *   fm1-seq [--cmd FILE] [--seq FILE.movy1] [--compat | --compat-frames] [--tracks N] [--rate HZ]
 *           [--block N] [--end FRAMES] [--log FILE.jsonl] [--state FILE.json]
 *           [--snap FRAME]... [--peek FRAME]... [--export FILE.movy1] [--fill BYTE] [--seed N]
 *           [--notes N] [--locks N] [--trigs N] [--gates N] [--capture N]
 *           [--song N] [--rec N] [--events N] [--import FRAME:FILE.movy1]...
 *
 * Plays a verb script (seq_script.h) through fm1_seq in blocks, writes the
 * event log, and dumps state as JSON at each --snap frame (the first block
 * boundary at or after it, once that boundary's commands are applied), each
 * --peek frame (the same boundary, before its commands) and at the end.
 * --events N gives each block (its commands and its advance together) an
 * event buffer of N, as a device's would be; the default is 65536.
 * --import FRAME:FILE imports a set mid-run, at the first block boundary at
 * or after FRAME, before that boundary's commands (an import emits no
 * event: the core releases nothing, as a host's import path must; tests of
 * what an import resets and reseeds use it).
 * --compat runs Movy's behaviour exactly; --compat-frames does too, but logs
 * each tick at its own frame (D1), as the Movy oracle's --frames tick does.
 * Without --cmd, nothing runs: --seq FILE --export OUT round-trips
 * a set. --sizes prints fm1_seq_size() for 1-16 tracks with the default
 * limits (Capture's 256 events included) and without Capture, and the item
 * sizes.
 *
 * Saved state (engines/state/, stage E3): --load FILE takes a project's set
 * or a binary set (it replaces the set), --load tT.S:FILE a clip into track
 * T, slot S (1-based; lanes matched by label, its old lines replaced),
 * after --seq; --save clip:T.S:FILE writes that slot's clip at the end, as
 * JSON or, for FILE.lunarb, binary. MIT licence.
 */
#define _POSIX_C_SOURCE 200112L   /* clock_gettime */

#include "fm1_seq.h"
#include "fm1_state.h"
#include "seq_script.h"
#include "state_clip.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void usage(void) {
  fputs("usage: fm1-seq --sizes\n"
        "       fm1-seq [--cmd FILE] [--seq FILE.movy1] [--compat | --compat-frames]\n"
        "               [--tracks N] [--rate HZ]\n"
        "               [--block N] [--end FRAMES] [--log FILE.jsonl] [--state FILE.json]\n"
        "               [--snap FRAME]... [--peek FRAME]... [--export FILE.movy1]\n"
        "               [--fill BYTE] [--seed N]\n"
        "               [--notes N] [--locks N] [--trigs N] [--gates N] [--capture N]\n"
        "               [--song N] [--rec N] [--events N] [--import FRAME:FILE.movy1]...\n"
        "               [--load [tT.S:]FILE]... [--save clip:T.S:FILE]...\n", stderr);
}

static void json_str(FILE *f, const char *s, size_t n) {
  size_t i;
  fputc('"', f);
  for (i = 0; i < n; ++i) {
    const unsigned char c = (unsigned char)s[i];
    if (c == '"' || c == '\\') fprintf(f, "\\%c", c);
    else if (c == '\n') fputs("\\n", f);
    else if (c < 0x20) fprintf(f, "\\u%04x", c);
    else fputc(c, f);
  }
  fputc('"', f);
}

static void json_slot(FILE *f, uint8_t v) {
  if (v == FM1_SEQ_NONE) fputs("null", f);
  else fprintf(f, "%u", (unsigned)v);
}

static void dump_state(FILE *f, const fm1_seq_t *s, const char *kind, const char *label,
                       uint64_t at, uint64_t frame, uint64_t block) {
  fm1_seq_info_t in;
  fm1_seq_stats_t st;
  unsigned t, k, lane, i;
  size_t need;
  char *text;
  fm1_seq_get_info(s, &in);
  fm1_seq_get_stats(s, &st);
  fprintf(f, "{\"kind\":\"%s\",\"at\":%llu,\"label\":", kind, (unsigned long long)at);
  json_str(f, label, strlen(label));
  fputc(',', f);
  fprintf(f, "\"frame\":%llu,\"block\":%llu,\"master_tick\":%llu,\"bpm_x100\":%lu,\"swing\":%u,"
          "\"playing\":%u,\"recording\":%u,\"counting_in\":%u,\"metronome\":%u,\"link\":%u,"
          "\"following\":%u,\"watch_track\":%u,\"rec_track\":%u,\"default_quant\":%u,"
          "\"song_pos\":%u,\"song\":[",
          (unsigned long long)frame, (unsigned long long)block, (unsigned long long)in.master_tick,
          (unsigned long)in.bpm_x100, in.swing_pct, in.playing, in.recording, in.counting_in,
          in.metronome, in.link, in.following, in.watch_track, in.rec_track, in.default_quant,
          in.song_pos);
  for (i = 0; i < in.song_len; ++i) fprintf(f, i ? ",%u" : "%u", in.song[i]);
  fprintf(f, "],\"song_entries\":%u,\"song_entry\":%u,\"song_armed\":%u,\"song_pass\":%u,"
          "\"song_pass_bar\":%u,\"song_end\":%u,\"song_jump\":",
          in.song_entries, in.song_entry, in.song_armed, in.song_pass, in.song_pass_bar,
          in.song_end);
  json_slot(f, in.song_jump);
  fprintf(f, ",\"song_follow\":%u,\"song_parked\":%u,\"song_bars\":%lu,\"scene_names\":[",
          in.song_follow, in.song_parked, (unsigned long)fm1_seq_song_bars(s));
  for (i = 0; i < FM1_SEQ_SCENES; ++i) {
    const char *name = fm1_seq_scene_name(s, (uint8_t)i);
    if (i) fputc(',', f);
    json_str(f, name, strlen(name));
  }
  fprintf(f, "],\"capture\":{\"gen\":%lu,\"pending\":%u,\"mode\":%u,\"sel\":%u,\"cands\":[",
          (unsigned long)in.capture_gen, in.capture_pending, in.capture_mode, in.capture_sel);
  for (i = 0; i < in.capture_n && i < 3; ++i) fprintf(f, i ? ",%u" : "%u", in.capture_cands[i]);
  fprintf(f, "]},\"stats\":{\"refused\":%lu,\"dropped_events\":%lu,\"gates_evicted\":%lu,"
          "\"movy_faults\":%lu,\"notes_used\":%u,\"locks_used\":%u,\"trigs_used\":%u},\"tracks\":[",
          (unsigned long)st.refused, (unsigned long)st.dropped_events,
          (unsigned long)st.gates_evicted, (unsigned long)st.movy_faults, st.notes_used,
          st.locks_used, st.trigs_used);
  for (t = 0; t < in.tracks; ++t) {
    fm1_seq_track_info_t ti;
    int first_clip = 1;
    fm1_seq_get_track(s, (uint8_t)t, &ti);
    fprintf(f, "%s{\"active\":%u,\"playing\":", t ? "," : "", ti.active);
    json_slot(f, ti.playing);
    fputs(",\"queued\":", f);
    json_slot(f, ti.queued);
    fputs(",\"pending_select\":", f);
    json_slot(f, ti.pending_select);
    fprintf(f, ",\"pending_stop\":%u,\"muted\":%u,\"drum\":%u,\"pad_solo\":", ti.pending_stop,
            ti.muted, ti.drum);
    json_slot(f, ti.pad_solo);
    fprintf(f, ",\"pos\":%u,\"cycle\":%lu,\"last_auto_step\":%d,\"route\":[%u,%u],\"lanes\":[",
            ti.pos_tick, (unsigned long)ti.cycle, ti.last_auto_step, ti.route_kind, ti.route_index);
    for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      const char *label = fm1_seq_lane_label(s, (uint8_t)t, (uint8_t)lane);
      fm1_seq_clip_info_t ac;
      fprintf(f, "%s{\"assigned\":%u,\"base\":%u,\"cur\":%d,\"label\":", lane ? "," : "",
              (ti.lanes_assigned >> lane) & 1u, ti.base[lane], ti.auto_cur[lane]);
      json_str(f, label, strlen(label));
      /* effective_at over the active clip's loop window, with the lane base */
      fputs(",\"eff\":[", f);
      fm1_seq_get_clip(s, (uint8_t)t, ti.active, &ac);
      for (i = 0; i < ac.length_steps; ++i) {
        fprintf(f, i ? ",%d" : "%d",
                fm1_seq_effective_at(s, (uint8_t)t, ti.active, (uint8_t)lane,
                                     (uint16_t)(ac.loop_start + i), ti.base[lane]));
      }
      fputs("]}", f);
    }
    fputs("],\"clips\":{", f);
    for (k = 0; k < FM1_SEQ_SLOTS; ++k) {
      fm1_seq_clip_info_t ci;
      fm1_seq_get_clip(s, (uint8_t)t, (uint8_t)k, &ci);
      if (!ci.length_steps && !ci.notes && !ci.locks && !ci.trigs) continue;
      fprintf(f, "%s\"%u\":{\"len\":%u,\"loop_start\":%u,\"scale\":[%u,%u],\"transpose\":%d,"
              "\"quant\":%u,\"locks\":%u,\"trigs\":%u,\"notes\":[",
              first_clip ? "" : ",", k, ci.length_steps, ci.loop_start, ci.scale_num, ci.scale_den,
              ci.transpose, ci.quant, ci.locks, ci.trigs);
      first_clip = 0;
      for (i = 0; i < ci.notes; ++i) {
        fm1_seq_note_info_t n;
        fm1_seq_get_note(s, (uint8_t)t, (uint8_t)k, (uint16_t)i, &n);
        fprintf(f, "%s[%u,%u,%u,%u,%u,%u,%u]", i ? "," : "", n.tick, n.gate, n.pitch, n.vel,
                n.step, n.suppress, n.fired);
      }
      /* fm1_seq_get_page over every step a note, lock or row can sit on:
       * [step, notes, lock mask, trig flags, prob, A, B, [8 lock values]]
       * for each step with anything on it (docs/15 §2.5). */
      fputs("],\"page\":[", f);
      {
        static fm1_seq_step_info_t pg[FM1_SEQ_MAX_STEPS + 1u];
        int first_step = 1;
        fm1_seq_get_page(s, (uint8_t)t, (uint8_t)k, 0, FM1_SEQ_MAX_STEPS + 1u, pg);
        for (i = 0; i <= FM1_SEQ_MAX_STEPS; ++i) {
          const fm1_seq_step_info_t *p = &pg[i];
          if (!p->notes && !p->lock_mask && !p->trig) continue;
          fprintf(f, "%s[%u,%u,%u,%u,%u,%u,%u,[%u,%u,%u,%u,%u,%u,%u,%u]]", first_step ? "" : ",", i,
                  p->notes, p->lock_mask, p->trig, p->prob, p->cond_a, p->cond_b, p->lock[0],
                  p->lock[1], p->lock[2], p->lock[3], p->lock[4], p->lock[5], p->lock[6],
                  p->lock[7]);
          first_step = 0;
        }
      }
      fputs("]}", f);
    }
    fputs("}}", f);
  }
  fputs("],\"movy1\":", f);
  need = fm1_seq_export_movy1(s, NULL, 0);
  text = (char *)malloc(need + 1u);
  if (text) {
    fm1_seq_export_movy1(s, text, need + 1u);
    json_str(f, text, need);
    free(text);
  } else {
    fputs("null", f);
  }
  fputc('}', f);
}

static void sizes(void) {
  unsigned t;
  fm1_seq_limits_t lim;
  printf("{\"tracks\":{");
  for (t = 1; t <= FM1_SEQ_MAX_TRACKS; ++t) {
    fm1_seq_limits_default(&lim, (uint8_t)t);
    printf("%s\"%u\":%lu", t > 1 ? "," : "", t, (unsigned long)fm1_seq_size(&lim));
  }
  printf("},\"no_capture\":{");
  for (t = 1; t <= FM1_SEQ_MAX_TRACKS; ++t) {
    fm1_seq_limits_default(&lim, (uint8_t)t);
    lim.capture = 0;
    printf("%s\"%u\":%lu", t > 1 ? "," : "", t, (unsigned long)fm1_seq_size(&lim));
  }
  fm1_seq_limits_default(&lim, 8);
  printf("},\"limits8\":{\"notes\":%u,\"locks\":%u,\"trigs\":%u,\"gates\":%u,\"song\":%u,"
         "\"rec_notes\":%u,\"pad_mutes\":%u,\"capture\":%u},\"cmd_bytes\":%lu,"
         "\"event_bytes\":%lu}\n",
         lim.notes, lim.locks, lim.trigs, lim.gates, lim.song, lim.rec_notes, lim.pad_mutes,
         lim.capture, (unsigned long)sizeof(fm1_seq_cmd_t), (unsigned long)sizeof(fm1_seq_ev_t));
}

static int cmp_u64(const void *a, const void *b) {
  const uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return x < y ? -1 : (x > y ? 1 : 0);
}

/* ---- Saved state: a file's movy1 lines, and a clip out ---------------------- */
typedef struct {
  char *set;                 /* the set's lines, joined */
  size_t set_n, set_cap;
  char **clip;               /* the clip's lines */
  size_t clip_n;
  int open;                  /* a line is being joined (pieces) */
} lines_t;

static void lines_add(char **buf, size_t *n, size_t *cap, const char *s, size_t m) {
  if (*n + m + 2 > *cap) {
    *cap = (*n + m + 2) * 2;
    *buf = (char *)realloc(*buf, *cap);
    if (!*buf) exit(3);
  }
  memcpy(*buf + *n, s, m);
  *n += m;
  (*buf)[*n] = '\0';
}

static int lines_sink(void *ctx, const fm1_rec_t *r) {
  lines_t *l = (lines_t *)ctx;
  if (r->type != FM1_REC_LINE) return 1;
  if (r->u.line.which == FM1_LINES_SET) {
    lines_add(&l->set, &l->set_n, &l->set_cap, r->u.line.s, r->u.line.n);
    if (r->piece & FM1_REC_LAST) lines_add(&l->set, &l->set_n, &l->set_cap, "\n", 1);
  } else {
    if (r->piece & FM1_REC_FIRST) {
      size_t z = 0, zc = 0;
      l->clip = (char **)realloc(l->clip, (l->clip_n + 1) * sizeof(char *));
      if (!l->clip) exit(3);
      l->clip[l->clip_n] = NULL;
      lines_add(&l->clip[l->clip_n], &z, &zc, "", 0);
      ++l->clip_n;
    }
    {
      char **c = &l->clip[l->clip_n - 1];
      size_t n = strlen(*c), cap = n + 1;
      lines_add(c, &n, &cap, r->u.line.s, r->u.line.n);
    }
  }
  return 1;
}

static uint32_t buf_read(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const size_t *len = (const size_t *)ctx;
  const uint8_t *b = (const uint8_t *)(len + 1);
  if (off >= *len) return 0;
  if (n > *len - off) n = (uint32_t)(*len - off);
  memcpy(out, b + off, n);
  return n;
}

typedef struct {
  char *b;
  size_t n, cap;
} out_t;

static void out_put(void *ctx, const char *s, size_t n) {
  out_t *o = (out_t *)ctx;
  lines_add(&o->b, &o->n, &o->cap, s, n);
}

/* --load [tT.S:]FILE into the core. */
static int state_load(fm1_seq_t *s, const char *spec) {
  int t = 0, sl = 0, at = 0;
  const char *path = spec;
  size_t len = 0, i;
  char *txt, *sized;
  lines_t l;
  fm1_state_report_t rep;
  int ok;
  memset(&l, 0, sizeof(l));
  if (sscanf(spec, "t%d.%d:%n", &t, &sl, &at) == 2 && at > 0) path = spec + at;
  txt = fm1_read_file(path, &len);
  if (!txt) { fprintf(stderr, "cannot read %s\n", path); return 0; }
  sized = (char *)malloc(sizeof(size_t) + len + 1);
  if (!sized) return 0;
  memcpy(sized, &len, sizeof(size_t));
  memcpy(sized + sizeof(size_t), txt, len);
  fm1_state_report_init(&rep);
  ok = fm1_state_sniff((const uint8_t *)txt, len) == 1
           ? fm1_state_bin_read(buf_read, sized, (uint32_t)len, lines_sink, &l, &rep, 0)
           : fm1_state_json_read(NULL, buf_read, sized, lines_sink, &l, &rep);
  free(sized);
  free(txt);
  if (!ok) {
    fprintf(stderr, "%s: %s: %s %s\n", path, fm1_state_code_name(rep.code), rep.what, rep.path);
    return 0;
  }
  if (l.set && !fm1_seq_import_movy1(s, l.set, l.set_n)) ok = 0;
  if (ok && l.clip_n) {
    const size_t need = fm1_seq_export_movy1(s, NULL, 0);
    char *set = (char *)malloc(need + 1), *text;
    char e[160] = "";
    if (!set || t < 1 || t > 16 || sl < 1 || sl > 8) {
      fprintf(stderr, "%s: a clip loads into a track and a slot: --load tT.S:%s\n", path, path);
      free(set);
      ok = 0;
    } else {
      fm1_seq_export_movy1(s, set, need + 1);
      text = fm1_state_clip_into(set, need, (const char *const *)l.clip, l.clip_n, (unsigned)(t - 1),
                                 (unsigned)(sl - 1), e, sizeof(e));
      free(set);
      if (!text || !fm1_seq_import_movy1(s, text, strlen(text))) {
        fprintf(stderr, "%s: the clip does not fit: %s\n", path, e);
        ok = 0;
      }
      free(text);
    }
  }
  free(l.set);
  for (i = 0; i < l.clip_n; ++i) free(l.clip[i]);
  free(l.clip);
  return ok;
}

/* --save clip:T.S:FILE */
static int state_save(const fm1_seq_t *s, const char *spec) {
  int t = 0, sl = 0, at = 0;
  size_t count = 0, i, need = fm1_seq_export_movy1(s, NULL, 0);
  char *set = (char *)malloc(need + 1), **lines;
  void *jw = calloc(1, fm1_state_json_writer_size());
  fm1_state_writer_t *w;
  fm1_state_report_t rep;
  fm1_rec_t r;
  out_t json;
  const char *path;
  FILE *f;
  int ok = 1;
  memset(&json, 0, sizeof(json));
  if (sscanf(spec, "clip:%d.%d:%n", &t, &sl, &at) != 2 || !at || t < 1 || t > 16 || sl < 1 || sl > 8 || !set || !jw) {
    fprintf(stderr, "--save wants clip:T.S:FILE\n");
    free(set);
    free(jw);
    return 0;
  }
  path = spec + at;
  fm1_seq_export_movy1(s, set, need + 1);
  lines = fm1_state_clip_from(set, need, (unsigned)(t - 1), (unsigned)(sl - 1), &count);
  free(set);
  if (!lines) { fprintf(stderr, "--save: no clip at track %d, slot %d\n", t, sl); free(jw); return 0; }
  fm1_state_report_init(&rep);
  w = fm1_state_json_writer(jw, NULL, 0, out_put, &json, &rep);
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_HEAD;
  r.u.head.kind = FM1_STATE_CLIP;
  r.u.head.major = FM1_STATE_MAJOR;
  ok = fm1_state_write(w, &r);
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_INFO;
  r.piece = FM1_REC_FIRST | FM1_REC_LAST;
  r.u.info.key = FM1_INFO_BY;
  r.u.info.s = "desktop";
  r.u.info.n = 7;
  ok = ok && fm1_state_write(w, &r);
  for (i = 0; ok && i < count; ++i) {
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_LINE;
    r.piece = FM1_REC_FIRST | FM1_REC_LAST;
    r.u.line.which = FM1_LINES_CLIP;
    r.u.line.s = lines[i];
    r.u.line.n = (uint32_t)strlen(lines[i]);
    ok = fm1_state_write(w, &r);
  }
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_END;
  ok = ok && fm1_state_write(w, &r);
  fm1_state_clip_free(lines, count);
  free(jw);
  if (ok && strlen(path) > 7 && strcmp(path + strlen(path) - 7, ".lunarb") == 0) {
    void *bw = calloc(1, fm1_state_bin_writer_size());
    out_t bin;
    char *sized = (char *)malloc(sizeof(size_t) + json.n + 1);
    static const uint8_t version[3] = { 0, 1, 0 };
    memset(&bin, 0, sizeof(bin));
    if (!bw || !sized) return 0;
    memcpy(sized, &json.n, sizeof(size_t));
    memcpy(sized + sizeof(size_t), json.b, json.n);
    w = fm1_state_bin_writer(bw, FM1_STATE_BIN_DEFLATE, FM1_STATE_WRITER_DESKTOP, version, out_put, &bin, &rep);
    ok = fm1_state_json_read(NULL, buf_read, sized, fm1_state_bin_write, w, &rep);
    free(sized);
    free(bw);
    free(json.b);
    json = bin;
  }
  if (!ok) { fprintf(stderr, "--save: %s: %s\n", fm1_state_code_name(rep.code), rep.what); free(json.b); return 0; }
  f = fopen(path, "wb");
  if (!f) { fprintf(stderr, "cannot write %s\n", path); free(json.b); return 0; }
  fwrite(json.b, 1, json.n, f);
  free(json.b);
  return fclose(f) == 0;
}

static double now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

int main(int argc, char **argv) {
  const char *cmd_path = NULL, *seq_path = NULL, *log_path = NULL, *state_path = NULL,
             *export_path = NULL, *loads[16], *saves[16];
  int n_loads = 0, n_saves = 0;
  int compat = 0, fill = 0, i;
  long tracks = -1, rate = -1, block = -1, notes = -1, locks = -1, trigs = -1, gates = -1,
       capture = -1, song = -1, rec = -1, events = -1;
  long long end = -1, seed = -1;
  uint64_t *snaps = NULL, *peeks = NULL;
  size_t n_snaps = 0, next_snap = 0, n_peeks = 0, next_peek = 0, k;
  const char **imports = NULL;           /* "FRAME:FILE", in frame order as given */
  size_t n_imports = 0, next_import = 0;
  fm1_script_t script;
  fm1_seq_limits_t lim;
  fm1_seq_t *s;
  void *mem = NULL;
  size_t bytes;
  FILE *log = NULL, *state = NULL;
  fm1_seq_ev_t *ev;
  uint32_t ev_cap = 65536;
  uint64_t frame = 0, blockno = 0, total;
  size_t next_cmd = 0;
  double ns_max = 0.0, ns_sum = 0.0, adv_max = 0.0, adv_sum = 0.0;
  int first_snap = 1;
  char err[256];

  memset(&script, 0, sizeof(script));
  for (i = 1; i < argc; ++i) {
    const char *a = argv[i];
    const char *v = i + 1 < argc ? argv[i + 1] : NULL;
    if (strcmp(a, "--sizes") == 0) { sizes(); return 0; }
    if (strcmp(a, "--compat") == 0) { compat = FM1_SEQ_COMPAT_MOVY; continue; }
    if (strcmp(a, "--compat-frames") == 0) { compat = FM1_SEQ_COMPAT_MOVY_FRAMES; continue; }
    if (!v) { usage(); return 2; }
    ++i;
    if (strcmp(a, "--cmd") == 0) cmd_path = v;
    else if (strcmp(a, "--seq") == 0) seq_path = v;
    else if (strcmp(a, "--log") == 0) log_path = v;
    else if (strcmp(a, "--state") == 0) state_path = v;
    else if (strcmp(a, "--export") == 0) export_path = v;
    else if (strcmp(a, "--load") == 0 && n_loads < 16) loads[n_loads++] = v;
    else if (strcmp(a, "--save") == 0 && n_saves < 16) saves[n_saves++] = v;
    else if (strcmp(a, "--tracks") == 0) tracks = strtol(v, NULL, 0);
    else if (strcmp(a, "--rate") == 0) rate = strtol(v, NULL, 0);
    else if (strcmp(a, "--block") == 0) block = strtol(v, NULL, 0);
    else if (strcmp(a, "--end") == 0) end = strtoll(v, NULL, 0);
    else if (strcmp(a, "--fill") == 0) fill = (int)(strtol(v, NULL, 0) & 0xFF);
    else if (strcmp(a, "--seed") == 0) seed = strtoll(v, NULL, 0);
    else if (strcmp(a, "--notes") == 0) notes = strtol(v, NULL, 0);
    else if (strcmp(a, "--locks") == 0) locks = strtol(v, NULL, 0);
    else if (strcmp(a, "--trigs") == 0) trigs = strtol(v, NULL, 0);
    else if (strcmp(a, "--gates") == 0) gates = strtol(v, NULL, 0);
    else if (strcmp(a, "--capture") == 0) capture = strtol(v, NULL, 0);
    else if (strcmp(a, "--song") == 0) song = strtol(v, NULL, 0);
    else if (strcmp(a, "--rec") == 0) rec = strtol(v, NULL, 0);
    else if (strcmp(a, "--events") == 0) events = strtol(v, NULL, 0);
    else if (strcmp(a, "--import") == 0) {
      const char **grown = (const char **)realloc((void *)imports, (n_imports + 1u) * sizeof(*imports));
      if (!grown || !strchr(v, ':')) { usage(); return 2; }
      imports = grown;
      imports[n_imports++] = v;
    } else if (strcmp(a, "--snap") == 0 || strcmp(a, "--peek") == 0) {
      const int peek = a[2] == 'p';
      uint64_t **list = peek ? &peeks : &snaps;
      size_t *count = peek ? &n_peeks : &n_snaps;
      uint64_t *grown = (uint64_t *)realloc(*list, (*count + 1u) * sizeof(**list));
      if (!grown) return 1;
      *list = grown;
      grown[(*count)++] = (uint64_t)strtoull(v, NULL, 0);
    } else { usage(); return 2; }
  }
  if (cmd_path && !fm1_script_load(cmd_path, &script, err, sizeof(err))) {
    fprintf(stderr, "%s\n", err);
    return 1;
  }
  if (!cmd_path) {
    script.rate = 44118;
    script.block = 128;
    script.tracks = 8;
  }
  if (tracks < 0) tracks = script.tracks;
  if (rate < 0) rate = (long)script.rate;
  if (block < 0) block = (long)script.block;
  if (end < 0) end = script.has_end ? (long long)script.end : -1;
  if (end < 0) {
    /* Default: through the block in which the last command is applied. */
    const uint64_t last = script.n ? script.cmds[script.n - 1].frame : 0;
    end = script.n ? (long long)(((last + (uint64_t)block - 1u) / (uint64_t)block + 1u) * (uint64_t)block) : 0;
  }
  if (tracks < 1 || tracks > 16 || rate < 1 || block < 1 || block > 65535) { usage(); return 2; }

  fm1_seq_limits_default(&lim, (uint8_t)tracks);
  if (compat) {
    /* Movy has no global caps; give the comparison runs generous pools. */
    lim.compat = (uint8_t)compat;
    lim.notes = 16384;
    lim.locks = 16384;
    lim.trigs = 8192;
    lim.gates = 255;
    lim.song = 255;
    lim.rec_notes = 64;
    lim.pad_mutes = 128;
    lim.capture = 512;
  }
  if (notes >= 0) lim.notes = (uint16_t)notes;
  if (locks >= 0) lim.locks = (uint16_t)locks;
  if (trigs >= 0) lim.trigs = (uint16_t)trigs;
  if (gates >= 0) lim.gates = (uint8_t)gates;
  if (capture >= 0) lim.capture = (uint16_t)capture;
  if (song >= 0) lim.song = (uint8_t)song;
  if (rec >= 0) lim.rec_notes = (uint8_t)rec;
  bytes = fm1_seq_size(&lim);
  if (!bytes) { fputs("limits out of range\n", stderr); return 2; }
  /* Over-allocate and offset by 8 so the instance never sits on 16-byte
   * alignment by accident: the core asks for 8. */
  mem = malloc(bytes + 16u);
  if (!mem) return 1;
  memset(mem, fill, bytes + 16u);
  s = fm1_seq_create((char *)mem + 8, &lim, (uint32_t)rate);
  if (!s) { fputs("create failed\n", stderr); return 1; }
  if (seed >= 0) fm1_seq_rng_seed(s, (uint64_t)seed);
  if (seq_path) {
    size_t len;
    char *txt = fm1_read_file(seq_path, &len);
    if (!txt) { fprintf(stderr, "cannot read %s\n", seq_path); return 1; }
    if (!fm1_seq_import_movy1(s, txt, len)) { fprintf(stderr, "%s: not a movy1 set\n", seq_path); return 1; }
    free(txt);
  }
  for (i = 0; i < n_loads; ++i) {
    if (!loads[i] || !state_load(s, loads[i])) return 1;
  }
  if (log_path && !(log = fopen(log_path, "w"))) { fprintf(stderr, "cannot write %s\n", log_path); return 1; }
  if (state_path && !(state = fopen(state_path, "w"))) { fprintf(stderr, "cannot write %s\n", state_path); return 1; }
  if (events > 0 && events < 65536) ev_cap = (uint32_t)events;
  ev = (fm1_seq_ev_t *)malloc(ev_cap * sizeof(*ev));
  if (!ev) return 1;
  if (state) fputs("{\"snaps\":[", state);
  /* glibc declares qsort's base nonnull even for zero items; the lists stay NULL when unused. */
  if (n_snaps > 1) qsort(snaps, n_snaps, sizeof(*snaps), cmp_u64);
  if (n_peeks > 1) qsort(peeks, n_peeks, sizeof(*peeks), cmp_u64);

  total = (uint64_t)end;
  for (;;) {
    uint32_t n_ev = 0, n_adv, frames;
    double t0, dt;
    while (state && next_peek < n_peeks && peeks[next_peek] <= frame) {
      if (!first_snap) fputc(',', state);
      dump_state(state, s, "peek", "", peeks[next_peek], frame, blockno);
      first_snap = 0;
      ++next_peek;
    }
    while (next_import < n_imports && strtoull(imports[next_import], NULL, 0) <= frame) {
      const char *path = strchr(imports[next_import], ':') + 1;
      size_t len;
      char *txt = fm1_read_file(path, &len);
      if (!txt || !fm1_seq_import_movy1(s, txt, len)) {
        fprintf(stderr, "%s: not a movy1 set\n", path);
        return 1;
      }
      free(txt);
      ++next_import;
    }
    t0 = now_ns();
    while (next_cmd < script.n && script.cmds[next_cmd].frame <= frame) {
      const char *ops = script.cmds[next_cmd].ops;
      if (script.cmds[next_cmd].snap) {
        if (state) {
          if (!first_snap) fputc(',', state);
          dump_state(state, s, "label", ops, script.cmds[next_cmd].frame, frame, blockno);
          first_snap = 0;
        }
      } else {
        n_ev += fm1_script_apply(s, ops, ev + n_ev, ev_cap - n_ev);
      }
      ++next_cmd;
    }
    dt = now_ns() - t0;
    while (state && next_snap < n_snaps && snaps[next_snap] <= frame) {
      if (!first_snap) fputc(',', state);
      dump_state(state, s, "snap", "", snaps[next_snap], frame, blockno);
      first_snap = 0;
      ++next_snap;
    }
    if (frame >= total) {
      if (log) for (k = 0; k < n_ev; ++k) fm1_script_log_event(log, blockno, frame, &ev[k]);
      break;
    }
    frames = (uint32_t)(total - frame < (uint64_t)block ? total - frame : (uint64_t)block);
    t0 = now_ns();
    n_adv = fm1_seq_advance(s, frames, ev + n_ev, ev_cap - n_ev);
    t0 = now_ns() - t0;
    if (t0 > adv_max) adv_max = t0;
    adv_sum += t0;
    dt += t0;
    if (dt > ns_max) ns_max = dt;
    ns_sum += dt;
    if (log) for (k = 0; k < n_ev + n_adv; ++k) fm1_script_log_event(log, blockno, frame, &ev[k]);
    frame += frames;
    ++blockno;
  }
  if (state) {
    fputs("],\"end\":", state);
    dump_state(state, s, "end", "", frame, frame, blockno);
    fprintf(state, ",\"bytes\":%lu,\"blocks\":%llu,\"ns_per_block\":%.1f,\"ns_max\":%.1f,"
            "\"advance_ns_per_block\":%.1f,\"advance_ns_max\":%.1f}\n",
            (unsigned long)bytes, (unsigned long long)blockno,
            blockno ? ns_sum / (double)blockno : 0.0, ns_max,
            blockno ? adv_sum / (double)blockno : 0.0, adv_max);
    fclose(state);
  }
  if (log) fclose(log);
  if (export_path) {
    const size_t need = fm1_seq_export_movy1(s, NULL, 0);
    char *text = (char *)malloc(need + 1u);
    FILE *f = fopen(export_path, "wb");
    if (!text || !f) { fprintf(stderr, "cannot write %s\n", export_path); return 1; }
    fm1_seq_export_movy1(s, text, need + 1u);
    fwrite(text, 1, need, f);
    fclose(f);
    free(text);
  }
  for (i = 0; i < n_saves; ++i) {
    if (!saves[i] || !state_save(s, saves[i])) return 1;
  }
  free(ev);
  free(snaps);
  free(peeks);
  free(mem);
  fm1_script_free(&script);
  return 0;
}
