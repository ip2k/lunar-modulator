/* fm1_tft.c -- the virtual FM-1's frame buffer (fm1_tft.h). MIT licence. */
#include "fm1_tft.h"

#include "fm1_font.h"
#include "fm1_font_mid.h"
#include "fm1_font_small.h"

#include <stddef.h>
#include <stdint.h>

/* The metrics fm1_tft.h declares are the generated tables' (C99: an array
 * of negative size stops the build). */
#define TFT_CHECK(name, cond) typedef char fm1_tft_check_##name[(cond) ? 1 : -1]
TFT_CHECK(main_advance, FM1_TFT_MAIN_ADVANCE == FM1_TFT_ADVANCE(2));
TFT_CHECK(main_h, FM1_TFT_MAIN_H == FM1_TFT_TEXT_H(2) && FM1_FONT_ROWS == 9);
TFT_CHECK(main_ink_w, FM1_TFT_MAIN_INK_W == 2 * FM1_FONT_COLS);
TFT_CHECK(mid_cell, FM1_FONT_MID_ROWS == FM1_TFT_MID_H && FM1_FONT_MID_COLS <= 8 &&
                        FM1_FONT_MID_ADVANCE == FM1_TFT_MID_ADVANCE);
TFT_CHECK(mid_shape, FM1_FONT_MID_INK_W == FM1_TFT_MID_INK_W &&
                         FM1_FONT_MID_CAP_H == FM1_TFT_MID_CAP_H &&
                         FM1_FONT_MID_BASELINE == FM1_TFT_MID_BASELINE);
TFT_CHECK(small_cell, FM1_FONT_SMALL_ROWS == FM1_TFT_SMALL_H && FM1_FONT_SMALL_COLS <= 8 &&
                          FM1_FONT_SMALL_ADVANCE == FM1_TFT_SMALL_ADVANCE);
TFT_CHECK(small_shape, FM1_FONT_SMALL_INK_W == FM1_TFT_SMALL_INK_W &&
                           FM1_FONT_SMALL_CAP_H == FM1_TFT_SMALL_CAP_H &&
                           FM1_FONT_SMALL_BASELINE == FM1_TFT_SMALL_BASELINE);
TFT_CHECK(ranges, FM1_FONT_MID_FIRST == FM1_FONT_FIRST && FM1_FONT_MID_LAST == FM1_FONT_LAST &&
                      FM1_FONT_SMALL_FIRST == FM1_FONT_FIRST &&
                      FM1_FONT_SMALL_LAST == FM1_FONT_LAST);

/* A face: its glyphs (`rows` bytes each, bit cols-1 the leftmost column),
 * drawn at `scale`, and its metrics. */
typedef struct face {
  const uint8_t *glyphs;
  uint8_t rows, cols, scale;
  fm1_tft_metrics_t m;
} face_t;

static const face_t k_faces[FM1_TFT_FONTS] = {
  { &fm1_font5x9[0][0], FM1_FONT_ROWS, FM1_FONT_COLS, 2,
    { FM1_TFT_MAIN_ADVANCE, FM1_TFT_MAIN_H, FM1_TFT_MAIN_INK_W, FM1_TFT_MAIN_CAP_H,
      FM1_TFT_MAIN_BASELINE } },
  { &fm1_font_mid[0][0], FM1_FONT_MID_ROWS, FM1_FONT_MID_COLS, 1,
    { FM1_TFT_MID_ADVANCE, FM1_TFT_MID_H, FM1_TFT_MID_INK_W, FM1_TFT_MID_CAP_H,
      FM1_TFT_MID_BASELINE } },
  { &fm1_font_small[0][0], FM1_FONT_SMALL_ROWS, FM1_FONT_SMALL_COLS, 1,
    { FM1_TFT_SMALL_ADVANCE, FM1_TFT_SMALL_H, FM1_TFT_SMALL_INK_W, FM1_TFT_SMALL_CAP_H,
      FM1_TFT_SMALL_BASELINE } },
};

