/* arp_engine.c -- the arpeggiator core (fm1_arp.h) as a MIDI effect of engine
 * API v3 (FM1_KIND_MIDI_FX, fm1_engine.h): its parameters as an engine's,
 * on the ARP pages of the options note (notes/2026-10-01-arp-modulation-
 * effects-options.md §2.4), and process() on the host's ticks.
 *
 * A parameter's value is the core's own integer, or, for a list, its entry
 * from 0 (OCTAVES, REPEAT and RATCHET count from 1 in the core). Values
 * round half up, and NaN is the default, so any float a host sends is a
 * value the core takes. No allocation, no libm. MIT licence, like the rest
 * of this repository.
 */
#include "fm1_arp.h"
#include "fm1_engine.h"

#include <string.h>

/* The core's event codes are the engine API's (fm1_midi_ev.h). */
typedef char arp_codes_match[(int)FM1_ARP_EV_NOTE_ON == (int)FM1_MIDI_EV_NOTE_ON &&
                             (int)FM1_ARP_EV_NOTE_OFF == (int)FM1_MIDI_EV_NOTE_OFF &&
                             (int)FM1_ARP_EV_SUSTAIN == (int)FM1_MIDI_EV_SUSTAIN &&
                             (int)FM1_ARP_EV_STEP == (int)FM1_MIDI_EV_STEP &&
                             (int)FM1_ARP_EV_RESET == (int)FM1_MIDI_EV_RESET &&
                             (int)FM1_ARP_EV_FLUSH == (int)FM1_MIDI_EV_FLUSH &&
                             (int)FM1_ARP_EV_PANIC == (int)FM1_MIDI_EV_PANIC &&
                             (int)FM1_ARP_EV_STOP == (int)FM1_MIDI_EV_STOP &&
                             FM1_ARP_OUT_MIN == FM1_MIDI_FX_OUT_MIN ? 1 : -1];

/* The list names, in the core's order (tests/test_engine_midi_fx.py checks
 * them against fm1-arp --list). */
static const char *const kModes[FM1_ARP_MODE_COUNT] = {
  "Up", "Down", "Up-Down", "Down-Up", "Up&Down", "Down&Up", "Converge", "Diverge",
  "Conv-Div", "Thumb Up", "Thumb Down", "Pinky Up", "Pinky Down", "Up Top Oct",
  "Down Low Oct", "Up Alt Oct", "Down Alt Oct", "Crawl", "Random", "Shuffle", "Walk", "Chord",
};
static const char *const kOrders[FM1_ARP_ORDER_COUNT] = { "Pitch", "Played", "Reverse" };
static const char *const kOctModes[FM1_ARP_OCT_COUNT] = { "Span", "Up", "Down", "Up-Down", "Random" };
static const char *const kRates[FM1_ARP_RATE_COUNT] = {
  "TRG", "1/32T", "1/32", "1/16T", "1/16", "1/8T", "1/16D", "1/8", "1/4T", "1/8D", "1/4",
  "1/2T", "1/4D", "1/2", "1/1T", "1/2D", "1/1",
};
static const char *const kCounts[8] = { "1", "2", "3", "4", "5", "6", "7", "8" };
static const char *const kPatterns[23] = {
  "All", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
  "17", "18", "19", "20", "21", "22",
};
static const char *const kOffOn[2] = { "Off", "On" };
static const char *const kJoin[2] = { "Now", "Next Pass" };
static const char *const kSync[2] = { "Free", "Key" };

/* Every parameter: the engine's view (name, type, range, default, page,
 * uid, flags, unit, abbreviation), the core's id, and the offset from the
 * engine's value to the core's. Pages after the options note §2.4: PLAY,
 * RHYTHM, CHANCE, FEEL, then MORE, KEYS and SEED for the rest. Knob order
 * is index order, so the table is in page order; uids are the core's id
 * plus 1 and never change. A list is read at the next step, so it is LATCH;
 * a number is LATCH and MOD, as the parameter rules want of a FLOAT (no
 * route reaches a MIDI effect yet).
 *
 * The core's SWING is not one of them: the arp swings by the set's swing,
 * which the host gives every call (fm1_midi_fx_ctx_t.swing; owner,
 * 2026-10-06). Its uid 7 is retired (tests/fixtures/param-uids.json), and
 * a file that still names the arp's "Swing" loads without it. */
#define ARP_N_PARAMS (FM1_ARP_P_COUNT - 1u)
#define L FM1_PARAM_LATCH
#define LM (FM1_PARAM_LATCH | FM1_PARAM_MOD)
enum { PAGE_PLAY, PAGE_RHYTHM, PAGE_CHANCE, PAGE_FEEL, PAGE_MORE, PAGE_KEYS, PAGE_SEED };

