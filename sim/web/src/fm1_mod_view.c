/* fm1_mod_view.c -- the modulation pages (fm1_mod_view.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_mod_view.h"

#include <math.h>
#include "fm1_mp.h"
#include <stdio.h>
#include <string.h>

#include "fm1_look.h"
#include "fm1_panel.h"

#define GAP 4                            /* FM1_APP_LAYOUT_GAP */
#define BAR_W (FM1_TFT_W - 2 * MARGIN)
#define STRIP_Y CONTENT_Y
#define STRIP_H 18
#define CELL_W 26
#define CELL_GAP 2
#define CELL_H 13                        /* a cell's meter, the selection's bar under it */
#define SEL_H 3
#define SEL_Y (STRIP_Y + STRIP_H - SEL_H)
#define STRIP_W (FM1_MOD_POSITIONS * CELL_W + (FM1_MOD_POSITIONS - 1) * CELL_GAP)
#define INFO_Y (STRIP_Y + STRIP_H + GAP)                   /* 50 */
#define PARAMS_Y (INFO_Y + 18 + GAP)                       /* 72 */
/* MATRIX and CHAIN set their lines in the MID face (audit D7): MATRIX its
 * slot rows and the hint under them, CHAIN ten lines; the selected line
 * on the selection's bar, 2 px of it above the text and 2 below. */
#define DENSE FM1_TFT_MID
#define DENSE_PITCH MID_LINE_PITCH                         /* 18 */
#define HL_ABOVE 2
#define CHAIN_LINES 10
#define MATRIX_HINT_Y (CONTENT_Y + FM1_MOD_UI_ROWS * DENSE_PITCH + GAP)   /* set apart from the rows */

typedef char fm1_mod_view_strip_fits[MARGIN + STRIP_W <= RIGHT && CELL_H + 2 + SEL_H == STRIP_H ? 1 : -1];
typedef char fm1_mod_view_rows_fit[PARAMS_Y + 3 * ROW_PITCH + BAR_DY + BAR_H + GAP <= BOTTOM_Y ? 1 : -1];
typedef char fm1_mod_view_matrix_fits[MATRIX_HINT_Y + MID_LINE_H + GAP <= BOTTOM_Y &&
                                      FM1_MOD_UI_ROW_CHARS <= MID_LINE_CHARS &&
                                      FM1_MOD_UI_HINT_CHARS <= MID_LINE_CHARS ? 1 : -1];
typedef char fm1_mod_view_chain_fits[CONTENT_Y + (CHAIN_LINES - 1) * DENSE_PITCH + MID_LINE_H + GAP <= BOTTOM_Y &&
                                     CHAIN_LINES <= FM1_MOD_UI_CHAIN_LINES ? 1 : -1];
typedef char fm1_mod_view_bar_fits[CONTENT_Y - HL_ABOVE >= TITLE_H ? 1 : -1];
/* MATRIX's narrow gaps (audit L2's fields, in the spirit of the 4 px rule):
 * the state mark keeps MARK_GAP px more from the source and from what
 * follows it, so a six-character source does not run into its mark
 * ("S2RTRG > ENV4 Gate", not "S2RTRG>ENV4 Gate"), and the space after
 * page A's destination (page B's VIA), always blank, is drawn MARK_GAP
 * wide instead of a character's 8 px, which pays for them: a row keeps
 * its 28 characters' room and ends by RIGHT. The mark's ink keeps at
 * least MARK_GAP from its neighbours' whatever the glyphs. */
#define MARK_GAP 4
#define MARK_COL FM1_MOD_UI_ROW_SRC
#define NARROW_COL(page) (MARK_COL + 1 + ((page) ? FM1_MOD_UI_ROW_SRC : FM1_MOD_UI_ROW_DST))
typedef char fm1_mod_view_marks_fit[FM1_TFT_MID_W(FM1_MOD_UI_ROW_CHARS - 1) + 3 * MARK_GAP <= RIGHT - MARGIN &&
                                    NARROW_COL(1) < NARROW_COL(0) &&
                                    NARROW_COL(0) < FM1_MOD_UI_ROW_CHARS ? 1 : -1];
