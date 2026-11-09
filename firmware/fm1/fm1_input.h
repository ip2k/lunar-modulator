/* SPDX-License-Identifier: MIT
 * FM-1 application input: panel scans, MIDI messages and USB-MIDI event
 * packets turned into one event stream for the app. Portable C99, no SDK
 * and no registers: the SDK glue (fm1_sdk_main.c) reads the hardware and
 * the app adapter (fm1_live.c) applies the events. Host-tested by
 * tests/test_fm1_input.py.
 *
 * The controls follow the virtual FM-1 (sim/web): a key is fm1_app_key, a
 * button fm1_app_button, an encoder fm1_app_encoder in detents, MASTER
 * fm1_app_master; MIDI note on/off, pitch bend (+/-2 semitones), CC 7 as
 * MASTER and CC 123 as all notes off, exactly as sim/web/www/app.js routes
 * a Web MIDI message.
 */
#ifndef LUNAR_FM1_INPUT_H
#define LUNAR_FM1_INPUT_H

#include <stdint.h>
#include "../board/midi_parser.h"
#include "../board/adc.h"
#include "../third_party/fm1-nes/fm1_keys.h"

#ifdef __cplusplus
extern "C" {
#endif

enum lunar_fm1_event_kind {
    LUNAR_FM1_EV_KEY = 1,  /* a key 0..26 (F3 = 0), b down, c velocity 1..127 */
    LUNAR_FM1_EV_BUTTON,   /* a FM1_BTN_* (fm1_panel.h), b down */
    LUNAR_FM1_EV_ENCODER,  /* a FM1_ENC_*, value detents (+ = assumed clockwise) */
    LUNAR_FM1_EV_MASTER,   /* a level 0..127 */
    LUNAR_FM1_EV_NOTE_ON,  /* a note, b velocity 1..127, c MIDI channel 0..15 */
    LUNAR_FM1_EV_NOTE_OFF, /* a note, c MIDI channel 0..15 */
    LUNAR_FM1_EV_BEND,     /* value -8192..8191 */
    LUNAR_FM1_EV_PANIC     /* all notes off */
};

struct lunar_fm1_event {
    uint8_t kind, a, b, c;
    int16_t value;
};

/* Single producer (the panel/MIDI task), single consumer (the audio
 * producer, between reserving a work slot and producing its block). Both
 * run on CPU0 in the FM-1 image; the fence also orders them across cores. */
#define LUNAR_FM1_QUEUE_SIZE 64u /* a power of two */
struct lunar_fm1_queue {
    volatile uint32_t head, tail, dropped;
    struct lunar_fm1_event slot[LUNAR_FM1_QUEUE_SIZE];
};
void lunar_fm1_queue_reset(struct lunar_fm1_queue *q);
/* 1 when queued; 0 when full (counted in `dropped`, the event is lost). */
int lunar_fm1_queue_push(struct lunar_fm1_queue *q, const struct lunar_fm1_event *e);
/* 1 when an event was taken. */
int lunar_fm1_queue_pop(struct lunar_fm1_queue *q, struct lunar_fm1_event *e);

/* Matrix button id (fm1_keys.h, 0..13) to FM1_BTN_*: identity. Ids 0 and 1
 * are OCT- and OCT+, 12 PLAY and 13 REC [reported: Felucca panel.c, PLAY
 * and REC "measured on hardware"]; ids 2..11 follow the manual's order FX,
 * SEL, ENV, LFO, EDIT, GLO, HOME, SAVE, ARP, SEQ [reported: Felucca's
 * default table, which it marks a best guess]. TODO(hardware): confirm each
 * label on the unit. */
extern const uint8_t lunar_fm1_button_map[14];
/* fm1-nes encoder order (SELECT, ALGORITHM, KNOB1-4, PRESETS [reported:
 * fm1-nes one-at-a-time tests]) to FM1_ENC_*. */
extern const uint8_t lunar_fm1_encoder_map[LUNAR_ENCODER_COUNT];
/* TODO(hardware): which way is clockwise is not established (fm1_keys.h);
 * every sign is +1 until a unit is turned and watched. */
extern const int8_t lunar_fm1_encoder_sign[LUNAR_ENCODER_COUNT];
/* Contact edges per detent. TODO(hardware): 2 follows SLOOP's rule of a
 * rest state after at least two net transitions [reported: SLOOP
 * hal/fm1_input.h]; not measured on this project's unit. */
#define LUNAR_FM1_EDGES_PER_DETENT 2
/* The keys sense no velocity [inferred: one contact per key in the matrix];
 * a fixed velocity until a setting chooses one. */
#define LUNAR_FM1_KEY_VELOCITY 100u

struct lunar_fm1_panel {
    unsigned stable[2], candidate[2]; /* debounced and last raw key sets */
    struct lunar_encoders encoders;
    int used[LUNAR_ENCODER_COUNT];    /* edges already sent as detents */
    struct lunar_pot pot;
    int master_seen;
    unsigned scans;
};
void lunar_fm1_panel_reset(struct lunar_fm1_panel *p);
/* One complete matrix pass (rows as lunar_matrix_scan returns them) and,
 * when master_raw >= 0, one MASTER ADC reading. A key or button changes
 * when two passes in a row agree. Returns the number of events queued. */
unsigned lunar_fm1_panel_update(struct lunar_fm1_panel *p,
                                const unsigned char rows[LUNAR_MATRIX_COLUMNS],
                                int master_raw, struct lunar_fm1_queue *q);

/* A parsed MIDI message (TRS or USB) as an event; the channel is kept for
 * the router. TODO: honour the app's MIDI-in channel setting. Returns 1 when
 * `e` is set; messages the virtual FM-1 ignores (program change, other CCs,
 * clock) give 0. */
int lunar_fm1_midi_event(const struct lunar_midi_message *m, struct lunar_fm1_event *e);

/* One USB-MIDI 1.0 event packet (cable/CIN byte and three MIDI bytes) as a
 * MIDI message. Channel voice messages (CIN 0x8..0xE) and single bytes
 * (CIN 0xF) are returned; SysEx and system common packets give 0. */
int lunar_fm1_usb_midi_packet(const unsigned char packet[4], struct lunar_midi_message *m);

/* ---- the router: events to the pipelined app's safe controls ------------
 * The pipelined app (FM1_APP_RENDER_PIPELINE) fails closed when a UI path
 * runs while a block is in flight: fm1_app_key, _button, _encoder,
 * _pitch_bend and _all_notes_off carry PIPELINE_GUARD(!pipeline_busy())
 * (sim/web/src/fm1_app.c) [verified: source]. While audio streams a block is
 * nearly always in flight, so the FM-1 image applies only what that build
 * allows between blocks: fm1_app_unit_note_on/off on sounds 0, 2 and 3, set
 * parameters on sound 0's filter insert, and fm1_app_master without its
 * popup. The router turns events into those actions and counts the rest.
 * TODO(app): the full panel UI (modes, menus, sequencer editing, sound 2's
 * notes, pitch bend) needs the app's pipeline fence widened (docs/18). */
#define LUNAR_FM1_KEY_BASE_NOTE 53   /* key 0 is F3 at octave 0 (fm1_app.h) */
#define LUNAR_FM1_OCTAVE_MAX 3
#define LUNAR_FM1_SOUNDS 4u
#define LUNAR_FM1_DEFERRED_SOUND 1u  /* sound 2 (Macro) is the CPU1 worker's */
#define LUNAR_FM1_CUTOFF_MIN 20.0f   /* fx_filter "Cutoff", Hz */
#define LUNAR_FM1_CUTOFF_MAX 18000.0f
#define LUNAR_FM1_CUTOFF_START 2400.0f
#define LUNAR_FM1_RESONANCE_START 0.25f

enum lunar_fm1_action_kind {
    LUNAR_FM1_ACT_NOTE_ON = 1, /* sound, note, velocity */
    LUNAR_FM1_ACT_NOTE_OFF,    /* sound, note */
    LUNAR_FM1_ACT_MASTER,      /* value 0..1 (fm1_app_master position) */
    LUNAR_FM1_ACT_CUTOFF,      /* value Hz, sound 0's filter insert, parameter 1 */
    LUNAR_FM1_ACT_RESONANCE    /* value 0..1, same insert, parameter 2 */
};
struct lunar_fm1_action {
    uint8_t kind, sound, note, velocity;
    float value;
};
typedef void (*lunar_fm1_action_fn)(void *ctx, const struct lunar_fm1_action *action);

struct lunar_fm1_router {
    int octave;                         /* -3..+3, OCT- / OCT+ */
    uint8_t key_note[27];               /* note + 1 while a key holds it, else 0 */
    uint8_t held[LUNAR_FM1_SOUNDS][128];/* note-ons not yet released, per sound */
    float cutoff, resonance;
    unsigned applied, deferred, ignored;
};
void lunar_fm1_router_reset(struct lunar_fm1_router *r);
/* MIDI channel to sound: channels 1, 3 and 4 play sounds 1, 3 and 4 (S1,
 * S3 drums, S4); channel 2 would be sound 2, which this image defers; every
 * other channel plays sound 1. Returns the sound index, or -1 to defer. */
int lunar_fm1_channel_sound(unsigned channel);
/* Apply one event; emits zero or more actions. Returns the number emitted. */
unsigned lunar_fm1_route(struct lunar_fm1_router *r, const struct lunar_fm1_event *e,
                         lunar_fm1_action_fn emit, void *ctx);

#ifdef __cplusplus
}
#endif
#endif
