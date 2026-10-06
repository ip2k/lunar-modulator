/* fm1_arp.h -- the arpeggiator core of Lunar Modulator, open firmware for the
 * M-VAVE FM-1 (options note 2026-10-01 §2; engines/midi_fx/README.md).
 *
 * A heap-free C99 arpeggiator on note events. Its loop follows Yarns'
 * `Part::ClockArpeggiator` (Emilie Gillet, MIT; yarns/part.cc 366-446 at
 * pichenettes/eurorack 08460a6): directions, octave range, 22 rhythm masks,
 * Euclidean length, fill and rotate, gate counted in clock ticks, latch. It
 * adds the note orders of MCL's `ArpSeqTrack` (Justin Mammarella, BSD-3) and
 * its trig-stepped rate, and seeded, loopable random modifiers after Super
 * Arp (Handcrafted Media, MIT). It is a reimplementation, not a port: no
 * upstream code is compiled here, and randomness comes from our own seeded,
 * counter-based generator, never stmlib's global `Random`. CREDITS.md holds
 * the three notices.
 *
 * Time. The core has no tempo and counts no samples. The host supplies clock
 * ticks (24, 48 or 96 per quarter note, fixed at create) and the core counts
 * steps in ticks; in RATE TRG the host supplies the steps themselves
 * (FM1_ARP_EV_STEP, MCL's ARP_RATE_TRIG). While the host's sequencer runs
 * it also says which of the sequencer's ticks the block's first is
 * (fm1_arp_process_at), and the steps lock to that grid: a step starts
 * where the tick is a multiple of the rate's length from the sequencer's
 * Start, swing moving the odd ones. Every output event carries the frame
 * of the input event or tick that caused it, so the output does not
 * depend on how the host cuts its blocks.
 *
 * Origins. Each held key remembers whether it came from the keys (live)
 * or from a sequencer track (FM1_MIDI_SRC_SEQ in a note's velocity's high
 * byte, fm1_midi_ev.h): a key latches against the later keys of its own
 * origin only, and STOP lets go of the sequencer's keys, held or latched,
 * and ends the notes they started, while the keys played live play on.
 *
 * Memory. fm1_arp_size() bytes, 8-byte aligned, contents irrelevant;
 * fm1_arp_create() builds the instance in them. The instance holds no
 * pointers, so its size is the same on 32- and 64-bit builds.
 *
 * Threads. One owner: everything runs on the audio task.
 *
 * In the hosts it is the MIDI effect "arp" (arp_engine.c, FM1_KIND_MIDI_FX of
 * engine API v3), which fm1-render and the virtual FM-1 run in front of a
 * sound (engines/include/fm1_mfx_host.h; the README's "In the hosts").
 *
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_ARP_H_
#define FM1_ARP_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_midi_ev.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_ARP_MAX_HELD 16u       /* held or latched keys; the oldest goes */
#define FM1_ARP_MAX_SOUNDING 32u   /* the note ledger; the oldest is stolen */
#define FM1_ARP_MAX_OCTAVES 4u
#define FM1_ARP_MAX_CYCLE 128u     /* entries in one pass of a note order */
#define FM1_ARP_OUT_MIN 64u        /* output room per call the host should give */

/* Events, in and out. Frames are offsets into the caller's block. */
enum {
  FM1_ARP_EV_NOTE_ON = 1,   /* in, out: a = key, b = velocity 1..127, its origin in
                               the high byte (FM1_MIDI_EV_B); out, the origin is
                               the sequencer's when every key that made the note
                               was */
  FM1_ARP_EV_NOTE_OFF = 2,  /* in, out: a = key; b's high byte the origin, as
                               its note-on's */
  FM1_ARP_EV_SUSTAIN = 3,   /* in: b = 0 up, 1 down (CC 64 >= 64) */
  FM1_ARP_EV_STEP = 4,      /* in: one step, used in RATE TRG; ignored otherwise */
  FM1_ARP_EV_RESET = 5,     /* in: restart the pattern; the next tick is step 0
                               (transport Play, a bar rejoin) */
  FM1_ARP_EV_FLUSH = 6,     /* in: note-off for every sounding note (Stop,
                               bypass); held keys stay */
  FM1_ARP_EV_PANIC = 7,     /* in: FLUSH, and forget every held and latched key */
  FM1_ARP_EV_PARAM = 8,     /* in: a = FM1_ARP_P_*, b = value */
  FM1_ARP_EV_STOP = 9       /* in: the sequencer stopped: its keys go (held or
                               latched) and so do the notes they started, and a
                               note waiting for a STEP; live keys play on */
};

/* The engine API's MIDI event (engines/include/fm1_midi_ev.h): {frame,
 * kind, a, b}. The kinds above are its FM1_MIDI_EV_* codes, plus PARAM. */
typedef fm1_midi_ev_t fm1_arp_ev_t;

