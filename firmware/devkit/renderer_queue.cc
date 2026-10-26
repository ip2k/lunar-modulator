/* SPDX-License-Identifier: MIT. No tasks, allocation or device operations. */
#include "renderer_queue.h"

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
  recording_ = true;
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
}

bool LunarRendererQueue::Dispatch() {
  if (disabled()) return false;
  if (!recording_) return Refuse(State);
  recording_ = false;
  const uint32_t start = clock_(context_);
  const uint32_t request = requested_ + 1u;
  queue_fence();
  requested_ = request;
  for (unsigned s = 0; s < kSounds; ++s) if (s != 1) Execute(s);
  unsigned polls = 0;
  for (;;) {
    if ((uint32_t)(clock_(context_) - start) >= budget_) return Refuse(Deadline);
    if (++polls == 1000000u) return Refuse(Polls);
    if (done_ == request) break;
  }
  queue_fence();
  ++completed_;
  return true;
}

int LunarRendererQueue::WorkerStep() {
  const uint32_t request = requested_;
  if (request == done_) return 0;
  queue_fence();
  Execute(1);
  queue_fence();
  done_ = request;
  /* No stream or instance access after acknowledgement until next request. */
  return 1;
}