/* Where each parameter goes in the core: its id, and the core's value at
 * the engine's 0 (1 for the lists that count from 1). */
typedef struct {
  uint8_t id;      /* FM1_ARP_P_* */
  uint8_t base;
} arp_map_t;

static const fm1_param_t kParams[ARP_N_PARAMS] = {
  { "Mode", FM1_PARAM_ENUM, 0, FM1_ARP_MODE_COUNT - 1, 0, kModes, PAGE_PLAY, 1, L, FM1_UNIT_NONE, "MODE" },
  { "Rate", FM1_PARAM_ENUM, 0, FM1_ARP_RATE_COUNT - 1, 4, kRates, PAGE_PLAY, 5, L, FM1_UNIT_NONE, "RATE" },
  { "Gate", FM1_PARAM_FLOAT, 1, 200, 50, NULL, PAGE_PLAY, 6, LM, FM1_UNIT_PCT, "GATE" },
  { "Octaves", FM1_PARAM_ENUM, 0, FM1_ARP_MAX_OCTAVES - 1, 0, kCounts, PAGE_PLAY, 3, L, FM1_UNIT_NONE, "OCT" },
  { "Pattern", FM1_PARAM_ENUM, 0, 22, 0, kPatterns, PAGE_RHYTHM, 8, L, FM1_UNIT_NONE, "PATT" },
  { "Fill", FM1_PARAM_FLOAT, 0, 32, 0, NULL, PAGE_RHYTHM, 10, LM, FM1_UNIT_NONE, "FILL" },
  { "Rotate", FM1_PARAM_FLOAT, 0, 31, 0, NULL, PAGE_RHYTHM, 11, LM, FM1_UNIT_NONE, "ROT" },
  { "Length", FM1_PARAM_FLOAT, 0, 32, 0, NULL, PAGE_RHYTHM, 9, LM, FM1_UNIT_NONE, "LEN" },
  { "Chance", FM1_PARAM_FLOAT, 0, 100, 100, NULL, PAGE_CHANCE, 18, LM, FM1_UNIT_PCT, "CHNC" },
  { "Ratchet", FM1_PARAM_ENUM, 0, 3, 0, kCounts, PAGE_CHANCE, 16, L, FM1_UNIT_NONE, "RATCH" },
  { "Vel Spread", FM1_PARAM_FLOAT, 0, 127, 0, NULL, PAGE_CHANCE, 22, LM, FM1_UNIT_NONE, "SPRD" },
  { "Loop", FM1_PARAM_FLOAT, 0, 64, 0, NULL, PAGE_CHANCE, 24, LM, FM1_UNIT_NONE, "LOOP" },
  { "Oct Mode", FM1_PARAM_ENUM, 0, FM1_ARP_OCT_COUNT - 1, 0, kOctModes, PAGE_FEEL, 4, L, FM1_UNIT_NONE, "OCTM" },
  { "Velocity", FM1_PARAM_FLOAT, 0, 127, 0, NULL, PAGE_FEEL, 21, LM, FM1_UNIT_NONE, "VEL" },
  { "Join", FM1_PARAM_ENUM, 0, 1, 0, kJoin, PAGE_FEEL, 13, L, FM1_UNIT_NONE, "JOIN" },
  { "Order", FM1_PARAM_ENUM, 0, FM1_ARP_ORDER_COUNT - 1, 0, kOrders, PAGE_MORE, 2, L, FM1_UNIT_NONE, "ORDR" },
  { "Repeat", FM1_PARAM_ENUM, 0, 7, 0, kCounts, PAGE_MORE, 15, L, FM1_UNIT_NONE, "REPT" },
  { "Chord %", FM1_PARAM_FLOAT, 0, 100, 0, NULL, PAGE_MORE, 19, LM, FM1_UNIT_PCT, "CHRD" },
  { "Oct Jump", FM1_PARAM_FLOAT, 0, 100, 0, NULL, PAGE_MORE, 20, LM, FM1_UNIT_PCT, "JUMP" },
  { "Latch", FM1_PARAM_ENUM, 0, 1, 0, kOffOn, PAGE_KEYS, 12, L, FM1_UNIT_NONE, "LTCH" },
  { "Sync", FM1_PARAM_ENUM, 0, 1, 1, kSync, PAGE_KEYS, 14, L, FM1_UNIT_NONE, "SYNC" },
  { "Ratchet %", FM1_PARAM_FLOAT, 0, 100, 100, NULL, PAGE_KEYS, 17, LM, FM1_UNIT_PCT, "RAT%" },
  { "Gate Sprd", FM1_PARAM_FLOAT, 0, 100, 0, NULL, PAGE_KEYS, 23, LM, FM1_UNIT_NONE, "GSPR" },
  { "Seed", FM1_PARAM_FLOAT, 0, 65535, 0, NULL, PAGE_SEED, 25, LM, FM1_UNIT_NONE, "SEED" },
};