/* Parameters. Values are integers in each one's own range
 * (fm1_arp_param_info); a host maps its 7-bit locks onto them. */
enum {
  FM1_ARP_P_MODE = 0,       /* note order, FM1_ARP_MODE_* */
  FM1_ARP_P_ORDER,          /* how held keys are listed: FM1_ARP_ORDER_* */
  FM1_ARP_P_OCTAVES,        /* 1..4 */
  FM1_ARP_P_OCT_MODE,       /* FM1_ARP_OCT_* */
  FM1_ARP_P_RATE,           /* 0 TRG (host steps), 1..16 note values (fm1_arp_rate_ticks96) */
  FM1_ARP_P_GATE,           /* 1..200 % of the step; over 100 overlaps the next note */
  FM1_ARP_P_SWING,          /* 50..80 %: odd steps start (SWING-50)*step/60 ticks
                               late, as fm1_seq's swing (docs/13 R6); 50 = straight */
  FM1_ARP_P_PATTERN,        /* 0 every step; 1..22 Yarns' rhythm masks */
  FM1_ARP_P_EUCLID_LEN,     /* 0 off (PATTERN rules); 1..32 Euclidean steps */
  FM1_ARP_P_EUCLID_FILL,    /* 0..32 onsets, at most EUCLID_LEN */
  FM1_ARP_P_EUCLID_ROTATE,  /* 0..31 */
  FM1_ARP_P_LATCH,          /* 0..1 */
  FM1_ARP_P_JOIN,           /* 0 added keys join now; 1 at the next pass */
  FM1_ARP_P_SYNC,           /* 0 free: the grid runs on; 1 key: the first key
                               into an empty chord restarts the pattern */
  FM1_ARP_P_REPEAT,         /* 1..8 steps per note before the order moves on */
  FM1_ARP_P_RATCHET,        /* 1..4 notes inside one step */
  FM1_ARP_P_RATCHET_PROB,   /* 0..100 % chance that a step ratchets */
  FM1_ARP_P_PROB,           /* 0..100 % chance that a step plays */
  FM1_ARP_P_CHORD_PROB,     /* 0..100 % chance that a step plays the whole chord */
  FM1_ARP_P_OCT_JUMP,       /* 0..100 % chance of one octave up */
  FM1_ARP_P_VELOCITY,       /* 0 as played; 1..127 fixed */
  FM1_ARP_P_VEL_SPREAD,     /* 0..127: a seeded offset in +-spread */
  FM1_ARP_P_GATE_SPREAD,    /* 0..100: a seeded offset in +-spread points of GATE */
  FM1_ARP_P_LOOP,           /* 0 off; 1..64: the phrase restarts every LOOP steps,
                               random draws included */
  FM1_ARP_P_SEED,           /* 0..65535 */
  FM1_ARP_P_COUNT
};

enum {
  FM1_ARP_MODE_UP = 0,         /* Yarns, MCL */
  FM1_ARP_MODE_DOWN,           /* Yarns, MCL */
  FM1_ARP_MODE_UP_DOWN,        /* Yarns, MCL: ends once */
  FM1_ARP_MODE_DOWN_UP,        /* MCL: ends once */
  FM1_ARP_MODE_UP_N_DOWN,      /* MCL: ends twice */
  FM1_ARP_MODE_DOWN_N_UP,      /* MCL: ends twice */
  FM1_ARP_MODE_CONVERGE,       /* MCL: outside in */
  FM1_ARP_MODE_DIVERGE,        /* inside out */
  FM1_ARP_MODE_CONV_DIV,       /* MCL: in, then out */
  FM1_ARP_MODE_THUMB_UP,       /* the lowest note between the others, rising */
  FM1_ARP_MODE_THUMB_DOWN,
  FM1_ARP_MODE_PINKY_UP,       /* the highest note between the others */
  FM1_ARP_MODE_PINKY_DOWN,
  FM1_ARP_MODE_UP_TOP_OCT,     /* MCL "UPP": each extra octave lifts only the last note */
  FM1_ARP_MODE_DOWN_LOW_OCT,   /* MCL "DOWNP" */
  FM1_ARP_MODE_UP_ALT_OCT,     /* MCL "UP2": each extra octave lifts every other note */
  FM1_ARP_MODE_DOWN_ALT_OCT,   /* MCL "DOWN2" */
  FM1_ARP_MODE_CRAWL,          /* +2, -1 */
  FM1_ARP_MODE_RANDOM,         /* Yarns, MCL "RND2": any note, each step */
  FM1_ARP_MODE_SHUFFLE,        /* each note once per pass, in a seeded order */
  FM1_ARP_MODE_WALK,           /* a seeded step to a neighbour */
  FM1_ARP_MODE_CHORD,          /* Yarns: every held note at once */
  FM1_ARP_MODE_COUNT
};

enum { FM1_ARP_ORDER_PITCH = 0, FM1_ARP_ORDER_PLAYED, FM1_ARP_ORDER_REVERSE, FM1_ARP_ORDER_COUNT };

