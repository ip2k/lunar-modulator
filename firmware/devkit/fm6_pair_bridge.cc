/* SPDX-License-Identifier: MIT. Offline bridge; no allocation or global ctor. */
#include "fm6_pair_bridge.h"
#include "fm6_pair_mailbox.h"
#include <new>

namespace {
alignas(64) unsigned char storage[sizeof(LunarFm6Mailbox)];
LunarFm6Mailbox *mailbox;
uint32_t (*direct_clock)(void);
uint32_t clock_bridge(void *) { return direct_clock(); }
int render_bridge(void *, fm1_dx7_kernel_job_t jobs[2]) {
  return mailbox->RenderPair(jobs);
}
const fm1_dx7_kernel_adapter_t adapter = {render_bridge, 0};
}

extern "C" int lunar_fm6_pair_init(uint32_t (*clock)(void), uint32_t budget) {
  if (mailbox || !clock || !budget || budget >= 0x80000000u) return 0;
  direct_clock = clock;
  mailbox = new (storage) LunarFm6Mailbox(clock_bridge, 0, budget);
  return 1;
}
extern "C" int lunar_fm6_pair_worker_step(void) {
  return mailbox ? mailbox->WorkerStep() : -1;
}
extern "C" const fm1_dx7_kernel_adapter_t *lunar_fm6_pair_adapter(void) {
  return mailbox ? &adapter : 0;
}
extern "C" unsigned lunar_fm6_pair_completed(void) {
  return mailbox ? mailbox->completed_pairs() : 0;
}
extern "C" int lunar_fm6_pair_disabled(void) {
  return !mailbox || mailbox->disabled();
}
