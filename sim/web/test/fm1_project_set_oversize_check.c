/* PROJECT set-overflow regression. Host-only, MIT. */
#include "fm1_app_state.h"
#include "fm1_edit.h"
#include <assert.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static fm1_app_t app, before;
static fm1_edit_t edit, edit_before;
static char text[131072], roundtrip[131072];
static unsigned char scratch[1024 * 1024] FM1_APP_ALIGN16;
static unsigned char output[262144];
static size_t text_n, output_n, export_length;
static unsigned calls;
static uint32_t digest = 2166136261u;
/* Only seq_persist.o renames its definition; every production caller still
 * resolves this delegating fixture. Real oversized tests leave length zero. */
size_t fm1_real_seq_export_movy1(const fm1_seq_t *, char *, size_t);
size_t fm1_seq_export_movy1(const fm1_seq_t *s, char *b, size_t cap) {
  if (!export_length) return fm1_real_seq_export_movy1(s, b, cap);
  /* 6 + 6553 * 10 = 65536; trailing empty lines cover the next two bytes.
   * All lines are valid existing movy1/typed-codec inputs, below line limits. */
  for (size_t i = 0; b && i < export_length && i + 1 < cap; ++i)
    b[i] = i < 6 ? "movy1\n"[i] : i < 65536 ? "bpm 12000\n"[(i - 6) % 10] : '\n';
  if (b && cap) b[export_length < cap ? export_length : cap - 1] = 0;
  return export_length;
}
static void add(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(text + text_n, sizeof text - text_n, fmt, ap);
  va_end(ap);
  assert(n >= 0 && (size_t)n < sizeof text - text_n);
  text_n += (size_t)n;
}
static void put(void *ctx, const char *s, size_t n) {
  (void)ctx;
  assert(n <= sizeof output - output_n);
  memcpy(output + output_n, s, n); output_n += n; ++calls;
}
static void hash(const void *p, size_t n) {
  const unsigned char *b = p;
  while (n--) digest = (digest ^ *b++) * 16777619u;
}
static void setup(void) {
  fm1_app_init(&app, 44118);
  assert(!fm1_app_select(&app, 0, fm1_app_find("test-sine")));
  assert(!fm1_app_seq_reset(&app, 8));
  fm1_edit_attach(&app, &edit, 0);
  fm1_app_note_on(&app, 60, 100);
}
static void dense_set(int oversized) {
  fm1_seq_stats_t st;
  /* Supported caller-selected pools, in the app's existing fixed arena.
   * Capture is runtime history, not saved set data. Trade it for 64 notes;
   * neither the production arena nor any format limit changes. */
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 8);
  if (oversized) {
    lim.capture = 0;
    lim.notes += 64;
  }
  assert(fm1_seq_size(&lim) <= sizeof app.seq_mem);
  app.seq_lim = lim;
  app.seq = fm1_seq_create(app.seq_mem, &lim, 44118);
  assert(app.seq);
  app.seq_host.seq = app.seq;
  text_n = 0;
  add("movy1\nbpm 12000\nswing 99\nlink 1\nkey 11 1\ndq 100\nsg");
  for (unsigned i = 0; i < 64; ++i) add(" 7");
  add("\nse 1\n");
  for (unsigned i = 0; i < 8; ++i) add("sn %u ABCDEF\n", i);
  for (unsigned t = 0; t < 8; ++t) {
    add("tk %u 7 0\ntn %u 4142434445464748494a4b4c4d4e4f50\n", t, t);
    for (unsigned i = 112; i < 128; ++i) add("pm %u %u\n", t, i);
    add("ps %u 127\n", t);
    for (unsigned l = 0; l < 8; ++l) add("au %u %u 127 ABCDEFGHIJKLMNOPQRSTUVW\n", t, l);
    for (unsigned c = 0; c < 8; ++c) {
      add("cl %u %u 256 0 ", t, c);
      for (unsigned i = 0; i < 24u + (unsigned)oversized; ++i)
        add("%s65535:65535:127:127:%u", i ? ";" : "", 232u - (unsigned)oversized + i);
      add("\ncp %u %u 255 255 -36 100\nlk %u %u ", t, c, t, c);
      for (unsigned i = 0; i < 24; ++i) add("%s7:%u:127", i ? ";" : "", 232 + i);
      add("\ntg %u %u ", t, c);
      for (unsigned i = 0; i < 4; ++i) add("%s%u:127:99:255:255:1", i ? ";" : "", 252 + i);
      add("\n");
    }
  }
  assert(fm1_app_seq_import(&app, text, text_n));
  fm1_seq_get_stats(app.seq, &st);
  assert(!st.refused && !st.movy_faults);
  assert(st.notes_used == 1536u + 64u * (unsigned)oversized && st.locks_used == 1536 && st.trigs_used == 256);
  text_n = fm1_real_seq_export_movy1(app.seq, text, sizeof text);
  printf("real set bytes=%zu notes=%u locks=%u trigs=%u\n", text_n, st.notes_used, st.locks_used, st.trigs_used);
  fflush(stdout);
  assert((text_n >= 65538) == oversized && text_n < sizeof text);
  /* A real current-app set, not a fabricated length: export/import/export
   * roundtrips at the original pool/format limits without refused edits. */
  assert(fm1_app_seq_import(&app, text, text_n));
  fm1_seq_get_stats(app.seq, &st);
  assert(!st.refused && !st.movy_faults);
  size_t n = fm1_real_seq_export_movy1(app.seq, roundtrip, sizeof roundtrip);
  assert(n == text_n && !memcmp(text, roundtrip, n));
}
static void attempt(int mode, int should_fit) {
  float pcm[128];
  fm1_state_report_t r;
  fm1_app_state_workspace_t w = {scratch, fm1_app_state_workspace_size(FM1_APP_STATE_WORK_SAVE)};
  assert(w.bytes <= sizeof scratch);
  fm1_app_note_on(&app, 64, 100);
  memcpy(&before, &app, sizeof app); memcpy(&edit_before, &edit, sizeof edit);
  memcpy(pcm, fm1_app_render(&app, 64), sizeof pcm);
  float energy = 0;
  for (unsigned i = 0; i < 128; ++i) energy += fabsf(pcm[i]);
  assert(energy > 0.001f);  /* PCM equivalence must exercise an audible voice. */
  memcpy(&app, &before, sizeof app); memcpy(&edit, &edit_before, sizeof edit);
  for (int legacy = 0; legacy < 2; ++legacy) {
    output_n = calls = 0;
    int ok = legacy ? fm1_app_state_save(&app, FM1_STATE_PROJECT, 0, mode, put, NULL, &r) :
      fm1_app_state_save_with_workspace(&app, FM1_STATE_PROJECT, 0, mode, put, NULL, &w, &r);
    printf("mode=%d api=%s length=%zu ok=%d code=%u calls=%u bytes=%zu what=%s\n", mode, legacy ? "host" : "workspace",
           export_length ? export_length : text_n, ok, r.code, calls, output_n, r.what);
    fflush(stdout);
    assert(!memcmp(&before, &app, sizeof app) && !memcmp(&edit_before, &edit, sizeof edit));
    if (should_fit) {
      assert(ok && r.code == FM1_STATE_OK && calls && output_n);
      hash(output, output_n);
    } else {
      assert(!ok && r.code == FM1_STATE_TOO_BIG && !calls && !output_n);
    }
  }
  assert(!memcmp(pcm, fm1_app_render(&app, 64), sizeof pcm));
  memcpy(&app, &before, sizeof app); memcpy(&edit, &edit_before, sizeof edit);
}
int main(int argc, char **argv) {
  setup();
  if (argc == 2 && !strcmp(argv[1], "--valid")) {
    for (int mode = 0; mode < 4; ++mode) attempt(mode, 1);
    /* Preserve absent-set PROJECT behavior too. */
    app.seq = NULL;
    for (int mode = 0; mode < 4; ++mode) attempt(mode, 1);
    /* Recreate real sequencer before injecting the exact fitting boundary. */
    assert(!fm1_app_seq_reset(&app, 8));
    for (export_length = 65536; export_length <= 65537; ++export_length)
      for (int mode = 0; mode < 4; ++mode) attempt(mode, 1);
    export_length = 0;
    dense_set(0);
    for (int mode = 0; mode < 4; ++mode) attempt(mode, 1);
    printf("valid digest=%08x\n", digest);
    return 0;
  }
  dense_set(1);
  for (int mode = 0; mode < 4; ++mode) attempt(mode, 0);
  export_length = 65538;
  for (int mode = 0; mode < 4; ++mode) attempt(mode, 0);
  /* Releasing a failed save must permit a subsequent fitting operation. */
  export_length = 65536;
  for (int mode = 0; mode < 4; ++mode) attempt(mode, 1);
  puts("PROJECT oversize guards passed");
  return 0;
}
