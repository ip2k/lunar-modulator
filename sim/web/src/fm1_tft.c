/* fm1_tft.c -- the virtual FM-1's frame buffer (fm1_tft.h). MIT licence. */
#include "fm1_tft.h"

#include "fm1_font.h"

#include <stdint.h>

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static void log_box(fm1_tft_t *t, int x, int y, int w, int h, uint8_t kind) {
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
  log_box(t, x, y, w, h, FM1_BOX_GRAPHIC);
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

int fm1_tft_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars, int scale,
                 uint16_t color) {
  int n = text_len(s, max_chars);
  int w = fm1_tft_text_width(s, n, scale);
  log_box(t, x, y, w, FM1_TFT_TEXT_H(scale), FM1_BOX_TEXT);
  if (t->record && s[n]) ++t->truncated;
  for (int i = 0; i < n; ++i) {
    int c = (unsigned char)s[i];
    if (c < FM1_FONT_FIRST || c > FM1_FONT_LAST) c = '?';
    const uint8_t *g = fm1_font5x9[c - FM1_FONT_FIRST];
    int gx = x + i * FM1_TFT_ADVANCE(scale);
    for (int r = 0; r < FM1_FONT_ROWS; ++r) {
      for (int col = 0; col < FM1_FONT_COLS; ++col) {
        if (g[r] & (1u << (FM1_FONT_COLS - 1 - col))) {
          fm1_tft_paint(t, gx + col * scale, y + r * scale, scale, scale, color);
        }
      }
    }
  }
  return w;
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