/* CHAIN's cable line ("-100 >ENV3 Sustain", fm1_mod_ui.c's cable_text): its
 * '>' (column CHAIN_MARK) keeps MARK_GAP px more from the destination, as
 * MATRIX's mark does; a full line still ends by RIGHT. */
#define CHAIN_MARK 5
typedef char fm1_mod_view_chain_mark_fits[FM1_TFT_MID_W(FM1_MOD_UI_ROW_CHARS) + MARK_GAP <= RIGHT - MARGIN
                                          ? 1 : -1];
typedef char fm1_mod_view_popups_agree[FM1_MOD_UI_POPUP_CHARS == POPUP_CHARS &&
                                       FM1_MOD_UI_BANNER_CHARS == BANNER_CHARS_MID ? 1 : -1];

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* Where value v sits on a bar of width w from x (fm1_look_bar's rounding;
 * a LOG parameter's knob position, engine API v3). */
static int bar_x(const fm1_param_t *p, float v, int x, int w) {
  const float range = p->max - p->min;
  float f = range > 0.0f ? (v - p->min) / range : 0.0f;
  int at;
  if (fm1_param_is_log(p)) f = fm1_param_pos(p, v);
  if (!(f == f)) f = 0.0f;
  f = f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
  at = x + (int)(f * (float)w + 0.5f);
  return clampi(at, x, x + w - 1);
}

void fm1_mod_view_row(fm1_tft_t *t, int y, const fm1_param_t *p, float base, const char *text,
                      int routes, float depth, float live) {
  char value[24];
  const int by = y + BAR_DY;
  if (text) snprintf(value, sizeof value, "%s", text);
  else fm1_look_value(p, base, value, sizeof value);
  /* A cable to a parameter that takes none is refused (MATRIX shows it
   * with `!`): nothing moves here, so nothing is marked. */
  if (!fm1_param_modulatable(p) && !(p->flags & FM1_PARAM_INPUT)) routes = 0;
  if (routes <= 0) {
    fm1_look_row(t, y, p->name, value, C_TEXT);
    fm1_look_bar(t, MARGIN, by, BAR_W, BAR_H, p, base, C_SELECT);
    return;
  }
  {
    /* Modulated (audit Q3): the label at full length in the modulation
     * colour, laid out as fm1_look_row lays out every other row, and the
     * value as ever. The bracket below is the cue that needs no colour. */
    const int label_chars = (int)strlen(p->name) < LABEL_CHARS ? (int)strlen(p->name) : LABEL_CHARS;
    const int value_chars = LINE_CHARS - 1 - label_chars;
    fm1_tft_text(t, MARGIN, y, p->name, label_chars, SCALE, C_MOD);
    fm1_tft_text(t, RIGHT - fm1_tft_text_width(value, value_chars, SCALE), y, value, value_chars,
                 SCALE, C_TEXT);
  }
  fm1_look_bar(t, MARGIN, by, BAR_W, BAR_H, p, base, C_SELECT);
  {
    /* The bracket: +-depth of the range round the base, clamped; for a LOG
     * parameter +-depth of its knob round the base's position, the octaves
     * its routes move it (engine API v3). The live value is a tick in the
     * text colour. */
    const float range = p->max - p->min;
    const int log = fm1_param_is_log(p);
    const float u = log ? fm1_param_pos(p, base) : 0.0f;
    const int lo = bar_x(p, log ? fm1_param_at(p, u - depth) : base - depth * range, MARGIN, BAR_W);
    const int hi = bar_x(p, log ? fm1_param_at(p, u + depth) : base + depth * range, MARGIN, BAR_W);
    const int lx = bar_x(p, live, MARGIN, BAR_W);
    fm1_tft_paint(t, lo, by, hi - lo + 1, 1, C_MOD);
    fm1_tft_paint(t, lo, by + BAR_H - 1, hi - lo + 1, 1, C_MOD);
    fm1_tft_paint(t, lo, by, 1, BAR_H, C_MOD);
    fm1_tft_paint(t, hi, by, 1, BAR_H, C_MOD);
    fm1_tft_paint(t, lx, by, 1, BAR_H, C_HINT);      /* the live value */
  }
}

/* ---- RACK ---------------------------------------------------------------------- */

static int src_pos(const fm1_mod_slot_t *s) {
  return s->src >= FM1_MOD_SRC_MODULE && s->src < FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS
             ? (int)((s->src - FM1_MOD_SRC_MODULE) / 8u)
             : -1;
}

static int span_chars(const fm1_tft_span_t *sp, int n) {
  int k, c = 0;
  for (k = 0; k < n; ++k) c += sp[k].s ? (int)strlen(sp[k].s) : 0;
  return c;
}

/* The info line's run: its pieces joined by `sep`, the label in `lead`,
 * each number as text and each word subtle. */
static int info_spans(fm1_tft_span_t *sp, char (*buf)[16], const char *label, uint16_t lead,
                      const int *num, const char *const *word, int n, const char *sep) {
  int k, ns = 0;
  sp[ns].s = label;
  sp[ns++].color = lead;
  for (k = 0; k < n; ++k) {
    snprintf(buf[k], sizeof buf[k], "%s%d", sep, num[k]);
    sp[ns].s = buf[k];
    sp[ns++].color = C_TEXT;
    sp[ns].s = word[k];
    sp[ns++].color = C_LABEL;
  }
  return ns;
}

/* Timed stages share one seconds axis. Sustain is an explicitly unbounded
 * hold region. The audio trace has its own short time window, labelled as
 * such: it is the recent mixed output, not a fabricated envelope waveform. */
static void env_graph(fm1_tft_t *t, const fm1_mod_ui_env_t *env, unsigned pos) {
  const fm1_mp_env_t *e = (const fm1_mp_env_t *)fm1_mod_view_state(env->m, pos);
  const int x = MARGIN, y = 160, w = BAR_W, h = 32;
  float duration[5] = {0}, total = 0, hold, starts[5], ends[5];
  int segments[5], stage = -1, offset, ad, looping, release, prev = -1;
  char caption[40];
  if (!e) return;
  offset = e->delay_stage ? 1 : 0;
  ad = e->sustain == 0;
  looping = e->loop_end > e->loop_start;
  release = offset + 2;
  for (int i = 0; i < 5; ++i) segments[i] = -1;
  if (e->delay_stage == 1) segments[0] = 0;
  segments[1] = offset;
  segments[2] = offset + 1;
  if (!ad) segments[4] = release;
  for (int i = 0; i < 5; ++i) if (segments[i] >= 0) {
    uint32_t inc = e->inc[segments[i]];
    duration[i] = (float)((0x100000000ull + inc - 1u) / inc) / e->sample_rate;
    total += duration[i];
  }
  hold = !ad && !looping ? total * 0.18f : 0.0f;
  if (hold > 0 && hold < 0.05f) hold = 0.05f;
  duration[3] = hold;
  snprintf(caption, sizeof caption, "Env %.2fs + hold | Audio %.0fms", (double)total,
           env->rate > 0 ? (double)(1000.0f * env->scope_n / env->rate) : 0.0);
  if (!hold) snprintf(caption, sizeof caption, "Env %.2fs | Audio %.0fms", (double)total,
           env->rate > 0 ? (double)(1000.0f * env->scope_n / env->rate) : 0.0);
  fm1_tft_font_text(t, x, 144, caption, SMALL_LINE_CHARS, FM1_TFT_SMALL, C_LABEL);
  total += hold;
  if (total <= 0) return;
  {
    float at = 0;
    for (int i = 0; i < 5; ++i) { starts[i] = at; at += duration[i]; ends[i] = at; }
  }
  fm1_tft_graphic(t, x, y, w, h);
  fm1_tft_paint(t, x, y, w, h, C_SCOPE_BG);
  if (env->scope && env->scope_n) {
    for (int px = 0; px < w; ++px) {
      unsigned n = ((unsigned)px * env->scope_n / (unsigned)w + env->scope_pos) % env->scope_n;
      float v = env->scope[n];
      if (!isfinite(v)) v = 0;
      v = v < -1 ? -1 : v > 1 ? 1 : v;
      int py = y + h / 2 - (int)(v * (h / 2 - 1));
      int lo = prev < 0 || py < prev ? py : prev, hi = prev < 0 || py > prev ? py : prev;
      fm1_tft_paint(t, x + px, lo, 1, hi - lo + 1, RP_HIGHLIGHT_HIGH);
      prev = py;
    }
  }
  prev = -1;
  for (int px = 0; px < w; ++px) {
    float time = total * px / (w - 1), v = 0;
    int i = 0;
    while (i < 4 && (duration[i] <= 0 || time > ends[i])) ++i;
    if (i == 3) v = e->level[release];
    else if (segments[i] >= 0) {
      int seg = segments[i];
      float a = e->level[seg], b = e->level[seg + 1];
      float f = duration[i] > 0 ? (time - starts[i]) / duration[i] : 1;
      if ((e->seg == seg || (i == 4 && !e->gate && e->seg == e->sustain)) &&
          !fm1_mp_env_done(e)) a = e->start;
      f = f < 0 ? 0 : f > 1 ? 1 : f;
      v = a + (b - a) * (f >= 1 ? 1 : fm1_mp_env_curve_at(e->curve[seg], (uint32_t)((double)f * 4294967296.0)));
    }
    v = v < 0 ? 0 : v > 1 ? 1 : v;
    int py = y + h - 1 - (int)(v * (h - 1) + 0.5f);
    int lo = prev < 0 || py < prev ? py : prev, hi = prev < 0 || py > prev ? py : prev;
    fm1_tft_paint(t, x + px, lo, 1, hi - lo + 1, C_MOD);
    prev = py;
  }
  if (!fm1_mp_env_done(e)) {
    float time = 0;
    if (hold && e->seg == e->sustain && e->gate) { stage = 3; time = starts[3] + hold * 0.5f; }
    else {
      for (int i = 0; i < 5; ++i) if (segments[i] == e->seg) { stage = i; break; }
      if (!ad && !e->gate && e->seg == e->sustain) stage = 4;
      if (stage >= 0) time = starts[stage] + duration[stage] * ((float)e->phase / 4294967296.0f);
    }
    if (stage >= 0) {
      int px = x + clampi((int)(time / total * (w - 1)), 0, w - 1);
      fm1_tft_paint(t, px, y, 1, h, C_LIVE);
    }
  }
  {
    static const char *const names[] = { "Delay", "Attack", "Decay", "Sustain", "Release" };
    for (int i = 0; i < 5; ++i) {
      fm1_tft_font_text(t, x + i * 46, 198, names[i], 7, FM1_TFT_SMALL,
                       i == stage ? C_LIVE : duration[i] > 0 ? C_LABEL : C_DIM);
    }
  }
}

void fm1_mod_view_rack(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u) {
  const fm1_mod_t *m = env->m;
  const int k = fm1_mod_kind_at(m, u->pos);
  const fm1_mod_kind_t *kd = k >= 0 ? fm1_mod_kinds[k] : NULL;
  char label[8], lead[12];
  unsigned p, i;
  int outs = 0, ins = 0, late = 0;
  /* The rack: one graphic, a cell per position, each a meter of its
   * module's first output in the modulation colour (an empty position
   * hollow), and under the shown one the selection's bar (gold while
   * SELECT moves it: grabbed). */
  fm1_tft_graphic(t, MARGIN, STRIP_Y, STRIP_W, STRIP_H);
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    const int x = MARGIN + (int)p * (CELL_W + CELL_GAP);
    const int pk = fm1_mod_kind_at(m, p);
    if (p == u->pos) fm1_tft_paint(t, x, SEL_Y, CELL_W, SEL_H, u->grab ? C_HELD : C_SELECT);
    if (pk < 0) {
      fm1_tft_frame(t, x, STRIP_Y, CELL_W, CELL_H, RP_HIGHLIGHT_HIGH);
      continue;
    }
    {
      const fm1_mod_kind_t *pd = fm1_mod_kinds[pk];
      float v = fm1_mod_out(m, p, 0), f;
      int h;
      if (pd->n_out && pd->out[0].kind == FM1_PORT_CV_BI) f = (v + 1.0f) * 0.5f;
      else f = v;
      f = f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
      h = (int)(f * (float)CELL_H + 0.5f);
      fm1_tft_paint(t, x, STRIP_Y, CELL_W, CELL_H, C_BAR_BG);
      fm1_tft_paint(t, x, STRIP_Y + CELL_H - h, CELL_W, h, C_MOD);
    }
  }
  /* The line under it: the module, the cables out of it and into it, those
   * a tick late, and its voices when it runs per voice (MG9). */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    const int on = ((u->plan.active >> i) & 1u) != 0;
    fm1_mod_get_slot(m, i, &s);
    if (!(s.flags & FM1_MOD_SLOT_ON)) continue;
    if (src_pos(&s) == (int)u->pos) outs += 1;
    if (s.dst_unit == FM1_MOD_MODULE + u->pos) ins += 1;
    if (on && ((u->plan.delayed >> i) & 1u) &&
        (src_pos(&s) == (int)u->pos || s.dst_unit == FM1_MOD_MODULE + u->pos)) {
      late += 1;
    }
  }
  if (kd) fm1_mod_ui_label(m, u->pos, label, sizeof label);   /* the position is in the label */
  else snprintf(label, sizeof label, "Mod%u", u->pos + 1u);
  snprintf(lead, sizeof lead, "%s%s", u->grab ? "*" : "", label);
  {
    /* "LFO6  2 out  7 in  1 late  4 voices": in MID where it fits, else
     * SMALL; the label gold while grabbed (the '*' for who cannot tell). */
    static const char *const kWord[4] = { " out", " in", " late", " voices" };
    const char *word[4];
    int num[4], n = 0, ns, f;
    char buf[4][16];
    fm1_tft_span_t sp[9];
    if (kd) {
      num[n] = outs, word[n++] = kWord[0];
      num[n] = ins, word[n++] = kWord[1];
      if (late) num[n] = late, word[n++] = kWord[2];
      if ((u->plan.poly >> u->pos) & 1u) num[n] = (int)fm1_mod_voice_count(m), word[n++] = kWord[3];
    }
    for (f = 0; f < 4; ++f) {
      const fm1_tft_font_t font = f < 2 ? FM1_TFT_MID : FM1_TFT_SMALL;
      const int room = font == FM1_TFT_MID ? MID_LINE_CHARS : SMALL_LINE_CHARS;
      ns = info_spans(sp, buf, lead, u->grab ? C_HELD : C_TEXT, num, word, n, f % 2 ? " " : "  ");
      if (!kd) sp[ns].s = "  empty", sp[ns++].color = C_LABEL;
      if (span_chars(sp, ns) <= room || f == 3) {
        const int h = fm1_tft_metrics(font)->height;
        fm1_tft_span_text(t, MARGIN, INFO_Y + (18 - h) / 2, sp, ns, room, font);
        break;
      }
    }
  }
  if (!kd) {
    fm1_tft_text(t, MARGIN, PARAMS_Y + 4, "Empty position:", LINE_CHARS, SCALE, C_DIM);
    fm1_tft_text(t, MARGIN, PARAMS_Y + 4 + LINE_PITCH, "turn ALGORITHM", LINE_CHARS, SCALE, C_DIM);
    return;
  }
  {
    int idx[4];
    const int n = fm1_mod_ui_rack_params(m, u->pos, u->page, idx);
    int r;
    for (r = 0; r < n; ++r) {
      const fm1_param_t *q = &kd->params[idx[r]];
      const float base = fm1_mod_param_base(m, u->pos, (unsigned)idx[r]);
      float depth = 0.0f;
      char text[24];
      const int routes = fm1_mod_ui_routes(m, u->plan.refused, FM1_MOD_MODULE + u->pos, q->uid, 0,
                                           &depth);
      const int own = fm1_mod_ui_value(env, u->pos, (unsigned)idx[r], base, text, sizeof text);
      if (strcmp(kd->id, "env") == 0) {
        if (!own) fm1_look_value(q, base, text, sizeof text);
        fm1_tft_font_text(t, MARGIN, PARAMS_Y + r * 18, q->name, 12, FM1_TFT_SMALL,
                         routes ? C_MOD : C_LABEL);
        fm1_tft_font_text(t, RIGHT - fm1_tft_font_width(text, 18, FM1_TFT_SMALL),
                         PARAMS_Y + r * 18, text, 18, FM1_TFT_SMALL, C_TEXT);
      } else {
        fm1_mod_view_row(t, PARAMS_Y + r * ROW_PITCH, q, base, own ? text : NULL, routes, depth,
                         fm1_mod_param(m, u->pos, (unsigned)idx[r]));
      }
    }
  }
  if (strcmp(kd->id, "env") == 0) env_graph(t, env, u->pos);
}