static const arp_map_t kMap[ARP_N_PARAMS] = {
  { FM1_ARP_P_MODE, 0 },
  { FM1_ARP_P_RATE, 0 },
  { FM1_ARP_P_GATE, 0 },
  { FM1_ARP_P_OCTAVES, 1 },
  { FM1_ARP_P_PATTERN, 0 },
  { FM1_ARP_P_EUCLID_FILL, 0 },
  { FM1_ARP_P_EUCLID_ROTATE, 0 },
  { FM1_ARP_P_EUCLID_LEN, 0 },
  { FM1_ARP_P_PROB, 0 },
  { FM1_ARP_P_RATCHET, 1 },
  { FM1_ARP_P_VEL_SPREAD, 0 },
  { FM1_ARP_P_LOOP, 0 },
  { FM1_ARP_P_OCT_MODE, 0 },
  { FM1_ARP_P_VELOCITY, 0 },
  { FM1_ARP_P_JOIN, 0 },
  { FM1_ARP_P_ORDER, 0 },
  { FM1_ARP_P_REPEAT, 1 },
  { FM1_ARP_P_CHORD_PROB, 0 },
  { FM1_ARP_P_OCT_JUMP, 0 },
  { FM1_ARP_P_LATCH, 0 },
  { FM1_ARP_P_SYNC, 0 },
  { FM1_ARP_P_RATCHET_PROB, 0 },
  { FM1_ARP_P_GATE_SPREAD, 0 },
  { FM1_ARP_P_SEED, 0 },
};
#undef L
#undef LM

/* An instance: the core, 8-byte aligned at the start of the host's memory. */
static size_t arp_size(const fm1_host_t *host) {
  (void)host;
  return (fm1_arp_size() + 15u) & ~(size_t)15u;
}

static void *arp_create(void *mem, const fm1_host_t *host) {
  (void)host;
  return fm1_arp_create(mem, FM1_MIDI_FX_PPQN);
}

static void arp_destroy(void *self) { (void)self; }

/* The core's integer for value v of the engine's parameter `index`: clamped
 * (NaN is the default), rounded half up, plus the list's base. */
static int core_value(unsigned index, float v) {
  v = fm1_param_clamp(&kParams[index], v);
  return (int)(v + 0.5f) + kMap[index].base;
}

static void arp_set_param(void *self, uint16_t index, float value) {
  if (index >= ARP_N_PARAMS) return;
  fm1_arp_set_param((fm1_arp_t *)self, kMap[index].id, core_value(index, value));
}

/* The block, on the host's ticks; while the sequencer runs, on its grid
 * (ctx->tick_pos), so the steps lock to the beat; swung by the set's swing
 * (the core clamps 0, an older host's, to 50: straight). */
static uint32_t arp_process(void *self, const fm1_midi_ev_t *in, uint32_t n_in,
                            const fm1_midi_fx_ctx_t *ctx, fm1_midi_ev_t *out, uint32_t cap) {
  if (ctx) fm1_arp_set_param((fm1_arp_t *)self, FM1_ARP_P_SWING, ctx->swing);
  return fm1_arp_process_at((fm1_arp_t *)self, in, n_in, ctx ? ctx->ticks : NULL,
                            ctx ? ctx->n_ticks : 0u, ctx && ctx->running, ctx ? ctx->tick_pos : 0u,
                            out, cap);
}

const fm1_midi_fx_t fm1_midi_fx_arp = {
  {
    FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_MIDI_FX,
    "arp", "Arp",
    "Lunar Modulator's arpeggiator (MIT): after Yarns' arpeggiator by Emilie Gillet (MIT), "
    "MCL's note orders by Justin Mammarella (BSD-3) and Super Arp's modifiers by "
    "Handcrafted Media (MIT); reimplemented, engines/midi_fx/CREDITS.md",
    kParams, ARP_N_PARAMS, 0,
    arp_size, arp_create, arp_destroy,
    NULL, NULL, NULL,         /* notes come through process() */
    arp_set_param, NULL,      /* no audio */
    NULL,                     /* no per-note offsets */
    0, NULL,                  /* no effect extension */
    0, 0,                     /* not a pad kit */
    NULL,                     /* API v4: no get_param, the host keeps its values */
  },
  arp_process,
};
