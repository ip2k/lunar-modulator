// editor_meta.cc -- the tables an editor reads beside the registries (stage
// ED0, notes/2026-10-06-web-editor.md §6): knob page names (fm1_engine_meta.h),
// the audio effects' groups, the refusal codes with their words
// (fm1_refusal.h) and the telemetry block's layout (fm1_tele.h). The panel
// reads the page names from here too, so the screen and the metadata export
// cannot disagree.
//
// Written as C in a C++11 file so every build that links the registry links
// it (fm1-render, the virtual FM-1, the JieLi object list). Constant data and
// snprintf-free formatting: no heap, no stdio, no libm. Our own code. MIT
// licence, like the rest of this repository.
#include <string.h>

#include "fm1_engine_meta.h"
#include "fm1_refusal.h"
#include "fm1_tele.h"

extern "C" {

// ---- Page names ----------------------------------------------------------------
// One row per module whose pages the panel names: the MIDI effects', on the ARP
// pages. The arpeggiator's follow its parameters' pages (midi_fx/arp_engine.c,
// after the options note §2.4); Acid Gen's (midi_fx/acid_gen.c, a GPL module
// built only with the GPL switch on) are named here all the same, since a name
// is no code of its.
namespace {
struct PageNames {
  const char *id;
  const char *names[8];
};
const PageNames kPageNames[] = {
  { "arp", { "PLAY", "RHYTHM", "CHANCE", "FEEL", "MORE", "KEYS", "SEED", NULL } },
  { "acid-gen", { "LINE", "KEY", "PLAY", "SEED", NULL, NULL, NULL, NULL } },
};
}  // namespace

const char *fm1_page_name(const char *id, unsigned page) {
  size_t i;
  unsigned k;
  for (i = 0; id && i < sizeof(kPageNames) / sizeof(kPageNames[0]); ++i) {
    if (strcmp(kPageNames[i].id, id) != 0) continue;
    for (k = 0; k <= page && k < 8u; ++k) {
      if (!kPageNames[i].names[k]) return NULL;
    }
    return page < 8u ? kPageNames[i].names[page] : NULL;
  }
  return NULL;
}

// ---- Effect groups ---------------------------------------------------------------
// As the project's page lists the effects (README.md, "The effects"); the test
// effects last. tests/test_engine_editor_meta.py checks every audio effect has one and
// that the page's lists agree.
const fm1_fx_group_t fm1_fx_groups[] = {
  { "reverb", "Reverbs" },
  { "space", "Chorus, space and delay" },
  { "filter", "Filters and EQ" },
  { "colour", "Grit and colour" },
  { "dynamics", "Dynamics" },
  { "test", "Tests" },
};
const size_t fm1_fx_group_count = sizeof(fm1_fx_groups) / sizeof(fm1_fx_groups[0]);

namespace {
struct FxGroup {
  const char *id;
  unsigned group;               // index into fm1_fx_groups
};
const FxGroup kFxGroups[] = {
  { "plate", 0 }, { "hall", 0 }, { "room", 0 }, { "sw-psxverb", 0 },
  { "ensemble", 1 }, { "diffuse", 1 }, { "echo", 1 },
  { "filter", 2 }, { "comb", 2 }, { "djfilter", 2 }, { "tilt", 2 }, { "isolator", 2 }, { "eq", 2 },
  { "drive", 3 }, { "crush", 3 }, { "fold", 3 }, { "sat", 3 },
  { "comp", 4 }, { "limit", 4 }, { "gate", 4 }, { "squash", 4 }, { "shaper", 4 },
  { "test-gain", 5 }, { "test-ext", 5 },
};
}  // namespace

const fm1_fx_group_t *fm1_fx_group_of(const char *id) {
  size_t i;
  for (i = 0; id && i < sizeof(kFxGroups) / sizeof(kFxGroups[0]); ++i) {
    if (strcmp(kFxGroups[i].id, id) == 0) return &fm1_fx_groups[kFxGroups[i].group];
  }
  return NULL;
}

// ---- Refusals ------------------------------------------------------------------
// The words the screen says where it says them (sim/web/src/fm1_app.c: "does not
// fit" with "needs 112% of RAM", "refuses 48000 Hz"); memory only as a
// percentage of the FM-1's budget (owner, 2026-10-06). {fills} are the values a
// refusal names, filled in by whoever shows it.
const fm1_refusal_t fm1_refusals[] = {
  { FM1_REFUSE_NOT_LUNAR, "NOT_LUNAR", "load", "Not a Lunar Modulator file", NULL },
  { FM1_REFUSE_TOO_NEW, "TOO_NEW", "load", "Made with a newer Lunar Modulator",
    "format {level}; this one reads {reads}" },
  { FM1_REFUSE_UNKNOWN, "UNKNOWN", "load", "Not in this build", "{name}: {why}" },
  { FM1_REFUSE_RATE, "RATE", "load,unit", "Cannot run at this rate", "refuses {rate} Hz" },
  { FM1_REFUSE_RAM, "RAM", "load,unit", "Does not fit", "needs {pct}% of RAM" },
  { FM1_REFUSE_NO_ROOM, "NO_ROOM", "load,rack,cable", "No room", "the {what} is full ({used} of {max})" },
  { FM1_REFUSE_TOO_BIG, "TOO_BIG", "load", "Too big to read", "over the limit for a {kind} file" },
  { FM1_REFUSE_BAD, "BAD", "load", "Cannot be read", "line {line}, column {col}: {what}" },
  { FM1_REFUSE_STOPPED, "STOPPED", "load", "Loading stopped", NULL },
  { FM1_REFUSE_ARENA, "ARENA", "unit", "Does not fit", "too large for its slot" },
  { FM1_REFUSE_NO_SOURCE, "NO_SOURCE", "cable", "No source", "nothing at {from}" },
  { FM1_REFUSE_NO_DEST, "NO_DEST", "cable", "No destination", "nothing at {to}" },
  { FM1_REFUSE_NOLOCK, "NOLOCK", "cable", "Cannot be modulated", "{param} rebuilds the voices" },
  { FM1_REFUSE_ENUM_NO_MOD, "ENUM_NO_MOD", "cable", "A list it cannot move",
    "{param} is a list that takes no cable" },
  { FM1_REFUSE_NO_MOD, "NO_MOD", "cable", "Takes no modulation", "{param} takes no cable" },
  { FM1_REFUSE_VOICE_TO_MONO, "VOICE_TO_MONO", "cable", "Per voice into one value",
    "poly never reaches mono" },
  { FM1_REFUSE_VOICE_TO_EFFECT, "VOICE_TO_EFFECT", "cable", "Per voice into an effect",
    "an effect plays every voice at once" },
  { FM1_REFUSE_UNIT_RESERVED, "UNIT_RESERVED", "cable", "Not a destination yet",
    "kept for a later version" },
  { FM1_REFUSE_VOICE_FULL, "VOICE_FULL", "cable", "Too many per-voice cables",
    "at most {max} parameters per voice" },
  { FM1_REFUSE_VOICE_ROOM, "VOICE_ROOM", "cable", "No room for voices",
    "the modules' voices do not fit" },
};
const size_t fm1_refusal_count = sizeof(fm1_refusals) / sizeof(fm1_refusals[0]);

const fm1_refusal_t *fm1_refusal_find(unsigned code) {
  size_t i;
  for (i = 0; i < fm1_refusal_count; ++i) {
    if (fm1_refusals[i].code == code) return &fm1_refusals[i];
  }
  return NULL;
}

const char *fm1_refusal_known_words(const char *reason) {
  if (!reason) return NULL;
  if (strcmp(reason, "gpl") == 0) return "in the GPL build only";
  if (strcmp(reason, "planned") == 0) return "not built yet";
  if (strcmp(reason, "retired") == 0) return "retired in {since}";
  if (strcmp(reason, "list") == 0) return "left out of this build";   // FM1_MODULES
  return NULL;
}

// ---- Telemetry ------------------------------------------------------------------
namespace {
// Floats and mask bits per section, in FM1_TELE_* order, as constants, so the
// table below is constant data (no constructor at start-up).
enum : unsigned {
  kPos = FM1_MOD_POSITIONS, kOuts = FM1_MOD_MAX_OUTS, kVoices = FM1_MOD_VOICES, kSlots = FM1_MOD_SLOTS,
  kN0 = FM1_TELE_POINTS * 2u,           // meters: peak, rms
  kN1 = FM1_TELE_REDUCERS,              // reduction: dB
  kN2 = kVoices * 2u,                   // voices: sound, note
  kN3 = kPos * kOuts * 3u,              // outs: value, min, max
  kN4 = kPos * kOuts * kVoices,         // voice_outs
  kN5 = kSlots,                         // dests
  kN6 = kSlots * kVoices,               // voice_dests
  kO1 = kN0, kO2 = kO1 + kN1, kO3 = kO2 + kN2, kO4 = kO3 + kN3, kO5 = kO4 + kN4, kO6 = kO5 + kN5,
  kFloats = kO6 + kN6,
  kB1 = FM1_TELE_POINTS, kB2 = kB1 + FM1_TELE_REDUCERS, kB3 = kB2 + kVoices, kB4 = kB3 + kPos,
  kB5 = kB4 + kPos, kB6 = kB5 + kSlots, kBits = kB6 + kSlots,
};
typedef char tele_mask_fits[kBits <= 32u * FM1_TELE_MASK_WORDS ? 1 : -1];
typedef char tele_offsets_fit[kFloats <= 0xFFFFu ? 1 : -1];

const fm1_tele_section_t kSections[FM1_TELE_SECTIONS] = {
  { "meters", "none", 0, FM1_TELE_POINTS, 1, 2, 0 },
  { "reduction", "db", kO1, FM1_TELE_REDUCERS, 1, 1, kB1 },
  { "voices", "none", kO2, kVoices, 1, 2, kB2 },
  { "outs", "port", kO3, kPos, kOuts, 3, kB3 },
  { "voice_outs", "port", kO4, kPos, kOuts, kVoices, kB4 },
  { "dests", "param", kO5, kSlots, 1, 1, kB5 },
  { "voice_dests", "param", kO6, kSlots, 1, kVoices, kB6 },
};

// "prefix" then n (1-based) into buf.
const char *numbered(const char *prefix, unsigned n, char *buf, size_t cap) {
  char digits[12];
  size_t len = strlen(prefix), d = 0, k;
  if (!buf || !cap) return "";
  do {
    digits[d++] = (char)('0' + n % 10u);
    n /= 10u;
  } while (n && d < sizeof(digits));
  if (len + d + 1 > cap) {
    buf[0] = 0;
    return buf;
  }
  memcpy(buf, prefix, len);
  for (k = 0; k < d; ++k) buf[len + k] = digits[d - 1 - k];
  buf[len + d] = 0;
  return buf;
}

const char *copy(const char *s, char *buf, size_t cap) {
  size_t len = strlen(s);
  if (!buf || !cap) return "";
  if (len + 1 > cap) len = 0;
  memcpy(buf, s, len);
  buf[len] = 0;
  return buf;
}

// A meter point or reduction row: "snd2", "snd2.fx1", "mix", "fx1", "out",
// "limiter".
const char *point_name(unsigned s, unsigned r, char *buf, size_t cap) {
  const unsigned per = s == FM1_TELE_METERS ? 1u + FM1_TELE_INSERTS : FM1_TELE_INSERTS;
  char tmp[16], num[12];
  if (r < FM1_TELE_SOUNDS * per) {
    const unsigned snd = r / per + 1u, at = r % per;
    const unsigned fx = s == FM1_TELE_METERS ? at : at + 1u;    // 0: the engine
    numbered("snd", snd, tmp, sizeof(tmp));
    if (fx) {
      size_t len = strlen(tmp);
      numbered(".fx", fx, num, sizeof(num));
      if (len + strlen(num) + 1 <= sizeof(tmp)) memcpy(tmp + len, num, strlen(num) + 1);
    }
    return copy(tmp, buf, cap);
  }
  r -= FM1_TELE_SOUNDS * per;
  if (s == FM1_TELE_METERS) {
    if (r == 0) return copy("mix", buf, cap);
    if (r <= FM1_TELE_MASTERS) return numbered("fx", r, buf, cap);
    return copy("out", buf, cap);
  }
  if (r < FM1_TELE_MASTERS) return numbered("fx", r + 1u, buf, cap);
  return copy("limiter", buf, cap);
}
}  // namespace

const fm1_tele_section_t *fm1_tele_section(unsigned s) {
  return s < FM1_TELE_SECTIONS ? &kSections[s] : NULL;
}

unsigned fm1_tele_floats(void) { return kFloats; }
unsigned fm1_tele_mask_bits(void) { return kBits; }

const char *fm1_tele_row_name(unsigned s, unsigned r, char *buf, size_t n) {
  const fm1_tele_section_t *sec = fm1_tele_section(s);
  if (!sec || r >= sec->rows) return copy("", buf, n);
  switch (s) {
    case FM1_TELE_METERS:
    case FM1_TELE_REDUCTION: return point_name(s, r, buf, n);
    case FM1_TELE_VOICES: return numbered("v", r + 1u, buf, n);
    case FM1_TELE_OUTS:
    case FM1_TELE_VOICE_OUTS: return numbered("pos", r + 1u, buf, n);
    default: return numbered("slot", r + 1u, buf, n);
  }
}

const char *fm1_tele_item_name(unsigned s, unsigned i, char *buf, size_t n) {
  const fm1_tele_section_t *sec = fm1_tele_section(s);
  if (!sec || i >= sec->items || sec->items == 1) return copy("", buf, n);
  return numbered("out", i + 1u, buf, n);
}

const char *fm1_tele_field_name(unsigned s, unsigned f, char *buf, size_t n) {
  static const char *const kMeter[] = { "peak", "rms" };
  static const char *const kVoice[] = { "sound", "note" };
  static const char *const kOut[] = { "value", "min", "max" };
  const fm1_tele_section_t *sec = fm1_tele_section(s);
  if (!sec || f >= sec->fields) return copy("", buf, n);
  switch (s) {
    case FM1_TELE_METERS: return copy(kMeter[f], buf, n);
    case FM1_TELE_REDUCTION: return copy("db", buf, n);
    case FM1_TELE_VOICES: return copy(kVoice[f], buf, n);
    case FM1_TELE_OUTS: return copy(kOut[f], buf, n);
    case FM1_TELE_DESTS: return copy("value", buf, n);
    default: return numbered("v", f + 1u, buf, n);         // voice_outs, voice_dests
  }
}

}  // extern "C"
