/* SPDX-License-Identifier: MIT. Injected HOST proof, never an MMIO binding. */
#ifndef LUNAR_DIAGNOSTIC_SPI_MODEL_H
#define LUNAR_DIAGNOSTIC_SPI_MODEL_H
#ifndef LUNAR_DIAGNOSTIC_OFFLINE_PROOF
#error "SPI model has no admitted hardware completion contract"
#endif
#include <stddef.h>
#include <stdint.h>
typedef struct {
  /* Each operation is bounded and non-reentrant; 0 succeeds except launch
   * (1 accepted) and done (0 pending, 1 done). Negative means uncertain I/O.
   * launch borrows immutable bytes through observed completion. DONE is an
   * injected model assumption, NOT proof of target final SCK/quiescence. */
  int (*pins)(void *, int selected, int data);
  int (*clear_done)(void *);
  int (*done)(void *);
  int (*barrier)(void *);
  int (*launch)(void *, const uint8_t *, size_t);
  uint32_t (*ticks)(void *);
  void *ctx;
} lunar_spi_model_ops_t;
enum { LUNAR_SPI_CONFIG=1, LUNAR_SPI_LEASE, LUNAR_SPI_IO, LUNAR_SPI_TIMEOUT };
typedef struct {
  lunar_spi_model_ops_t ops;
  const uint8_t *row;
  uint8_t params[8];
  uint32_t initialized, active, fault, phase, transfer, ticket, stepping;
  uint32_t start, steps, max_steps, timeout_ticks;
} lunar_spi_model_t;
/* Fresh zeroed permanent storage, stable disjoint ops/context/row lifetime.
 * No init/retry/reset after a fault. Bounds are host test parameters. */
int lunar_spi_model_init(lunar_spi_model_t *, const lunar_spi_model_ops_t *,
                          uint32_t timeout_ticks, uint32_t max_steps);
int lunar_spi_model_submit(void *, uint32_t row, uint32_t ticket,
                            const uint8_t *, size_t);
/* One protocol operation per step, plus one clock observation. Returns 1
 * only after all six transfers and final deselect; writes completed ticket.
 * Error/timeout retains source leases and makes every later step inert. */
int lunar_spi_model_step(lunar_spi_model_t *, uint32_t *completed_ticket);
#endif
