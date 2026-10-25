/* SPDX-License-Identifier: MIT. Offline CPU1 kernel handoff prototype. */
#ifndef LUNAR_FM6_PAIR_MAILBOX_H
#define LUNAR_FM6_PAIR_MAILBOX_H
#include "fm1_dx7_kernel.h"
#include <stdint.h>
#ifdef LUNAR_MAILBOX_HOST_TEST
#include <atomic>
typedef std::atomic<uint32_t> LunarMailboxWord;
#else
/* pi32v2 only: this is not a portable C++ memory model implementation. */
typedef volatile uint32_t LunarMailboxWord;
#endif

/* One audio caller, one permanently allocated worker. No reinitialization or
 * destruction while the worker may execute. A timeout permanently disables
 * submission; the late worker retains only this object's copied job. */
class alignas(64) LunarFm6Mailbox {
 public:
  typedef uint32_t (*Clock)(void *);
  LunarFm6Mailbox(Clock clock, void *context, uint32_t budget);
  int RenderPair(fm1_dx7_kernel_job_t jobs[2]);
  /* CPU1 calls repeatedly. Returns 0 for idle, 1 for a completed request. */
  int WorkerStep();
  bool disabled() const { return disabled_; } // Audio caller only.
  unsigned completed_pairs() const { return completed_; }
 private:
  LunarFm6Mailbox(const LunarFm6Mailbox &);
  LunarFm6Mailbox &operator=(const LunarFm6Mailbox &);
  LunarMailboxWord requested_, done_, ok_;
  fm1_dx7_kernel_job_t job_;
  Clock clock_;
  void *context_;
  uint32_t budget_;
  bool disabled_;
  unsigned completed_;
};
#endif
