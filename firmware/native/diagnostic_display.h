/* SPDX-License-Identifier: MIT. Offline lease proof; no hardware binding. */
#ifndef LUNAR_DIAGNOSTIC_DISPLAY_H
#define LUNAR_DIAGNOSTIC_DISPLAY_H
#include <stddef.h>
#include <stdint.h>
#define LUNAR_DISPLAY_WIDTH 240u
#define LUNAR_DISPLAY_HEIGHT 240u
#define LUNAR_DISPLAY_ROW_BYTES (2u * LUNAR_DISPLAY_WIDTH)
enum { LUNAR_DISPLAY_UNBOUND = 0, LUNAR_DISPLAY_HOST_MOCK = 1 };
enum { LUNAR_DISPLAY_BIND = 1, LUNAR_DISPLAY_LEASE, LUNAR_DISPLAY_IO,
       LUNAR_DISPLAY_TIMEOUT };
/* Sole serialized owner. draw returns permanent native RGB565 pixels only
 * after a real redraw; NULL means no redraw. It must not draw elsewhere while
 * active. submit borrows row until matching successful completion, must not
 * reenter this object, and returns 1 only for an accepted mock submission.
 * No target completion/timeout/stop register sequence is supplied here. */
typedef const uint16_t *(*lunar_display_draw_fn)(void *, uint32_t min_frames);
typedef int (*lunar_display_submit_fn)(void *, uint32_t row, uint32_t ticket,
                                     const uint8_t *, size_t);
typedef struct {
  uint8_t row[LUNAR_DISPLAY_ROW_BYTES];
  const uint16_t *pixels;
  lunar_display_submit_fn submit;
  void *context;
  uint32_t initialized, active, pending, next_row, ticket, fault;
} lunar_diagnostic_display_t;
/* Fresh zeroed permanent object only. All non-mock bindings refuse. */
int lunar_display_init(lunar_diagnostic_display_t *, unsigned binding,
                       lunar_display_submit_fn, void *);
int lunar_display_frame(lunar_diagnostic_display_t *, lunar_display_draw_fn,
                        void *, uint32_t min_frames);
int lunar_display_pump(lunar_diagnostic_display_t *);
/* result: 0 pending, 1 completed, -1 uncertain/error. Error/timeout retain
 * leases forever. A faulted object cannot be reset or reinitialized. */
int lunar_display_complete(lunar_diagnostic_display_t *, uint32_t ticket, int result);
void lunar_display_timeout(lunar_diagnostic_display_t *);
#endif
