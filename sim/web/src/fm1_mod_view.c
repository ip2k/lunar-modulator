/* fm1_mod_view.c -- the modulation pages (fm1_mod_view.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_mod_view.h"

#include <stdio.h>

#include "fm1_look.h"
#include "fm1_panel.h"

#define GAP 4                            /* FM1_APP_LAYOUT_GAP */
#define BAR_W (FM1_TFT_W - 2 * MARGIN)
#define STRIP_Y CONTENT_Y
#define STRIP_H 18
#define CELL_W 26
#define CELL_GAP 2
#define STRIP_W (FM1_MOD_POSITIONS * CELL_W + (FM1_MOD_POSITIONS - 1) * CELL_GAP)
#define INFO_Y (STRIP_Y + STRIP_H + GAP)                   /* 50 */
#define PARAMS_Y (INFO_Y + 18 + GAP)                       /* 72 */
#define MARK 8                                             /* the marker's side */
#define TEXT_LINES 8                                       /* MATRIX and CHAIN */

typedef char fm1_mod_view_strip_fits[MARGIN + STRIP_W <= RIGHT ? 1 : -1];
typedef char fm1_mod_view_rows_fit[PARAMS_Y + 3 * ROW_PITCH + BAR_DY + BAR_H + GAP <= BOTTOM_Y ? 1 : -1];
typedef char fm1_mod_view_lines_fit[CONTENT_Y + (TEXT_LINES - 1) * LINE_PITCH + 18 + GAP <= BOTTOM_Y ? 1 : -1];

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
    fm1_look_bar(t, MARGIN, by, BAR_W, BAR_H, p, base, C_ACCENT);
    return;
  }
  {
    /* The label from abbr, the marker (a gold diamond, the bracket's
     * colour), the value right-aligned after it. */
    const int lw = fm1_tft_text(t, MARGIN, y, p->abbr ? p->abbr : p->name, 6, SCALE, C_DIM);
    const int mx = MARGIN + lw + GAP + 2, my = y + (18 - MARK) / 2;
    const int vx = mx + MARK + GAP;
    const int chars = (RIGHT - vx + SCALE) / FM1_TFT_ADVANCE(SCALE);
    const int vw = fm1_tft_text_width(value, chars, SCALE);
    int r;
    fm1_tft_graphic(t, mx, my, MARK, MARK);
    for (r = 0; r < MARK; ++r) {
      const int half = r < MARK / 2 ? r : MARK - 1 - r;   /* 0 1 2 3 3 2 1 0 */
      fm1_tft_paint(t, mx + MARK / 2 - 1 - half, my + r, 2 * half + 2, 1, C_MODEL);
    }
    fm1_tft_text(t, RIGHT - vw, y, value, chars, SCALE, C_TEXT);
  }
  fm1_look_bar(t, MARGIN, by, BAR_W, BAR_H, p, base, C_ACCENT);
  {
    /* The bracket: +-depth of the range round the base, clamped; for a LOG
     * parameter +-depth of its knob round the base's position, the octaves
     * its routes move it (engine API v3). */
    const float range = p->max - p->min;
    const int log = fm1_param_is_log(p);
    const float u = log ? fm1_param_pos(p, base) : 0.0f;
    const int lo = bar_x(p, log ? fm1_param_at(p, u - depth) : base - depth * range, MARGIN, BAR_W);
    const int hi = bar_x(p, log ? fm1_param_at(p, u + depth) : base + depth * range, MARGIN, BAR_W);
    const int lx = bar_x(p, live, MARGIN, BAR_W);
    fm1_tft_paint(t, lo, by, hi - lo + 1, 1, C_MODEL);
    fm1_tft_paint(t, lo, by + BAR_H - 1, hi - lo + 1, 1, C_MODEL);
    fm1_tft_paint(t, lo, by, 1, BAR_H, C_MODEL);
    fm1_tft_paint(t, hi, by, 1, BAR_H, C_MODEL);
    fm1_tft_paint(t, lx, by, 1, BAR_H, C_WARN);      /* the live value */
  }
}

/* ---- RACK ---------------------------------------------------------------------- */

static int src_pos(const fm1_mod_slot_t *s) {
  return s->src >= FM1_MOD_SRC_MODULE && s->src < FM1_MOD_SRC_MODULE + 8u * FM1_MOD_POSITIONS
             ? (int)((s->src - FM1_MOD_SRC_MODULE) / 8u)
             : -1;
}

