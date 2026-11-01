/* SPDX-License-Identifier: MIT. Host composition; no admitted target profile. */
#ifndef LUNAR_SELECTED_INTERACTIVE_OWNER_H
#define LUNAR_SELECTED_INTERACTIVE_OWNER_H
#ifndef LUNAR_SELECTED_INTERACTIVE_PROOF
#error "selected interactive composition is host proof only"
#endif
#include "diagnostic_transport.h"
#include "diagnostic_display.h"
#include "diagnostic_spi_model.h"
typedef struct {
  lunar_transport_t transport;
  lunar_diagnostic_display_t display;
  lunar_spi_model_t spi;
  lunar_spi_model_ops_t injected_spi;
  uint32_t initialized, max_events, min_draw_frames, stepping, audio_only;
} lunar_selected_owner_t;
/* All objects, callback contexts and queue storage are zeroed, permanent and
 * mutually disjoint. Caller serializes init/step; only matrix/encoder is the
 * single input producer and only audio is the single PCM consumer. No other
 * diagnostic/app API may run while this owner is live. Capacities/cadence are
 * host proof parameters, never inferred production defaults. */
int lunar_selected_owner_init(lunar_selected_owner_t *, lunar_input_t *, uint32_t,
    lunar_pcm_t *, uint32_t, uint32_t initial, uint32_t max_events,
    uint32_t min_draw_frames, const lunar_spi_model_ops_t *, uint32_t, uint32_t);
/* Explicit audio-only composition: no SPI callbacks or app draw. Permanent
 * storage and exclusive-owner rules above still apply. */
int lunar_selected_owner_init_audio(lunar_selected_owner_t *, lunar_input_t *, uint32_t,
    lunar_pcm_t *, uint32_t, uint32_t initial, uint32_t max_events);
int lunar_selected_owner_step(lunar_selected_owner_t *);
/* Host injected platform. Callbacks cannot reenter; init executes before
 * either simulated IRQ is enabled. scan_tick must call the accepted-event
 * capture functions below, never poll aggregate masks or invoke the app.
 * No MMIO, interrupt registration, ROM, storage or service implementation. */
typedef struct {
  int (*scan_init)(void *);
  void (*scan_tick)(void *);
  int (*audio_start)(void *);
  void *ctx;
} lunar_selected_platform_ops_t;
typedef struct {
  lunar_selected_owner_t owner;
  lunar_selected_platform_ops_t ops;
  /* CPU0 main/normal-IRQ control state; no CPU1/thread contract. */
  volatile uint32_t initialized, started, scan, preparing;
} lunar_selected_platform_t;
int lunar_selected_platform_start(lunar_selected_platform_t *,
    const lunar_selected_platform_ops_t *, lunar_input_t *, uint32_t,
    lunar_pcm_t *, uint32_t, uint32_t initial, uint32_t max_events,
    uint32_t min_draw_frames, const lunar_spi_model_ops_t *, uint32_t, uint32_t);
/* Prepare, never enable DMA/IRQs. audio_prepare may synchronously consume the
 * first queued block and produce the remaining bounded startup blocks through
 * this same owner. On return started means facade-ready, not DMA-running.
 * IRQ access/reentry during preparation poisons the attempt. */
typedef struct {
  int (*scan_init)(void *);
  void (*scan_tick)(void *);
  int (*audio_prepare)(void *);
  void *ctx;
} lunar_selected_audio_prepare_ops_t;
int lunar_selected_platform_prepare_audio(lunar_selected_platform_t *,
    const lunar_selected_audio_prepare_ops_t *, lunar_input_t *, uint32_t,
    lunar_pcm_t *, uint32_t, uint32_t initial, uint32_t max_events);
int lunar_selected_platform_main(lunar_selected_platform_t *);
void lunar_selected_platform_timer(lunar_selected_platform_t *);
int lunar_selected_platform_audio(lunar_selected_platform_t *, int32_t *);
void lunar_selected_platform_matrix(lunar_selected_platform_t *, unsigned id, int down);
void lunar_selected_platform_encoder(lunar_selected_platform_t *, unsigned id, int delta);
#endif