/* ---- MATRIX and CHAIN's lines ------------------------------------------------- */

/* A role's colour (fm1_mod_ui.h; audit L2): sources in the modulation
 * colour, marks subtle, destinations and amounts as text, a sound's
 * "S<n>" in that sound's colour; padding takes its neighbour's. */
static uint16_t role_colour(uint8_t role) {
  if (role >= FM1_MOD_UI_ROLE_SOUND) return fm1_sound_colour(role - FM1_MOD_UI_ROLE_SOUND);
  switch (role) {
    case FM1_MOD_UI_ROLE_SRC: return C_MOD;
    case FM1_MOD_UI_ROLE_MARK: return C_LABEL;
    case FM1_MOD_UI_ROLE_DST:
    case FM1_MOD_UI_ROLE_AMT: return C_TEXT;
    default: return C_LABEL;
  }
}

/* One line in the dense face at (MARGIN, y): in `solid` when roles is
 * NULL, else in its roles' colours, as one run (one logged box). A MATRIX
 * row (page 0 or 1; -1 for CHAIN's lines) gets the mark's narrow gaps; a
 * CHAIN cable line, the gap after its '>'. */
static void role_line(fm1_tft_t *t, int y, const char *s, const uint8_t *roles, uint16_t solid,
                      int page) {
  char seg[2 * (FM1_MOD_UI_ROW_CHARS + 1)];
  fm1_tft_span_t spans[FM1_MOD_UI_ROW_CHARS];
  uint8_t lead[FM1_MOD_UI_ROW_CHARS];
  const int n = (int)strlen(s) < FM1_MOD_UI_ROW_CHARS ? (int)strlen(s) : FM1_MOD_UI_ROW_CHARS;
  const int narrow = page < 0 ? -1 : NARROW_COL(page);
  const int chain_mark = page < 0 && n > CHAIN_MARK + 1 && s[CHAIN_MARK - 1] == ' ' && s[CHAIN_MARK] == '>'
                             ? CHAIN_MARK : -1;
  int k, ns = 0, at = 0, gap = 0;
  uint16_t cur = solid;
  for (k = 0; k < n; ++k) {
    uint16_t c = solid;
    if (k == narrow && s[k] == ' ') {    /* the blank after the destination or VIA */
      gap += MARK_GAP;
      continue;
    }
    if (page >= 0 && (k == MARK_COL || k == MARK_COL + 1)) gap += MARK_GAP;
    if (chain_mark >= 0 && k == chain_mark + 1) gap += MARK_GAP;   /* CHAIN: after its '>' */
    if (roles) c = roles[k] != FM1_MOD_UI_ROLE_PLAIN ? role_colour(roles[k]) : k ? cur : C_LABEL;
    if (ns == 0 || c != cur || gap) {
      if (ns) seg[at++] = '\0';
      spans[ns].s = &seg[at];
      spans[ns].color = c;
      lead[ns] = (uint8_t)gap;
      ++ns;
      cur = c;
      gap = 0;
    }
    seg[at++] = s[k];
  }
  seg[at] = '\0';
  fm1_tft_span_text_lead(t, MARGIN, y, spans, lead, ns, FM1_MOD_UI_ROW_CHARS, DENSE);
}

