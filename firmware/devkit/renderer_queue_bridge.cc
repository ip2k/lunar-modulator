/* SPDX-License-Identifier: MIT. Permanent storage, no heap/global constructor. */
#include "renderer_queue_bridge.h"
#include "renderer_queue.h"
#include <new>

static_assert(static_cast<unsigned>(LunarRendererQueue::Render) == LUNAR_QUEUE_RENDER &&
    static_cast<unsigned>(LunarRendererQueue::NoteOn) == LUNAR_QUEUE_NOTE_ON &&
    static_cast<unsigned>(LunarRendererQueue::NoteOff) == LUNAR_QUEUE_NOTE_OFF &&
    static_cast<unsigned>(LunarRendererQueue::SetParam) == LUNAR_QUEUE_SET_PARAM &&
    static_cast<unsigned>(LunarRendererQueue::Bend) == LUNAR_QUEUE_BEND &&
    static_cast<unsigned>(LunarRendererQueue::SetNote) == LUNAR_QUEUE_SET_NOTE,
    "C command kinds must match the queue protocol");
namespace {
alignas(64) unsigned char storage[sizeof(LunarRendererQueue)];
LunarRendererQueue *queue;
uint32_t (*direct_clock)(void);
uint32_t clock_bridge(void *) { return direct_clock(); }
}
extern "C" int lunar_renderer_queue_init(uint32_t (*clock)(void), uint32_t budget) {
  if (queue || !clock || !budget || budget >= 0x80000000u) return 0;
  direct_clock = clock;
  queue = new (storage) LunarRendererQueue(clock_bridge, 0, budget);
  return 1;
}
extern "C" int lunar_renderer_queue_begin(void) { return queue && queue->Begin(); }
extern "C" int lunar_renderer_queue_push(unsigned sound, const fm1_engine_t *engine,
    void *instance, unsigned kind, float *output, unsigned frames, unsigned index,
    unsigned key, unsigned velocity, float value) {
  if (!queue) return 0;
  /* Validate BEFORE narrowing: a malformed command must permanently refuse the
   * batch rather than aliasing another note/parameter or enum value. */
  LunarRendererQueue::Op op = {};
  if (kind > LUNAR_QUEUE_SET_NOTE || index > UINT16_MAX || key > UINT8_MAX || velocity > UINT8_MAX)
    op.kind = static_cast<LunarRendererQueue::Kind>(LUNAR_QUEUE_SET_NOTE + 1);
  else
    op.kind = static_cast<LunarRendererQueue::Kind>(kind);
  op.output = output;
  op.frames = frames;
  op.index = static_cast<uint16_t>(index);
  op.key = static_cast<uint8_t>(key);
  op.velocity = static_cast<uint8_t>(velocity);
  op.value = value;
  return queue->Push(sound, engine, instance, op);
}
extern "C" int lunar_renderer_queue_dispatch(void) { return queue && queue->Dispatch(); }
extern "C" unsigned lunar_renderer_queue_completed(void) { return queue ? queue->completed() : 0; }
extern "C" unsigned lunar_renderer_queue_error(void) {
  return queue ? static_cast<unsigned>(queue->error()) : static_cast<unsigned>(LunarRendererQueue::Configuration);
}
extern "C" unsigned lunar_renderer_queue_peak(unsigned sound) { return queue ? queue->peak(sound) : 0; }
extern "C" int lunar_renderer_queue_worker_step(void) { return queue ? queue->WorkerStep() : -1; }

#ifdef LUNAR_QUEUE_PROFILE
extern "C" int lunar_renderer_queue_profile_read(uint32_t start, uint32_t end, uint32_t ticks[6]) {
  return queue && queue->ProfileRead(start, end, ticks);
}
#endif