static const face_t *face_of(fm1_tft_font_t font) {
  return (unsigned)font < FM1_TFT_FONTS ? &k_faces[font] : &k_faces[FM1_TFT_MAIN];
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static void log_box(fm1_tft_t *t, int x, int y, int w, int h, uint8_t kind, uint8_t font) {
  if (!t->record || w <= 0 || h <= 0) return;
  if (t->n_boxes >= FM1_TFT_MAX_BOXES) {
    t->overflow = 1;
    return;
  }
  fm1_tft_box_t *b = &t->boxes[t->n_boxes++];
  b->x = (int16_t)x;
  b->y = (int16_t)y;
  b->w = (int16_t)w;
  b->h = (int16_t)h;
  b->kind = kind;
  b->hidden = 0;
  b->font = font;
}

static int touches(int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh, int gap) {
  return ax < bx + bw + gap && bx < ax + aw + gap && ay < by + bh + gap && by < ay + ah + gap;
}

void fm1_tft_begin(fm1_tft_t *t, uint16_t color) {
  for (int i = 0; i < FM1_TFT_W * FM1_TFT_H; ++i) t->px[i] = color;
  t->n_boxes = 0;
  t->overflow = 0;
  t->truncated = 0;
}

void fm1_tft_paint(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color) {
  int x0 = clampi(x, 0, FM1_TFT_W), x1 = clampi(x + w, 0, FM1_TFT_W);
  int y0 = clampi(y, 0, FM1_TFT_H), y1 = clampi(y + h, 0, FM1_TFT_H);
  for (int yy = y0; yy < y1; ++yy) {
    uint16_t *row = &t->px[yy * FM1_TFT_W];
    for (int xx = x0; xx < x1; ++xx) row[xx] = color;
  }
}

void fm1_tft_fill(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color) {
  for (int i = 0; i < t->n_boxes; ++i) {
    fm1_tft_box_t *b = &t->boxes[i];
    if (touches(x, y, w, h, b->x, b->y, b->w, b->h, 0)) b->hidden = 1;
  }
  fm1_tft_paint(t, x, y, w, h, color);
}

void fm1_tft_frame(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color) {
  fm1_tft_paint(t, x, y, w, 1, color);
  fm1_tft_paint(t, x, y + h - 1, w, 1, color);
  fm1_tft_paint(t, x, y, 1, h, color);
  fm1_tft_paint(t, x + w - 1, y, 1, h, color);
}

void fm1_tft_graphic(fm1_tft_t *t, int x, int y, int w, int h) {
  log_box(t, x, y, w, h, FM1_BOX_GRAPHIC, 0);
}

static int text_len(const char *s, int max_chars) {
  int n = 0;
  while (s[n] && n < max_chars) ++n;
  return n;
}

int fm1_tft_text_width(const char *s, int max_chars, int scale) {
  int n = text_len(s, max_chars);
  return n ? n * FM1_TFT_ADVANCE(scale) - scale : 0;
}

/* One glyph of a table, its top-left at (x, y); outside 0x20..0x7E, '?'. */
static void draw_glyph(fm1_tft_t *t, int x, int y, int c, const uint8_t *glyphs, int rows,
                       int cols, int scale, uint16_t color) {
  if (c < FM1_FONT_FIRST || c > FM1_FONT_LAST) c = '?';
  const uint8_t *g = glyphs + (c - FM1_FONT_FIRST) * rows;
  for (int r = 0; r < rows; ++r) {
    for (int col = 0; col < cols; ++col) {
      if (g[r] & (1u << (cols - 1 - col))) {
        fm1_tft_paint(t, x + col * scale, y + r * scale, scale, scale, color);
      }
    }
  }
}

int fm1_tft_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars, int scale,
                 uint16_t color) {
  int n = text_len(s, max_chars);
  int w = fm1_tft_text_width(s, n, scale);
  log_box(t, x, y, w, FM1_TFT_TEXT_H(scale), FM1_BOX_TEXT, FM1_TFT_MAIN);
  if (t->record && s[n]) ++t->truncated;
  for (int i = 0; i < n; ++i) {
    draw_glyph(t, x + i * FM1_TFT_ADVANCE(scale), y, (unsigned char)s[i], &fm1_font5x9[0][0],
               FM1_FONT_ROWS, FM1_FONT_COLS, scale, color);
  }
  return w;
}

const fm1_tft_metrics_t *fm1_tft_metrics(fm1_tft_font_t font) { return &face_of(font)->m; }

int fm1_tft_font_width(const char *s, int max_chars, fm1_tft_font_t font) {
  const fm1_tft_metrics_t *m = &face_of(font)->m;
  return FM1_TFT_RUN_W(m->advance, m->ink_w, text_len(s, max_chars));
}

int fm1_tft_font_fit(int w, fm1_tft_font_t font) {
  const fm1_tft_metrics_t *m = &face_of(font)->m;
  return FM1_TFT_FIT(m->advance, m->ink_w, w);
}

