/* SPDX-License-Identifier: MIT. Offline SPSC proof, no target atomic binding. */
#ifndef LUNAR_DIAGNOSTIC_TRANSPORT_H
#define LUNAR_DIAGNOSTIC_TRANSPORT_H
#ifndef LUNAR_DIAGNOSTIC_OFFLINE_PROOF
#error "transport has no admitted target timing or atomic implementation"
#endif
#include <stdint.h>
#include <stdatomic.h>
#define LUNAR_PCM_FRAMES 64u
#define LUNAR_PCM_WORDS (2u * LUNAR_PCM_FRAMES)
enum { LUNAR_INPUT_KEY, LUNAR_INPUT_BUTTON, LUNAR_INPUT_ENCODER };
enum { LUNAR_TRANSPORT_CONFIG=1, LUNAR_TRANSPORT_INPUT,
       LUNAR_TRANSPORT_OVERFLOW, LUNAR_TRANSPORT_LEASE,
       LUNAR_TRANSPORT_APP };
typedef struct { uint32_t scan; uint8_t kind, id; int16_t value; } lunar_input_t;
typedef struct { int32_t word[LUNAR_PCM_WORDS]; } lunar_pcm_t;
typedef struct {
  lunar_input_t *input;
  lunar_pcm_t *pcm;
  uint32_t input_capacity, pcm_capacity, initialized;
  _Atomic uint32_t input_head, input_tail, pcm_head, pcm_tail, fault, underruns;
  uint32_t leased, ticket; /* sole main owner; IRQ never reads these */
} lunar_transport_t;
/* All storage is caller-owned permanent memory. Power-of-two capacities are
 * offline test parameters, not release queue defaults. initial tests wrap. */
int lunar_transport_init(lunar_transport_t *, lunar_input_t *, uint32_t,
                         lunar_pcm_t *, uint32_t, uint32_t initial);
/* One ordered input producer; scan is provenance, never used to reorder.
 * Matrix IDs: buttons 0..13, notes 14..40 => app key 0..26. */
int lunar_transport_matrix(lunar_transport_t *, uint32_t scan, unsigned id, int down);
int lunar_transport_encoder(lunar_transport_t *, uint32_t scan, unsigned id, int delta);
/* Sole main owner. Reserve is backpressure (0), not loss; no publication until
 * complete. The returned slot must not be touched after publish. */
int lunar_transport_reserve(lunar_transport_t *, int32_t **, uint32_t *ticket);
int lunar_transport_publish(lunar_transport_t *, uint32_t ticket);
typedef int (*lunar_input_apply_fn)(void *, const lunar_input_t *);
typedef int (*lunar_pcm_render_fn)(void *, int32_t *);
int lunar_transport_produce(lunar_transport_t *, uint32_t max_events,
                            lunar_input_apply_fn, lunar_pcm_render_fn, void *);
/* Only copies immutable, published PCM or zeroes. No app call, render, draw,
 * allocation, wait or hardware access. Fault retains unpublished leases. */
int lunar_transport_irq(lunar_transport_t *, int32_t out[LUNAR_PCM_WORDS]);
void lunar_transport_fault(lunar_transport_t *, uint32_t reason);
#endif