/* ---- MATRIX ------------------------------------------------------------------- */

void fm1_mod_view_matrix(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u,
                         uint64_t now) {
  char row[FM1_MOD_UI_ROW_CHARS + 1], hint[40];
  uint8_t roles[FM1_MOD_UI_ROW_CHARS];
  int r;
  for (r = 0; r < FM1_MOD_UI_ROWS; ++r) {
    const unsigned i = (unsigned)u->top + (unsigned)r;
    const int y = CONTENT_Y + r * DENSE_PITCH;
    fm1_mod_slot_t s;
    if (i >= FM1_MOD_SLOTS) break;
    fm1_mod_get_slot(env->m, i, &s);
    fm1_mod_ui_row(env, u, i, u->mpage, row, roles);
    /* The selected row on the selection's bar; a row that is off or
     * empty subtle, a refused one in the refusal colour, whole (the mark
     * says which as well); else each field in its colour. */
    if (i == u->slot) {
      fm1_tft_paint(t, 0, y - HL_ABOVE, FM1_TFT_W, DENSE_PITCH, C_SELECT);
      role_line(t, y, row, NULL, C_BG, u->mpage);
    } else if (fm1_mod_ui_empty(u, env->m, i) || !(s.flags & FM1_MOD_SLOT_ON)) {
      role_line(t, y, row, NULL, C_LABEL, u->mpage);
    } else if ((u->plan.refused >> i) & 1u) {
      role_line(t, y, row, NULL, C_REFUSE, u->mpage);
    } else {
      role_line(t, y, row, roles, 0, u->mpage);
    }
  }
  fm1_mod_ui_hint(env, u, now, hint, sizeof hint);
  hint[FM1_MOD_UI_HINT_CHARS] = '\0';
  /* The hint names a sound in its colour; under a refused slot it is in
   * the refusal colour, whole, as the slot's row is when not selected. */
  if ((u->plan.refused >> u->slot) & 1u) {
    fm1_tft_font_text(t, MARGIN, MATRIX_HINT_Y, hint, FM1_MOD_UI_HINT_CHARS, DENSE, C_REFUSE);
  } else {
    fm1_look_sound_text(t, MARGIN, MATRIX_HINT_Y, hint, FM1_MOD_UI_HINT_CHARS, DENSE, C_HINT);
  }
}

