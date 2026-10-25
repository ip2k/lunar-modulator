/* SPDX-License-Identifier: MIT. Offline only; no task or device operations. */
#include "fm6_pair_mailbox.h"

static void fence() {
#ifdef LUNAR_MAILBOX_HOST_TEST
  std::atomic_thread_fence(std::memory_order_seq_cst);
#else
  __asm__ volatile("csync;" ::: "memory");
#endif
}

LunarFm6Mailbox::LunarFm6Mailbox(Clock clock, void *context, uint32_t budget)
    : requested_(0), done_(0), ok_(0), job_(), clock_(clock), context_(context),
      budget_(budget), disabled_(!clock || !budget || budget >= 0x80000000u),
      completed_(0) {}

int LunarFm6Mailbox::RenderPair(fm1_dx7_kernel_job_t jobs[2]) {
  if (disabled_ || !jobs) return 0;
  const uint32_t start = clock_(context_);
  const uint32_t request = requested_ + 1u;
  job_ = jobs[1];
  fence();
  requested_ = request;
  /* Only the caller's first job is computed here. The worker never sees it. */
  if (!fm1_dx7_compute_kernel(&jobs[0])) { disabled_ = true; return 0; }
  unsigned polls = 0;
  for (;;) {
    /* Check the total deadline even when the worker has already completed. */
    if ((uint32_t)(clock_(context_) - start) >= budget_ || ++polls == 1000000u) {
      disabled_ = true;
      return 0;
    }
    if (done_ == request) break;
  }
  fence();
  if (!ok_) { disabled_ = true; return 0; }
  jobs[1] = job_;
  ++completed_;
  return 1;
}

int LunarFm6Mailbox::WorkerStep() {
  const uint32_t request = requested_;
  if (request == done_) return 0;
  fence();
  ok_ = fm1_dx7_compute_kernel(&job_) ? 1u : 0u;
  fence();
  done_ = request;
  /* After publishing done, do not access job_ until a new request arrives. */
  return 1;
}
