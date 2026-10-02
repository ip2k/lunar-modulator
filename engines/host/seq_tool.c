/* seq_tool.c -- fm1-seq: runs the sequencer core alone, for tests.
 *
 *   fm1-seq --sizes
 *   fm1-seq [--cmd FILE] [--seq FILE.movy1] [--compat | --compat-frames] [--tracks N] [--rate HZ]
 *           [--block N] [--end FRAMES] [--log FILE.jsonl] [--state FILE.json]
 *           [--snap FRAME]... [--peek FRAME]... [--export FILE.movy1] [--fill BYTE] [--seed N]
 *           [--notes N] [--locks N] [--trigs N] [--gates N] [--capture N]
 *           [--song N] [--rec N] [--events N]
 *
 * Plays a verb script (seq_script.h) through fm1_seq in blocks, writes the
 * event log, and dumps state as JSON at each --snap frame (the first block
 * boundary at or after it, once that boundary's commands are applied), each
 * --peek frame (the same boundary, before its commands) and at the end.
 * --events N gives each block (its commands and its advance together) an
 * event buffer of N, as a device's would be; the default is 65536.
 * --compat runs Movy's behaviour exactly; --compat-frames does too, but logs
 * each tick at its own frame (D1), as the Movy oracle's --frames tick does.
 * Without --cmd, nothing runs: --seq FILE --export OUT round-trips
 * a set. --sizes prints fm1_seq_size() for 1-16 tracks with the default
 * limits, with Capture, and the item sizes. MIT licence.
 */
#define _POSIX_C_SOURCE 200112L   /* clock_gettime */

#include "fm1_seq.h"
#include "seq_script.h"

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
        "               [--song N] [--rec N] [--events N]\n", stderr);
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
          "\"following\":%u,\"watch_track\":%u,\"default_quant\":%u,\"song_pos\":%u,\"song\":[",
          (unsigned long long)frame, (unsigned long long)block, (unsigned long long)in.master_tick,
          (unsigned long)in.bpm_x100, in.swing_pct, in.playing, in.recording, in.counting_in,
          in.metronome, in.link, in.following, in.watch_track, in.default_quant, in.song_pos);
  for (i = 0; i < in.song_len; ++i) fprintf(f, i ? ",%u" : "%u", in.song[i]);
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
  printf("},\"capture256\":{");
  for (t = 1; t <= FM1_SEQ_MAX_TRACKS; ++t) {
    fm1_seq_limits_default(&lim, (uint8_t)t);
    lim.capture = 256;
    printf("%s\"%u\":%lu", t > 1 ? "," : "", t, (unsigned long)fm1_seq_size(&lim));
  }
  fm1_seq_limits_default(&lim, 8);
  printf("},\"limits8\":{\"notes\":%u,\"locks\":%u,\"trigs\":%u,\"gates\":%u,\"song\":%u,"
         "\"rec_notes\":%u,\"pad_mutes\":%u},\"cmd_bytes\":%lu,\"event_bytes\":%lu}\n",
         lim.notes, lim.locks, lim.trigs, lim.gates, lim.song, lim.rec_notes, lim.pad_mutes,
         (unsigned long)sizeof(fm1_seq_cmd_t), (unsigned long)sizeof(fm1_seq_ev_t));
}

static int cmp_u64(const void *a, const void *b) {
  const uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return x < y ? -1 : (x > y ? 1 : 0);
}

static double now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

int main(int argc, char **argv) {
  const char *cmd_path = NULL, *seq_path = NULL, *log_path = NULL, *state_path = NULL,
             *export_path = NULL;
  int compat = 0, fill = 0, i;
  long tracks = -1, rate = -1, block = -1, notes = -1, locks = -1, trigs = -1, gates = -1,
       capture = -1, song = -1, rec = -1, events = -1;
  long long end = -1, seed = -1;
  uint64_t *snaps = NULL, *peeks = NULL;
  size_t n_snaps = 0, next_snap = 0, n_peeks = 0, next_peek = 0, k;
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
    else if (strcmp(a, "--snap") == 0 || strcmp(a, "--peek") == 0) {
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
  if (log_path && !(log = fopen(log_path, "w"))) { fprintf(stderr, "cannot write %s\n", log_path); return 1; }
  if (state_path && !(state = fopen(state_path, "w"))) { fprintf(stderr, "cannot write %s\n", state_path); return 1; }
  if (events > 0 && events < 65536) ev_cap = (uint32_t)events;
  ev = (fm1_seq_ev_t *)malloc(ev_cap * sizeof(*ev));
  if (!ev) return 1;
  if (state) fputs("{\"snaps\":[", state);
  qsort(snaps, n_snaps, sizeof(*snaps), cmp_u64);
  qsort(peeks, n_peeks, sizeof(*peeks), cmp_u64);

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
  free(ev);
  free(snaps);
  free(peeks);
  free(mem);
  fm1_script_free(&script);
  return 0;
}
