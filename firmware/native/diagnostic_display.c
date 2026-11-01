/* SPDX-License-Identifier: MIT */
#include "diagnostic_display.h"

static int refuse(lunar_diagnostic_display_t *d, uint32_t why) {
  if (!d->fault) d->fault = why;
  return -1;
}
int lunar_display_init(lunar_diagnostic_display_t *d, unsigned binding,
                       lunar_display_submit_fn submit, void *context) {
  if (!d) return -1;
  if (d->initialized || d->fault) return refuse(d, LUNAR_DISPLAY_BIND);
  d->initialized = 1;
  if (binding != LUNAR_DISPLAY_HOST_MOCK || !submit)
    return refuse(d, LUNAR_DISPLAY_BIND);
  d->submit = submit;
  d->context = context;
  return 0;
}
int lunar_display_frame(lunar_diagnostic_display_t *d, lunar_display_draw_fn draw,
                        void *context, uint32_t min_frames) {
  if (!d || !d->initialized || d->fault) return -1;
  if (d->active || d->pending) return 0; /* no callback: pixels remain frozen */
  if (!draw) return refuse(d, LUNAR_DISPLAY_BIND);
  const uint16_t *pixels = draw(context, min_frames);
  if (!pixels) return 0;
  d->pixels = pixels;
  d->next_row = 0;
  d->active = 1;
  return 1;
}
int lunar_display_pump(lunar_diagnostic_display_t *d) {
  if (!d || !d->initialized || d->fault) return -1;
  if (!d->active || d->pending) return 0;
  if (!d->pixels || d->next_row >= LUNAR_DISPLAY_HEIGHT)
    return refuse(d, LUNAR_DISPLAY_LEASE);
  const uint16_t *pixels = d->pixels + d->next_row * LUNAR_DISPLAY_WIDTH;
  for (uint32_t x = 0; x < LUNAR_DISPLAY_WIDTH; ++x) {
    d->row[2u*x] = (uint8_t)(pixels[x] >> 8);
    d->row[2u*x+1u] = (uint8_t)pixels[x];
  }
  ++d->ticket; /* modulo 2^32; one outstanding lease, including ticket zero */
  d->pending = 1; /* publish lease before mock transport borrows the bytes */
  if (d->submit(d->context, d->next_row, d->ticket, d->row, sizeof d->row) != 1)
    return refuse(d, LUNAR_DISPLAY_IO); /* cannot prove transport quiescence */
  return 1;
}
int lunar_display_complete(lunar_diagnostic_display_t *d, uint32_t ticket, int result) {
  if (!d || !d->initialized || d->fault) return -1;
  if (!d->pending || ticket != d->ticket)
    return refuse(d, LUNAR_DISPLAY_LEASE);
  if (!result) return 0;
  if (result != 1) return refuse(d, LUNAR_DISPLAY_IO);
  d->pending = 0;
  if (++d->next_row == LUNAR_DISPLAY_HEIGHT) {
    d->active = 0;
    d->pixels = 0;
  }
  return 1;
}
void lunar_display_timeout(lunar_diagnostic_display_t *d) {
  if (d) (void)refuse(d, LUNAR_DISPLAY_TIMEOUT);
}