/* ---- CHAIN --------------------------------------------------------------------- */

void fm1_mod_view_chain(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u) {
  char lines[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS + 1];
  uint8_t roles[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS];
  int hl = -1, k;
  const int n = fm1_mod_ui_chain(env, u, u->slot, lines, roles, &hl);
  const int start = n <= CHAIN_LINES ? 0 : clampi(hl - 4, 0, n - CHAIN_LINES);
  for (k = 0; k < CHAIN_LINES && start + k < n; ++k) {
    const int at = start + k;
    const int y = CONTENT_Y + k * DENSE_PITCH;
    if (at == hl) {                     /* the selected cable, on the selection's bar */
      fm1_tft_paint(t, 0, y - HL_ABOVE, FM1_TFT_W, DENSE_PITCH, C_SELECT);
      role_line(t, y, lines[at], NULL, C_BG, -1);
    } else if (n == 1) {                /* "Slot 21: no cable" */
      role_line(t, y, lines[at], NULL, C_LABEL, -1);
    } else {
      role_line(t, y, lines[at], roles[at], 0, -1);
    }
  }
}

/* ---- the bars' texts -------------------------------------------------------------- */

void fm1_mod_view_title(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, int mode, char *buf,
                        size_t size) {
  if (mode == FM1_MODE_RACK) fm1_mod_ui_title(env->m, u->pos, buf, size);
  else if (mode == FM1_MODE_MATRIX) snprintf(buf, size, "Matrix %c", u->mpage ? 'B' : 'A');
  else snprintf(buf, size, "Chain");
}

void fm1_mod_view_bottom(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, int mode, char *buf,
                         size_t size) {
  if (mode == FM1_MODE_RACK) {
    snprintf(buf, size, "%d/%d Mod%u", u->page + 1, fm1_mod_ui_rack_pages(env->m, u->pos),
             u->pos + 1u);
  } else {
    /* "Slot", not "Matrix": with two digits it would reach the RAM meter
     * on the right. */
    snprintf(buf, size, "%u/%u %s", u->slot + 1u, FM1_MOD_SLOTS,
             mode == FM1_MODE_MATRIX ? "Slot" : "Chain");
  }
}
