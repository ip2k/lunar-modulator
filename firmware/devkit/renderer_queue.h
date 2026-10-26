/* SPDX-License-Identifier: MIT. Offline whole-engine scheduling experiment. */
#ifndef LUNAR_RENDERER_QUEUE_H
#define LUNAR_RENDERER_QUEUE_H
#include "fm1_engine.h"
#include <stdint.h>
#ifdef LUNAR_QUEUE_HOST_TEST
#include <atomic>
typedef std::atomic<uint32_t> LunarQueueWord;
#else
/* pi32v2 publication only; not a portable C++ memory model implementation. */
typedef volatile uint32_t LunarQueueWord;
#endif

/* One caller records four independent sound streams. One permanent worker
 * executes sound 1 (also sound 2 with LUNAR_QUEUE_WORKER_DRUMS); the caller
 * executes the others. Each stream executes once in sound order on its owner.
 * Callbacks, engine state and
 * output buffers must remain alive and exclusively owned through completion.
 * In particular, the selected engines must not share mutable global state.
 * No device integration or engine/model independence is established here. */
class alignas(64) LunarRendererQueue {
 public:
  enum { kSounds = 4, kCapacity = 128, kMaxFrames = 64 };
  enum Kind { Render, NoteOn, NoteOff, SetParam, Bend, SetNote };
  enum Error { None, Configuration, State, Command, Capacity, Deadline, Polls };
  struct Op {
    float *output;
    uint32_t frames;
    float value;
    uint16_t index;
    uint8_t key, velocity;
    Kind kind;
  };
  typedef uint32_t (*Clock)(void *);
  LunarRendererQueue(Clock clock, void *context, uint32_t budget);
  bool Begin();
  bool Push(unsigned sound, const fm1_engine_t *engine, void *instance, const Op &op);
  bool Dispatch();
  int WorkerStep();
  bool disabled() const { return error_ != None; } // Caller only.
  Error error() const { return error_; }
  unsigned completed() const { return completed_; }
  unsigned peak(unsigned sound) const { return sound < kSounds ? peak_[sound] : 0; }
 private:
  LunarRendererQueue(const LunarRendererQueue &);
  LunarRendererQueue &operator=(const LunarRendererQueue &);
  struct Stream { const fm1_engine_t *engine; void *instance; unsigned count; Op ops[kCapacity]; };
  void Execute(unsigned sound);
  bool Refuse(Error error);
  LunarQueueWord requested_, done_;
  Stream streams_[kSounds];
  Clock clock_;
  void *context_;
  uint32_t budget_;
  Error error_;
  bool recording_;
  unsigned completed_, peak_[kSounds];
};
#endif
