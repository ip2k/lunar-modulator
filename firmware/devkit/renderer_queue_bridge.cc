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

#ifdef LUNAR_QUEUE_DETAIL
namespace {
uint32_t detail_ticks[LUNAR_QUEUE_DETAILS], detail_start, detail_seen;
unsigned detail_active;
bool detail_valid;
}
extern "C" void lunar_renderer_queue_detail_reset(void) {
  for (unsigned i = 0; i < LUNAR_QUEUE_DETAILS; ++i) detail_ticks[i] = 0;
  detail_seen = 0;
  detail_active = LUNAR_QUEUE_DETAILS;
  detail_valid = queue && direct_clock;
}
extern "C" void lunar_renderer_queue_detail_mark(unsigned region, int entering) {
  if (!detail_valid) return;
  const uint32_t tick = direct_clock();
  if (region >= LUNAR_QUEUE_DETAILS || (entering != 0 && entering != 1) ||
      (entering ? detail_active != LUNAR_QUEUE_DETAILS : detail_active != region)) {
    detail_valid = false;
    return;
  }
  if (entering) {
    detail_active = region;
    detail_start = tick;
  } else {
    const uint32_t elapsed = tick - detail_start;
    if (elapsed >= 0x80000000u || UINT32_MAX - detail_ticks[region] < elapsed) {
      detail_valid = false;
      return;
    }
    detail_ticks[region] += elapsed;
    detail_seen |= 1u << region;
    detail_active = LUNAR_QUEUE_DETAILS;
  }
}
extern "C" int lunar_renderer_queue_detail_read(uint32_t ticks[LUNAR_QUEUE_DETAILS]) {
  if (!detail_valid || detail_active != LUNAR_QUEUE_DETAILS ||
      detail_seen != (1u << LUNAR_QUEUE_DETAILS) - 1 || !ticks ||
      lunar_renderer_queue_error()) {
    detail_valid = false;
    return 0;
  }
  for (unsigned i = 0; i < LUNAR_QUEUE_DETAILS; ++i) ticks[i] = detail_ticks[i];
  detail_valid = false; // Exactly one read per completed outer block.
  return 1;
}
#endif

#ifdef LUNAR_QUEUE_MICRO
namespace {
uint32_t micro_ticks[LUNAR_QUEUE_MICROS], micro_calls[LUNAR_QUEUE_MICROS], micro_start;
unsigned micro_active;
bool micro_valid;
}
extern "C" void lunar_renderer_queue_micro_reset(void) {
  for (unsigned i = 0; i < LUNAR_QUEUE_MICROS; ++i) micro_ticks[i] = micro_calls[i] = 0;
  micro_active = LUNAR_QUEUE_MICROS;
  micro_valid = queue && direct_clock;
}
extern "C" void lunar_renderer_queue_micro_mark(unsigned region, int entering) {
  if (!micro_valid) return;
  const uint32_t tick = direct_clock();
  if (region >= LUNAR_QUEUE_MICROS || (entering != 0 && entering != 1) ||
      (entering ? micro_active != LUNAR_QUEUE_MICROS : micro_active != region)) {
    micro_valid = false;
    return;
  }
  if (entering) {
    micro_active = region;
    micro_start = tick;
  } else {
    const uint32_t elapsed = tick - micro_start;
    if (elapsed >= 0x80000000u || UINT32_MAX - micro_ticks[region] < elapsed ||
        micro_calls[region] == UINT32_MAX) {
      micro_valid = false;
      return;
    }
    micro_ticks[region] += elapsed;
    ++micro_calls[region];
    micro_active = LUNAR_QUEUE_MICROS;
  }
}
extern "C" int lunar_renderer_queue_micro_read(uint32_t ticks[LUNAR_QUEUE_MICROS],
                                               uint32_t calls[LUNAR_QUEUE_MICROS]) {
  if (!micro_valid || micro_active != LUNAR_QUEUE_MICROS || !ticks || !calls ||
      lunar_renderer_queue_error()) {
    micro_valid = false;
    return 0;
  }
  for (unsigned i = 0; i < LUNAR_QUEUE_MICROS; ++i) {
    ticks[i] = micro_ticks[i];
    calls[i] = micro_calls[i];
  }
  micro_valid = false; // Exactly one read per completed outer block.
  return 1;
}
#endif