enum {
  FM1_ARP_OCT_SPAN = 0,  /* the order runs over all octaves as one list (Yarns) */
  FM1_ARP_OCT_UP,        /* one pass per octave, rising (MCL) */
  FM1_ARP_OCT_DOWN,
  FM1_ARP_OCT_UP_DOWN,
  FM1_ARP_OCT_RANDOM,    /* a seeded octave for each pass */
  FM1_ARP_OCT_COUNT
};

#define FM1_ARP_RATE_TRG 0u
#define FM1_ARP_RATE_COUNT 17u

typedef struct fm1_arp_param_info {
  const char *name;
  uint16_t min, max, def;
} fm1_arp_param_info_t;

typedef struct fm1_arp_stats {
  uint32_t dropped_ons;   /* note-ons not sent for want of output room */
  uint32_t deferred_offs; /* note-offs sent in a later call for the same reason */
  uint32_t stolen;        /* notes ended early because the ledger was full */
  uint32_t steps;         /* steps since create */
} fm1_arp_stats_t;

typedef struct fm1_arp fm1_arp_t;

size_t fm1_arp_size(void);

/* ppqn: the host's ticks per quarter note, 24, 48 or 96 (anything else
 * becomes 96). Parameters start at their defaults. */
fm1_arp_t *fm1_arp_create(void *mem, uint16_t ppqn);

/* One host block. Input events and ticks are each ascending by frame; at
 * one frame the input events come first, then the tick, so a key pressed on
 * a tick plays on it. Output is ascending by frame. At one frame the order
 * is: note-offs whose gate ran out, then each step's note-offs and note-ons
 * (a note that would start while the same key sounds ends it first).
 * Returns the number of events written to out (at most cap). With cap at
 * least FM1_ARP_OUT_MIN nothing is deferred in normal use; with less, a
 * note-off that does not fit is sent at the start of the next call and a
 * note-on that does not fit is never sent, so every note-on sent still gets
 * exactly one note-off. */
uint32_t fm1_arp_process(fm1_arp_t *a, const fm1_arp_ev_t *in, uint32_t n_in,
                         const uint16_t *ticks, uint32_t n_ticks,
                         fm1_arp_ev_t *out, uint32_t cap);

/* The same, with the host sequencer's transport: `running` 1 while it plays,
 * and then ticks[k] is its tick first_tick + k counted from its Start (0
 * the first downbeat, at the core's ppqn). A rate's steps then start only
 * where that tick is on the rate's grid (a multiple of the step; an odd
 * step later by the swing), so a key, Sync or not, waits for the grid's
 * next step; the pattern's own count (order, rhythm, loop) is unchanged.
 * `running` 0 is fm1_arp_process: the steps run on from the last. */
uint32_t fm1_arp_process_at(fm1_arp_t *a, const fm1_arp_ev_t *in, uint32_t n_in,
                            const uint16_t *ticks, uint32_t n_ticks, int running,
                            uint64_t first_tick, fm1_arp_ev_t *out, uint32_t cap);

/* Immediate parameter change, between blocks; the same as an
 * FM1_ARP_EV_PARAM event, which can do nothing that needs output room. */
void fm1_arp_set_param(fm1_arp_t *a, unsigned id, int value);
int fm1_arp_get_param(const fm1_arp_t *a, unsigned id);

const fm1_arp_param_info_t *fm1_arp_param_info(unsigned id);  /* NULL if out of range */
const char *fm1_arp_mode_name(unsigned mode);
const char *fm1_arp_order_name(unsigned order);
const char *fm1_arp_oct_mode_name(unsigned oct_mode);
const char *fm1_arp_rate_name(unsigned rate);
uint16_t fm1_arp_rate_ticks96(unsigned rate);   /* step length at 96 PPQN; 0 for TRG */

/* Rhythm tables (arp_rhythm.c). pattern 1..22 is Yarns' mask pattern-1;
 * 0 plays every step. Bit i set means step i plays. */
uint16_t fm1_arp_pattern_mask(unsigned pattern);
/* Yarns' Euclidean mask for `len` steps (1..32) and `fill` onsets (clamped
 * to len), as its lut_euclidean[(len - 1) * 32 + fill]. */
uint32_t fm1_arp_euclid_mask(unsigned len, unsigned fill);

unsigned fm1_arp_sounding(const fm1_arp_t *a);   /* notes on, owed offs included */
unsigned fm1_arp_held(const fm1_arp_t *a);       /* keys in the chord, pending ones included */
unsigned fm1_arp_held_seq(const fm1_arp_t *a);   /* ...of them, those the sequencer gave */
void fm1_arp_get_stats(const fm1_arp_t *a, fm1_arp_stats_t *st);

#ifdef __cplusplus
}
#endif

#endif  /* FM1_ARP_H_ */