void fm1_mod_view_rack(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u) {
  const fm1_mod_t *m = env->m;
  const int k = fm1_mod_kind_at(m, u->pos);
  const fm1_mod_kind_t *kd = k >= 0 ? fm1_mod_kinds[k] : NULL;
  char buf[64], label[8];               /* room for any count GCC can imagine */
  unsigned p, i;
  int outs = 0, ins = 0, late = 0;
  /* The rack: one graphic, a cell per position. */
  fm1_tft_graphic(t, MARGIN, STRIP_Y, STRIP_W, STRIP_H);
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    const int x = MARGIN + (int)p * (CELL_W + CELL_GAP);
    const int pk = fm1_mod_kind_at(m, p);
    if (pk < 0) {
      fm1_tft_frame(t, x, STRIP_Y, CELL_W, STRIP_H, p == u->pos ? C_TEXT : C_BAR_BG);
      continue;
    }
    {
      const fm1_mod_kind_t *pd = fm1_mod_kinds[pk];
      float v = fm1_mod_out(m, p, 0), f;
      int h;
      if (pd->n_out && pd->out[0].kind == FM1_PORT_CV_BI) f = (v + 1.0f) * 0.5f;
      else f = v;
      f = f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
      h = (int)(f * (float)STRIP_H + 0.5f);
      fm1_tft_paint(t, x, STRIP_Y, CELL_W, STRIP_H, C_BAR_BG);
      fm1_tft_paint(t, x, STRIP_Y + STRIP_H - h, CELL_W, h, C_ACCENT);
      if (p == u->pos) {
        fm1_tft_frame(t, x, STRIP_Y, CELL_W, STRIP_H, u->grab ? C_MODEL : C_TEXT);
        fm1_tft_frame(t, x + 1, STRIP_Y + 1, CELL_W - 2, STRIP_H - 2, C_BG);
      }
    }
  }
  /* The line under it: position, module, cables out, in, a tick late. */
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
  fm1_mod_ui_label(m, u->pos, label, sizeof label);   /* the position is in the label */
  if (!kd) {
    snprintf(buf, sizeof buf, "%s%u empty", u->grab ? "*" : "", u->pos + 1u);
  } else {
    /* ...and `vN` when it runs per voice (MG9), N its voices now. */
    char voices[16] = "";
    if ((u->plan.poly >> u->pos) & 1u) snprintf(voices, sizeof voices, " v%u", fm1_mod_voice_count(m));
    if (late) {
      snprintf(buf, sizeof buf, "%s%s >%d <%d ~%d%s", u->grab ? "*" : "", label, outs, ins, late, voices);
    } else {
      snprintf(buf, sizeof buf, "%s%s >%d <%d%s", u->grab ? "*" : "", label, outs, ins, voices);
    }
  }
  fm1_tft_text(t, MARGIN, INFO_Y, buf, LINE_CHARS, SCALE, u->grab ? C_MODEL : C_TEXT);
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
      const int routes = fm1_mod_ui_routes(m, FM1_MOD_MODULE + u->pos, q->uid, 0, &depth);
      const int own = fm1_mod_ui_value(env, u->pos, (unsigned)idx[r], base, text, sizeof text);
      fm1_mod_view_row(t, PARAMS_Y + r * ROW_PITCH, q, base, own ? text : NULL, routes, depth,
                       fm1_mod_param(m, u->pos, (unsigned)idx[r]));
    }
  }
}

/* ---- MATRIX ------------------------------------------------------------------- */

void fm1_mod_view_matrix(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u,
                         uint64_t now) {
  char row[FM1_MOD_UI_ROW_CHARS + 1], hint[40];
  int r;
  for (r = 0; r < FM1_MOD_UI_ROWS; ++r) {
    const unsigned i = (unsigned)u->top + (unsigned)r;
    const int y = CONTENT_Y + r * LINE_PITCH;
    uint16_t color = C_TEXT;
    fm1_mod_slot_t s;
    if (i >= FM1_MOD_SLOTS) break;
    fm1_mod_get_slot(env->m, i, &s);
    fm1_mod_ui_row(env, u, i, u->mpage, row);
    if (fm1_mod_ui_empty(u, env->m, i) || !(s.flags & FM1_MOD_SLOT_ON)) color = C_DIM;
    else if ((u->plan.refused >> i) & 1u) color = C_WARN;
    if (i == u->slot) {
      fm1_tft_paint(t, 0, y - 2, FM1_TFT_W, LINE_PITCH, C_ACCENT);
      color = C_BG;
    }
    fm1_tft_text(t, MARGIN, y, row, LINE_CHARS, SCALE, color);
  }
  fm1_mod_ui_hint(env, u, now, hint, sizeof hint);
  hint[LINE_CHARS] = '\0';
  fm1_tft_text(t, MARGIN, CONTENT_Y + FM1_MOD_UI_ROWS * LINE_PITCH, hint, LINE_CHARS, SCALE, C_MODEL);
}

/* ---- CHAIN --------------------------------------------------------------------- */

void fm1_mod_view_chain(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u) {
  char lines[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS + 1];
  int hl = -1, k;
  const int n = fm1_mod_ui_chain(env, u, u->slot, lines, &hl);
  const int start = n <= TEXT_LINES ? 0 : clampi(hl - 3, 0, n - TEXT_LINES);
  for (k = 0; k < TEXT_LINES && start + k < n; ++k) {
    const int at = start + k;
    const uint16_t color = at == hl ? C_ACCENT : (at % 2 == 0 ? C_TEXT : C_DIM);
    fm1_tft_text(t, MARGIN, CONTENT_Y + k * LINE_PITCH, lines[at], LINE_CHARS, SCALE, color);
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