/* The characters of the spans that max_chars lets through, whether a span
 * was cut short, and the pixels the leads add (lead NULL for none): a
 * lead counts before a span that draws a character, not before the
 * first. */
static int span_len(const fm1_tft_span_t *spans, const uint8_t *lead, int n_spans, int max_chars,
                    int *cut, int *gaps) {
  int n = 0;
  *cut = 0;
  *gaps = 0;
  for (int k = 0; k < n_spans; ++k) {
    const char *s = spans[k].s;
    if (!s) continue;
    int len = text_len(s, max_chars - n);
    if (lead && len && n) *gaps += lead[k];
    n += len;
    if (s[len]) *cut = 1;
  }
  return n;
}

int fm1_tft_span_width_lead(const fm1_tft_span_t *spans, const uint8_t *lead, int n_spans,
                            int max_chars, fm1_tft_font_t font) {
  const fm1_tft_metrics_t *m = &face_of(font)->m;
  int cut, gaps;
  const int n = span_len(spans, lead, n_spans, max_chars, &cut, &gaps);
  return n ? FM1_TFT_RUN_W(m->advance, m->ink_w, n) + gaps : 0;
}

int fm1_tft_span_width(const fm1_tft_span_t *spans, int n_spans, int max_chars,
                       fm1_tft_font_t font) {
  return fm1_tft_span_width_lead(spans, NULL, n_spans, max_chars, font);
}

int fm1_tft_span_text_lead(fm1_tft_t *t, int x, int y, const fm1_tft_span_t *spans,
                           const uint8_t *lead, int n_spans, int max_chars, fm1_tft_font_t font) {
  const face_t *f = face_of(font);
  int cut, gaps;
  int n = span_len(spans, lead, n_spans, max_chars, &cut, &gaps);
  int w = n ? FM1_TFT_RUN_W(f->m.advance, f->m.ink_w, n) + gaps : 0;
  log_box(t, x, y, w, f->m.height, FM1_BOX_TEXT, (uint8_t)(f - k_faces));
  if (t->record && cut) ++t->truncated;
  int i = 0, at = x;
  for (int k = 0; k < n_spans && i < n; ++k) {
    const char *s = spans[k].s;
    if (lead && i && s && s[0]) at += lead[k];
    for (int j = 0; s && s[j] && i < n; ++j, ++i, at += f->m.advance) {
      draw_glyph(t, at, y, (unsigned char)s[j], f->glyphs, f->rows, f->cols, f->scale,
                 spans[k].color);
    }
  }
  return w;
}

int fm1_tft_span_text(fm1_tft_t *t, int x, int y, const fm1_tft_span_t *spans, int n_spans,
                      int max_chars, fm1_tft_font_t font) {
  return fm1_tft_span_text_lead(t, x, y, spans, NULL, n_spans, max_chars, font);
}

int fm1_tft_font_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars,
                      fm1_tft_font_t font, uint16_t color) {
  const fm1_tft_span_t span = { s, color };
  return fm1_tft_span_text(t, x, y, &span, 1, max_chars, font);
}

int fm1_tft_check_layout(const fm1_tft_t *t, int gap, int *report, int max_report) {
  int faults = 0;
  if (t->overflow) {
    if (report && faults < max_report) { report[2 * faults] = -1; report[2 * faults + 1] = -1; }
    ++faults;
  }
  for (int k = 0; k < t->truncated; ++k) {
    if (report && faults < max_report) { report[2 * faults] = -2; report[2 * faults + 1] = -2; }
    ++faults;
  }
  for (int i = 0; i < t->n_boxes; ++i) {
    const fm1_tft_box_t *a = &t->boxes[i];
    if (a->hidden) continue;
    if (a->x < 0 || a->y < 0 || a->x + a->w > FM1_TFT_W || a->y + a->h > FM1_TFT_H) {
      if (report && faults < max_report) { report[2 * faults] = i; report[2 * faults + 1] = i; }
      ++faults;
    }
    for (int j = i + 1; j < t->n_boxes; ++j) {
      const fm1_tft_box_t *b = &t->boxes[j];
      if (b->hidden) continue;
      if (a->kind == FM1_BOX_GRAPHIC && b->kind == FM1_BOX_GRAPHIC) continue;
      if (touches(a->x, a->y, a->w, a->h, b->x, b->y, b->w, b->h, gap)) {
        if (report && faults < max_report) { report[2 * faults] = i; report[2 * faults + 1] = j; }
        ++faults;
      }
    }
  }
  return faults;
}
