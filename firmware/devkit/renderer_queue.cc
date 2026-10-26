/* SPDX-License-Identifier: MIT. No tasks, allocation or device operations. */
#include "renderer_queue.h"

static bool worker_sound(unsigned sound) {
#ifdef LUNAR_QUEUE_WORKER_DRUMS
  return sound == 1 || sound == 2;
#else
  return sound == 1;
#endif
}

static void queue_fence() {
#ifdef LUNAR_QUEUE_HOST_TEST
  std::atomic_thread_fence(std::memory_order_seq_cst);
#else
  __asm__ volatile("csync;" ::: "memory");
#endif
}

LunarRendererQueue::LunarRendererQueue(Clock clock, void *context, uint32_t budget)
    : requested_(0), done_(0), streams_(), clock_(clock), context_(context),
      budget_(budget), error_(None), recording_(false), completed_(0), peak_() {
#ifdef LUNAR_QUEUE_PROFILE
  record_start_ = publish_start_ = caller_end_ = dispatch_end_ = worker_ticks_ = 0;
  profiled_completed_ = 0;
#endif
#ifdef LUNAR_QUEUE_POST
  post_ = 0;
  post_context_ = 0;
#endif
  if (!clock || !budget || budget >= 0x80000000u) error_ = Configuration;
}

bool LunarRendererQueue::Refuse(Error error) {
  /* Permanent refusal: even a late acknowledgement never permits reuse. */
  if (error_ == None) error_ = error;
  return false;
}

bool LunarRendererQueue::Begin() {
  if (disabled()) return false;
  if (recording_ || requested_ != done_) return Refuse(State);
  queue_fence();
  for (unsigned s = 0; s < kSounds; ++s) {
    streams_[s].engine = 0;
    streams_[s].instance = 0;
    streams_[s].count = 0;
  }
#ifdef LUNAR_QUEUE_POST
  post_ = 0;
  post_context_ = 0;
#endif
  recording_ = true;
#ifdef LUNAR_QUEUE_PROFILE
  record_start_ = clock_(context_);
#endif
  return true;
}

bool LunarRendererQueue::Push(unsigned sound, const fm1_engine_t *e, void *instance, const Op &op) {
  if (disabled()) return false;
  if (!recording_) return Refuse(State);
  if (sound >= kSounds || !e || !instance || e->kind != FM1_KIND_SOUND ||
      (op.kind == Render && (!e->render || !op.output || !op.frames || op.frames > kMaxFrames)) ||
      (op.kind == NoteOn && !e->note_on) || (op.kind == NoteOff && !e->note_off) ||
      (op.kind == SetParam && !e->set_param) || op.kind < Render || op.kind > SetNote)
    return Refuse(Command);
  Stream &s = streams_[sound];
  if (s.count && (s.engine != e || s.instance != instance)) return Refuse(Command);
  if (s.count == kCapacity) return Refuse(Capacity);
  s.engine = e;
  s.instance = instance;
  s.ops[s.count++] = op;
  if (peak_[sound] < s.count) peak_[sound] = s.count;
  return true;
}

#ifdef LUNAR_QUEUE_POST
bool LunarRendererQueue::SetPost(unsigned sound, Post callback, void *context) {
  if (disabled()) return false;
  if (!recording_ || sound != 1 || !callback || !context || post_) return Refuse(Command);
  post_ = callback;
  post_context_ = context;
  return true;
}
#endif

void LunarRendererQueue::Execute(unsigned sound) {
  const Stream &s = streams_[sound];
  const fm1_engine_t *e = s.engine;
  for (unsigned i = 0; i < s.count; ++i) {
    const Op &op = s.ops[i];
    switch (op.kind) {
      case Render: e->render(s.instance, op.output, op.frames); break;
      case NoteOn: e->note_on(s.instance, op.key, op.velocity); break;
      case NoteOff: e->note_off(s.instance, op.key); break;
      case SetParam: e->set_param(s.instance, op.index, op.value); break;
      case Bend: if (e->pitch_bend) e->pitch_bend(s.instance, op.value); break;
      case SetNote: if (e->set_param_note) e->set_param_note(s.instance, op.key, op.index, op.value); break;
    }
  }
#ifdef LUNAR_QUEUE_POST
  if (sound == 1 && post_) post_(post_context_, sound);
#endif
}

bool LunarRendererQueue::Dispatch() {
  if (disabled()) return false;
  if (!recording_) return Refuse(State);
  recording_ = false;
  const uint32_t start = clock_(context_);
#ifdef LUNAR_QUEUE_PROFILE
  publish_start_ = start;
#endif
  const uint32_t request = requested_ + 1u;
  queue_fence();
  requested_ = request;
  for (unsigned s = 0; s < kSounds; ++s) if (!worker_sound(s)) Execute(s);
#ifdef LUNAR_QUEUE_PROFILE
  caller_end_ = clock_(context_);
#endif
  unsigned polls = 0;
  for (;;) {
    if ((uint32_t)(clock_(context_) - start) >= budget_) return Refuse(Deadline);
    if (++polls == 1000000u) return Refuse(Polls);
    if (done_ == request) break;
  }
  queue_fence();
#ifdef LUNAR_QUEUE_PROFILE
  dispatch_end_ = clock_(context_);
#endif
  ++completed_;
  return true;
}

int LunarRendererQueue::WorkerStep() {
  const uint32_t request = requested_;
  if (request == done_) return 0;
  queue_fence();
#ifdef LUNAR_QUEUE_PROFILE
  const uint32_t start = clock_(context_);
#endif
  for (unsigned s = 0; s < kSounds; ++s) if (worker_sound(s)) Execute(s);
#ifdef LUNAR_QUEUE_PROFILE
  worker_ticks_ = clock_(context_) - start;
#endif
  queue_fence();
  done_ = request;
  /* No stream or instance access after acknowledgement until next request. */
  return 1;
}

#ifdef LUNAR_QUEUE_PROFILE
bool LunarRendererQueue::ProfileRead(uint32_t outer_start, uint32_t outer_end,
                                     uint32_t ticks[6]) {
  if (!ticks || disabled() || recording_ || !completed_ ||
      completed_ != profiled_completed_ + 1u || requested_ != done_) return false;
  /* Dispatch already acquired the worker ACK. CPU1 cannot write its next
   * duration until CPU0 publishes another batch; no idle polling clock reads. */
  ticks[0] = record_start_ - outer_start;
  ticks[1] = publish_start_ - record_start_;
  ticks[2] = caller_end_ - publish_start_;
  ticks[3] = dispatch_end_ - caller_end_;
  ticks[4] = outer_end - dispatch_end_;
  ticks[5] = worker_ticks_;
  profiled_completed_ = completed_;
  return true;
}
#endif
