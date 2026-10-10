/*
 * Sophie — an original metallic percussion synthesizer for Schwung.
 *
 * This is not an emulation. It combines established FM, phase modulation,
 * oscillator feedback, pitch envelopes and intentionally reduced digital
 * resolution into a compact instrument designed for Ableton Move.
 */

#include "plugin_api_v1.h"

#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SOPHIE_PI 3.14159265358979323846f
#define SOPHIE_TAU (2.0f * SOPHIE_PI)
#define SOPHIE_VOICES 12
#define SOPHIE_PADS 16
#define SOPHIE_FIRST_NOTE 36
#define SOPHIE_MAX_DELAY_SAMPLES 1536 /* ~34 ms at 44.1 kHz */

typedef struct {
    int model;
    float tune;
    float color;
    float metal;
    float feedback;
    float sweep;
    float decay;
    float crush;
    float drive;
    float level;
    float cutoff;
    float resonance;
    int filter_type;
    float ring_time;
    float ring_feedback;
    float ring_mix;
    float ring_tone;
} sophie_patch_t;

typedef struct {
    float carrier_phase;
    float mod1_phase;
    float mod2_phase;
    float mod3_phase;
    float amp_env;
    float pitch_env;
    float attack;
    float feedback_z;
    float filter_low;
    float filter_band;
    float noise_z;
    float base_hz;
    float velocity;
    float crush_hold;
    int crush_count;
    float delay_buf[SOPHIE_MAX_DELAY_SAMPLES];
    float delay_lp;
    int delay_pos;
    int pad_index;
    sophie_patch_t patch;
    uint32_t age;
    uint32_t rng;
    int active;
} sophie_voice_t;

typedef struct {
    sophie_voice_t voices[SOPHIE_VOICES];
    int sample_rate;
    uint32_t age_counter;
    uint32_t rng;
    sophie_patch_t pads[SOPHIE_PADS];
    int focused_pad;
    char error[96];
} sophie_t;

static const host_api_v1_t *g_host;

static float clampf(float x, float lo, float hi) {
    return x < lo ? lo : (x > hi ? hi : x);
}

static float wrap_phase(float x) {
    /* Preserve the original one-turn path. High-ratio modulators can advance
     * through many cycles in one sample, so reduce only if that fast path
     * leaves the phase out of range. The increments are bounded by the
     * oscillator cap and supported rates, making the quotient representable. */
    if (x >= SOPHIE_TAU) x -= SOPHIE_TAU;
    else if (x < 0.0f) x += SOPHIE_TAU;
    if (x >= SOPHIE_TAU || x < 0.0f) {
        int turns = (int)(x / SOPHIE_TAU);
        x -= (float)turns * SOPHIE_TAU;
        if (x < 0.0f) x += SOPHIE_TAU;
        if (x >= SOPHIE_TAU) x -= SOPHIE_TAU;
    }
    return x;
}

static float soft_clip(float x) {
    float ax = fabsf(x);
    return x / (1.0f + ax);
}

static uint32_t xorshift32(uint32_t *state) {
    uint32_t x = *state ? *state : 0x6d2b79f5u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static float noise_bipolar(uint32_t *state) {
    return (float)(xorshift32(state) & 0x00ffffffu) * (2.0f / 16777215.0f) - 1.0f;
}

static float midi_hz(int note) {
    return 440.0f * exp2f(((float)note - 69.0f) / 12.0f);
}

static float json_number(const char *json, const char *key, float fallback) {
    if (!json) return fallback;
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(json, needle);
    if (!p || !(p = strchr(p + strlen(needle), ':'))) return fallback;
    return strtof(p + 1, NULL);
}

static sophie_patch_t patch(int model, float tune, float color, float metal, float feedback,
                            float sweep, float decay, float crush, float drive) {
    sophie_patch_t p = {model, tune, color, metal, feedback, sweep, decay, crush, drive};
    p.level = 100.0f; p.cutoff = 100.0f; p.resonance = 0.0f; p.filter_type = 0;
    p.ring_time = 6.0f; p.ring_feedback = 0.0f; p.ring_mix = 0.0f; p.ring_tone = 70.0f;
    return p;
}

static void set_factory_kit(sophie_t *s) {
    /* GM/Ableton Drum Rack order, MIDI notes 36–51. */
    s->pads[0]  = patch(0, -5, 24,  8,  6,  55, 0.28f,  0, 58); /* Kick */
    s->pads[1]  = patch(3,  0, 76, 72, 34,  16, 0.09f, 48, 58); /* Rim */
    s->pads[2]  = patch(3,  0, 52, 76, 18,  28, 0.24f, 30, 52); /* Snare */
    s->pads[3]  = patch(2,  0, 84, 88, 42,  -8, 0.19f, 56, 68); /* Clap */
    s->pads[4]  = patch(1,  0, 63, 82, 28,  24, 0.18f, 38, 58); /* Snare 2 */
    s->pads[5]  = patch(0,  0, 24, 44, 16,  58, 0.42f,  8, 48); /* Low Tom */
    s->pads[6]  = patch(3,  0, 94, 98, 58,   0, 0.055f, 52, 62); /* Closed HH */
    s->pads[7]  = patch(0,  0, 31, 48, 20,  54, 0.47f, 10, 50); /* Floor Tom */
    s->pads[8]  = patch(3,  0, 88, 94, 50,   2, 0.10f, 46, 58); /* Pedal HH */
    s->pads[9]  = patch(0,  0, 38, 52, 22,  48, 0.36f, 12, 52); /* Mid Tom */
    s->pads[10] = patch(3,  0, 91, 96, 62,  -4, 0.48f, 42, 60); /* Open HH */
    s->pads[11] = patch(0,  0, 45, 56, 25,  44, 0.31f, 14, 54); /* Low-mid Tom */
    s->pads[12] = patch(0,  0, 51, 60, 28,  40, 0.27f, 16, 56); /* High-mid Tom */
    s->pads[13] = patch(1,  0, 78, 92, 72, -12, 1.65f, 28, 54); /* Crash */
    s->pads[14] = patch(0,  0, 58, 64, 30,  36, 0.23f, 18, 58); /* High Tom */
    s->pads[15] = patch(2,  0, 69, 86, 66,  -6, 1.15f, 22, 52); /* Ride */
    s->focused_pad = 1;
}

static void apply_patch_json(sophie_patch_t *p, const char *json, const char *prefix) {
    char key[40];
#define LOAD_FIELD(field) do { snprintf(key, sizeof(key), "%s" #field, prefix); \
    p->field = json_number(json, key, p->field); } while (0)
    snprintf(key, sizeof(key), "%smodel", prefix);
    p->model = (int)json_number(json, key, (float)p->model);
    LOAD_FIELD(tune);
    LOAD_FIELD(color);
    LOAD_FIELD(metal);
    LOAD_FIELD(feedback);
    LOAD_FIELD(sweep);
    LOAD_FIELD(decay);
    LOAD_FIELD(crush);
    LOAD_FIELD(drive);
    LOAD_FIELD(level); LOAD_FIELD(cutoff); LOAD_FIELD(resonance); LOAD_FIELD(filter_type);
    LOAD_FIELD(ring_time); LOAD_FIELD(ring_feedback); LOAD_FIELD(ring_mix); LOAD_FIELD(ring_tone);
#undef LOAD_FIELD
}

static void apply_state_json(sophie_t *s, const char *json) {
    if (!json) return;
    if (strstr(json, "\"p01_model\"")) {
        for (int i = 0; i < SOPHIE_PADS; ++i) {
            char prefix[12];
            snprintf(prefix, sizeof(prefix), "p%02d_", i + 1);
            apply_patch_json(&s->pads[i], json, prefix);
        }
        s->focused_pad = (int)json_number(json, "focused_pad", (float)s->focused_pad);
    } else if (strstr(json, "\"model\"")) {
        /* v0.1 saved one shared sound. Preserve it on Pad 1 while retaining
         * the new factory mappings on the other fifteen pads. */
        apply_patch_json(&s->pads[0], json, "");
        s->focused_pad = 1;
    }
    if (s->focused_pad < 1 || s->focused_pad > SOPHIE_PADS) s->focused_pad = 1;
}

static void *sophie_create(const char *module_dir, const char *json_defaults) {
    (void)module_dir;
    sophie_t *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->sample_rate = (g_host && g_host->sample_rate > 0) ? g_host->sample_rate : MOVE_SAMPLE_RATE;
    s->rng = 0x534f5048u;
    set_factory_kit(s);
    apply_state_json(s, json_defaults);
    return s;
}

static void sophie_destroy(void *instance) {
    free(instance);
}

static sophie_voice_t *allocate_voice(sophie_t *s) {
    sophie_voice_t *oldest = &s->voices[0];
    for (int i = 0; i < SOPHIE_VOICES; ++i) {
        if (!s->voices[i].active) return &s->voices[i];
        if (s->voices[i].age < oldest->age) oldest = &s->voices[i];
    }
    return oldest;
}

static void trigger_voice(sophie_t *s, int note, int velocity, int source) {
    int pad_index = note - SOPHIE_FIRST_NOTE;
    if (pad_index < 0 || pad_index >= SOPHIE_PADS) return;
    sophie_voice_t *v = allocate_voice(s);
    memset(v, 0, sizeof(*v));
    v->active = 1;
    v->age = ++s->age_counter;
    v->velocity = clampf((float)velocity / 127.0f, 0.01f, 1.0f);
    v->patch = s->pads[pad_index];
    v->pad_index = pad_index;
    v->base_hz = clampf(midi_hz(note) * exp2f(v->patch.tune / 12.0f), 20.0f, 10000.0f);
    v->amp_env = 1.0f;
    v->pitch_env = 1.0f;
    v->attack = 0.0f;
    v->rng = xorshift32(&s->rng) ^ ((uint32_t)note << 16) ^ (uint32_t)velocity;
    /* Slight phase variation retains impact while avoiding machine-gun repeats. */
    v->mod2_phase = noise_bipolar(&v->rng) * 0.12f;
    v->mod3_phase = noise_bipolar(&v->rng) * 0.08f;
    /* Editor pad selection is owned by ui_chain.js. Never mutate focused_pad
     * from DSP note-ons: playback and live MIDI can share the same source. */
}

static void sophie_midi(void *instance, const uint8_t *msg, int len, int source) {
    sophie_t *s = instance;
    if (!s || !msg || len < 3) return;
    int status = msg[0] & 0xf0;
    if (status == 0x90 && msg[2] > 0)
        trigger_voice(s, msg[1] & 0x7f, msg[2] & 0x7f, source);
}

static const char *parse_pad_key(const char *key, int *pad_index) {
    if (!key || key[0] != 'p' || key[1] < '0' || key[1] > '9' ||
        key[2] < '0' || key[2] > '9' || key[3] != '_') return NULL;
    int n = (key[1] - '0') * 10 + (key[2] - '0');
    if (n < 1 || n > SOPHIE_PADS) return NULL;
    *pad_index = n - 1;
    return key + 4;
}

static int assign_patch_param(sophie_patch_t *p, const char *key, float value) {
    if (!strcmp(key, "model")) p->model = (int)clampf(value, 0.0f, 3.0f);
    else if (!strcmp(key, "tune")) p->tune = clampf(value, -24.0f, 24.0f);
    else if (!strcmp(key, "color")) p->color = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "metal")) p->metal = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "feedback")) p->feedback = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "sweep")) p->sweep = clampf(value, -100.0f, 100.0f);
    else if (!strcmp(key, "decay")) p->decay = clampf(value, 0.03f, 4.0f);
    else if (!strcmp(key, "crush")) p->crush = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "drive")) p->drive = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "level")) p->level = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "cutoff")) p->cutoff = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "resonance")) p->resonance = clampf(value, 0.0f, 100.0f);
    /* BPF is appended as value 4 so existing saved Notch (2) and DJ (3)
     * patches keep their meaning. */
    else if (!strcmp(key, "filter_type")) p->filter_type = (int)clampf(value, 0.0f, 4.0f);
    else if (!strcmp(key, "ring_time")) p->ring_time = clampf(value, 0.5f, 30.0f);
    else if (!strcmp(key, "ring_feedback")) p->ring_feedback = clampf(value, 0.0f, 95.0f);
    else if (!strcmp(key, "ring_mix")) p->ring_mix = clampf(value, 0.0f, 100.0f);
    else if (!strcmp(key, "ring_tone")) p->ring_tone = clampf(value, 0.0f, 100.0f);
    else return 0;
    return 1;
}

static void sophie_set(void *instance, const char *key, const char *val) {
    sophie_t *s = instance;
    if (!s || !key || !val) return;
    if (!strcmp(key, "state")) {
        apply_state_json(s, val);
        return;
    }
    if (!strcmp(key, "focused_pad")) {
        int n = (int)strtof(val, NULL);
        if (n >= 1 && n <= SOPHIE_PADS) s->focused_pad = n;
        return;
    }
    int pad_index;
    const char *field = parse_pad_key(key, &pad_index);
    if (field) {
        assign_patch_param(&s->pads[pad_index], field, strtof(val, NULL));
        return;
    }
    /* Compatibility alias: bare keys edit whichever pad is focused. */
    assign_patch_param(&s->pads[s->focused_pad - 1], key, strtof(val, NULL));
}

static const char *UI_HIERARCHY =
    "{\"levels\":{\"root\":{\"label\":\"Sophie\",\"child_count\":16,"
    "\"child_label\":\"Pad\",\"child_key_template\":\"p{index}_{key}\","
    "\"child_labels\":[\"1 Kick\",\"2 Rim\",\"3 Snare\",\"4 Clap\",\"5 Snare 2\",\"6 Low Tom\",\"7 Closed HH\",\"8 Floor Tom\",\"9 Pedal HH\",\"10 Mid Tom\",\"11 Open HH\",\"12 Low-Mid\",\"13 High-Mid\",\"14 Crash\",\"15 High Tom\",\"16 Ride\"],"
    "\"child_index_base\":1,\"child_index_digits\":2,\"child_index_param\":\"focused_pad\","
    "\"child_key_overrides\":{\"focused_pad\":\"focused_pad\"},"
    "\"params\":[\"focused_pad\",\"tune\",\"decay\",\"model\",\"color\",\"metal\",\"feedback\",\"sweep\",\"crush\",\"drive\",\"level\",\"cutoff\",\"resonance\",\"filter_type\",{\"level\":\"ring\",\"label\":\"Ring\"}],"
    "\"knobs\":[\"tune\",\"decay\",\"model\",\"color\",\"metal\",\"feedback\",\"sweep\",\"crush\",\"drive\",\"level\",\"cutoff\",\"resonance\",\"filter_type\"]},"
    "\"ring\":{\"label\":\"Ring\",\"child_count\":16,\"child_label\":\"Pad\",\"child_key_template\":\"p{index}_{key}\",\"child_labels\":[\"1 Kick\",\"2 Rim\",\"3 Snare\",\"4 Clap\",\"5 Snare 2\",\"6 Low Tom\",\"7 Closed HH\",\"8 Floor Tom\",\"9 Pedal HH\",\"10 Mid Tom\",\"11 Open HH\",\"12 Low-Mid\",\"13 High-Mid\",\"14 Crash\",\"15 High Tom\",\"16 Ride\"],\"child_index_base\":1,\"child_index_digits\":2,\"child_index_param\":\"focused_pad\",\"params\":[\"ring_time\",\"ring_feedback\",\"ring_mix\",\"ring_tone\"],\"knobs\":[\"ring_time\",\"ring_feedback\",\"ring_mix\",\"ring_tone\"]}}}";

static int write_string(char *buf, int len, const char *value) {
    if (!buf || len <= 0) return -1;
    int n = snprintf(buf, (size_t)len, "%s", value);
    return n >= len ? len - 1 : n;
}

static void appendf(char *buf, int len, int *pos, const char *fmt, ...) {
    if (!buf || len <= 0 || *pos >= len - 1) return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf + *pos, (size_t)(len - *pos), fmt, ap);
    va_end(ap);
    if (n < 0) return;
    *pos += n;
    if (*pos >= len) *pos = len - 1;
}

static int write_chain_params(sophie_t *s, char *buf, int len) {
    int pos = 0;
    appendf(buf, len, &pos, "[{\"key\":\"focused_pad\",\"name\":\"Pad\",\"type\":\"int\",\"min\":1,\"max\":16,\"step\":1}");
    for (int i = 0; i < SOPHIE_PADS; ++i) {
        sophie_patch_t *p = &s->pads[i];
        int n = i + 1;
        appendf(buf, len, &pos,
            ",{\"key\":\"p%02d_model\",\"name\":\"Pad %d Model\",\"type\":\"enum\","
            "\"options\":[\"Fuse\",\"Stack\",\"Split\",\"Shard\"],\"default\":%d}", n, n, p->model);
#define ADD_FLOAT(field, label, minv, maxv, stepv, unitv) \
        appendf(buf, len, &pos, ",{\"key\":\"p%02d_" #field "\",\"name\":\"Pad %d %s\"," \
            "\"type\":\"float\",\"min\":%g,\"max\":%g,\"step\":%g," \
            "\"default\":%.3f,\"unit\":\"%s\"}", \
            n, n, label, (double)(minv), (double)(maxv), (double)(stepv), p->field, unitv)
        ADD_FLOAT(tune, "Tune", -24, 24, 1, "st");
        ADD_FLOAT(color, "Color", 0, 100, 1, "%");
        ADD_FLOAT(metal, "Metal", 0, 100, 1, "%");
        ADD_FLOAT(feedback, "Feedback", 0, 100, 1, "%");
        ADD_FLOAT(sweep, "Sweep", -100, 100, 1, "%");
        ADD_FLOAT(decay, "Decay", 0.03, 4, 0.01, "s");
        ADD_FLOAT(crush, "Crush", 0, 100, 1, "%");
        ADD_FLOAT(drive, "Drive", 0, 100, 1, "%");
        ADD_FLOAT(level, "Level", 0, 100, 1, "%");
        appendf(buf, len, &pos, ",{\"key\":\"p%02d_cutoff\",\"name\":\"Pad %d Cutoff\",\"type\":\"float\",\"min\":0,\"max\":100,\"step\":1,\"default\":%.3f,\"unit\":\"%%\",\"viz\":{\"kind\":\"filter\",\"group\":\"sophie_filter\",\"role\":\"cutoff\"}}", n, n, p->cutoff);
        appendf(buf, len, &pos, ",{\"key\":\"p%02d_resonance\",\"name\":\"Pad %d Resonance\",\"type\":\"float\",\"min\":0,\"max\":100,\"step\":1,\"default\":%.3f,\"unit\":\"%%\",\"viz\":{\"kind\":\"filter\",\"group\":\"sophie_filter\",\"role\":\"resonance\"}}", n, n, p->resonance);
        appendf(buf, len, &pos, ",{\"key\":\"p%02d_filter_type\",\"name\":\"Pad %d Filter Type\",\"type\":\"enum\",\"options\":[\"LPF\",\"HPF\",\"Notch\",\"DJ\",\"BPF\"],\"default\":%d,\"viz\":{\"kind\":\"filter\",\"group\":\"sophie_filter\",\"role\":\"mode\"}}", n, n, p->filter_type);
        ADD_FLOAT(ring_time, "Ring Time", 0.5, 30, 0.1, "ms");
        ADD_FLOAT(ring_feedback, "Ring Feedback", 0, 95, 1, "%");
        ADD_FLOAT(ring_mix, "Ring Mix", 0, 100, 1, "%");
        ADD_FLOAT(ring_tone, "Ring Tone", 0, 100, 1, "%");
#undef ADD_FLOAT
    }
    appendf(buf, len, &pos, "]");
    return pos;
}

static int write_state(sophie_t *s, char *buf, int len) {
    int pos = 0;
    appendf(buf, len, &pos, "{\"focused_pad\":%d", s->focused_pad);
    for (int i = 0; i < SOPHIE_PADS; ++i) {
        sophie_patch_t *p = &s->pads[i];
        appendf(buf, len, &pos,
            ",\"p%02d_model\":%d,\"p%02d_tune\":%.3f,\"p%02d_color\":%.3f,\"p%02d_metal\":%.3f,"
            "\"p%02d_feedback\":%.3f,\"p%02d_sweep\":%.3f,\"p%02d_decay\":%.3f,"
            "\"p%02d_crush\":%.3f,\"p%02d_drive\":%.3f,\"p%02d_level\":%.3f,\"p%02d_cutoff\":%.3f,\"p%02d_resonance\":%.3f,\"p%02d_filter_type\":%d,\"p%02d_ring_time\":%.3f,\"p%02d_ring_feedback\":%.3f,\"p%02d_ring_mix\":%.3f,\"p%02d_ring_tone\":%.3f",
            i + 1, p->model, i + 1, p->tune, i + 1, p->color, i + 1, p->metal,
            i + 1, p->feedback, i + 1, p->sweep, i + 1, p->decay,
            i + 1, p->crush, i + 1, p->drive, i + 1, p->level, i + 1, p->cutoff,
            i + 1, p->resonance, i + 1, p->filter_type, i + 1, p->ring_time,
            i + 1, p->ring_feedback, i + 1, p->ring_mix, i + 1, p->ring_tone);
    }
    appendf(buf, len, &pos, "}");
    return pos;
}

static int get_patch_param(const sophie_patch_t *p, const char *key, char *buf, int len) {
    if (!strcmp(key, "model")) return snprintf(buf, (size_t)len, "%d", p->model);
    float value;
    if (!strcmp(key, "tune")) value = p->tune;
    else if (!strcmp(key, "color")) value = p->color;
    else if (!strcmp(key, "metal")) value = p->metal;
    else if (!strcmp(key, "feedback")) value = p->feedback;
    else if (!strcmp(key, "sweep")) value = p->sweep;
    else if (!strcmp(key, "decay")) value = p->decay;
    else if (!strcmp(key, "crush")) value = p->crush;
    else if (!strcmp(key, "drive")) value = p->drive;
    else if (!strcmp(key, "level")) value = p->level;
    else if (!strcmp(key, "cutoff")) value = p->cutoff;
    else if (!strcmp(key, "resonance")) value = p->resonance;
    else if (!strcmp(key, "filter_type")) return snprintf(buf, (size_t)len, "%d", p->filter_type);
    else if (!strcmp(key, "ring_time")) value = p->ring_time;
    else if (!strcmp(key, "ring_feedback")) value = p->ring_feedback;
    else if (!strcmp(key, "ring_mix")) value = p->ring_mix;
    else if (!strcmp(key, "ring_tone")) value = p->ring_tone;
    else return -1;
    return snprintf(buf, (size_t)len, "%.3f", value);
}

static int sophie_get(void *instance, const char *key, char *buf, int len) {
    sophie_t *s = instance;
    if (!s || !key) return -1;
    if (!strcmp(key, "chain_params")) return write_chain_params(s, buf, len);
    /* Keep the hierarchy private so Schwung loads the module UI shim. The
     * shim serves this same hierarchy as ui_pages and handles pad-follow at
     * the UI event boundary, where sequenced notes are not fed back into it. */
    if (!strcmp(key, "ui_hierarchy")) return -1;
    if (!strcmp(key, "ui_pages")) return write_string(buf, len, UI_HIERARCHY);
    if (!strcmp(key, "clock_running")) {
        int running = g_host && g_host->get_clock_status &&
                      g_host->get_clock_status() == MOVE_CLOCK_STATUS_RUNNING;
        return snprintf(buf, (size_t)len, "%d", running ? 1 : 0);
    }
    if (!strcmp(key, "state")) return write_state(s, buf, len);
    if (!strcmp(key, "focused_pad")) return snprintf(buf, (size_t)len, "%d", s->focused_pad);
    int pad_index;
    const char *field = parse_pad_key(key, &pad_index);
    if (field) return get_patch_param(&s->pads[pad_index], field, buf, len);
    return get_patch_param(&s->pads[s->focused_pad - 1], key, buf, len);
}

static int sophie_error(void *instance, char *buf, int len) {
    sophie_t *s = instance;
    if (!s || !s->error[0]) return 0;
    return write_string(buf, len, s->error);
}

static float render_voice(sophie_t *s, sophie_voice_t *v) {
    if (!v->active) return 0.0f;
    const sophie_patch_t *p = &v->patch;

    float decay_s = clampf(p->decay, 0.03f, 4.0f);
    /* Decay is the approximate audible duration, not an e-folding time. The
     * old coefficient took about nine displayed decay values to reach the
     * voice cutoff, making 0.20 s ring for almost two seconds. */
    float amp_mul = expf(logf(0.00012f) / (decay_s * (float)s->sample_rate));
    float pitch_time = v->pad_index == 0 ? 0.075f : 0.028f;
    float pitch_mul = expf(-1.0f / (pitch_time * (float)s->sample_rate));
    v->amp_env *= amp_mul;
    v->pitch_env *= pitch_mul;
    v->attack += (1.0f - v->attack) * 0.085f;
    if (v->amp_env < 0.00012f) {
        v->active = 0;
        return 0.0f;
    }

    float color = p->color * 0.01f;
    float metal = p->metal * 0.01f;
    float feedback = p->feedback * 0.01f;
    float sweep_range = v->pad_index == 0 ? 2.5f : 4.5f;
    float sweep_oct = p->sweep * 0.01f * sweep_range * v->pitch_env;
    float hz = clampf(v->base_hz * exp2f(sweep_oct), 18.0f, 18000.0f);

    /* Deliberately non-integer ratios: Color moves through useful clang zones. */
    float r1 = 0.47f + color * color * 7.6f;
    float r2 = 1.31f + color * 11.17f;
    float r3 = 2.07f + (1.0f - color) * 15.73f;
    float inc = SOPHIE_TAU * hz / (float)s->sample_rate;

    v->carrier_phase = wrap_phase(v->carrier_phase + inc);
    v->mod1_phase = wrap_phase(v->mod1_phase + inc * r1);
    v->mod2_phase = wrap_phase(v->mod2_phase + inc * r2);
    v->mod3_phase = wrap_phase(v->mod3_phase + inc * r3);

    float fb = v->feedback_z * feedback * (2.0f + metal * 10.0f);
    float m1 = sinf(v->mod1_phase + fb);
    float m2 = sinf(v->mod2_phase + m1 * metal * 2.5f);
    float m3 = sinf(v->mod3_phase);
    float index = metal * metal * (2.0f + 24.0f * (0.25f + v->pitch_env * 0.75f));
    float out;

    if (v->pad_index == 0) {
        /* Ponyboy-style kick architecture: a low analog-BD sine owns the
         * pitch and weight. Folded/FM material is a quiet parallel texture,
         * rather than the entire body being forced through metallic FM. */
        float body = sinf(v->carrier_phase);
        float folded = sinf(body * (1.0f + color * 2.2f));
        float texture = sinf(v->carrier_phase + m2 * (0.18f + feedback * 1.35f));
        float n = noise_bipolar(&v->rng);
        v->noise_z += (n - v->noise_z) * 0.32f;
        float click = v->noise_z * v->pitch_env;
        out = body * (0.86f - color * 0.08f)
            + folded * (0.14f + color * 0.08f)
            + texture * metal * 0.18f
            + click * (0.012f + metal * 0.035f);
        /* Keep the kick's low tuned body, but let Model remain meaningful on
         * pad 1 instead of silently behaving like Fuse for every choice. */
        if (p->model == 1)
            out += 0.16f * sinf(v->carrier_phase * 2.01f + m1 * (0.4f + metal * 2.0f));
        else if (p->model == 2)
            out += 0.14f * sinf(v->carrier_phase * 0.503f - m2 * (0.3f + metal * 1.5f));
        else if (p->model == 3) {
            float stair = floorf((v->carrier_phase / SOPHIE_TAU) * 24.0f) * (SOPHIE_TAU / 24.0f);
            out += 0.12f * sinf(stair + m1 * (0.5f + metal * 2.0f));
        }
    } else switch (p->model) {
    default: /* Fuse: two modulators in series, highly responsive feedback. */
        out = sinf(v->carrier_phase + index * (m2 * 0.72f + m1 * 0.28f));
        break;
    case 1: /* Stack: dense additive/FM stack. */
        out = sinf(v->carrier_phase + index * 0.62f * m1)
            + 0.55f * sinf(v->carrier_phase * 0.501f + index * 0.35f * m2)
            + 0.32f * sinf(v->carrier_phase * 1.997f + index * 0.22f * m3);
        out *= 0.56f;
        break;
    case 2: /* Split: parallel operators with asymmetric modulation. */
        out = 0.62f * sinf(v->carrier_phase + index * m1)
            + 0.38f * sinf(v->carrier_phase * 1.003f - index * 0.71f * m2)
            + 0.18f * m3;
        break;
    case 3: { /* Shard: 12-bit wavetable/noise hybrid. */
        float stair = floorf((v->carrier_phase / SOPHIE_TAU) * 32.0f) * (SOPHIE_TAU / 32.0f);
        float n = noise_bipolar(&v->rng);
        v->noise_z += (n - v->noise_z) * (0.02f + color * 0.35f);
        out = sinf(stair + index * 0.55f * m1) * (0.85f - metal * 0.25f)
            + v->noise_z * metal * 0.42f;
        break;
    }
    }
    v->feedback_z = soft_clip(out * 1.4f);
    out *= v->amp_env * v->attack;

    out *= p->level * 0.01f;

    float crush = p->crush * 0.01f;
    if (crush >= 0.005f) {
        int rate_div = 1 + (int)(crush * crush * 31.0f);
        if (v->crush_count <= 0) {
            v->crush_hold = out;
            v->crush_count = rate_div;
        }
        out = v->crush_hold;
        v->crush_count--;
        float levels = exp2f(15.0f - crush * 12.0f);
        out = floorf(out * levels + 0.5f) / levels;
    }
    float drive = clampf(p->drive * 0.01f, 0.0f, 1.0f);
    /* Preserve the original curve through 50%, then open up a much hotter
     * range above it. The old normalization kept 100% surprisingly polite;
     * easing it out in the upper half lets the soft clip become audibly
     * destructive without changing the useful low-drive region. */
    float drive_units = drive <= 0.5f
        ? drive * 100.0f
        : 50.0f + 250.0f * powf((drive - 0.5f) * 2.0f, 1.5f);
    float drive_gain = 1.0f + drive_units * 0.075f;
    float norm = soft_clip(drive_gain);
    if (drive > 0.5f) {
        float t = (drive - 0.5f) * 2.0f;
        norm += (1.0f - norm) * 0.72f * t;
    }
    float dry = (soft_clip(out * drive_gain) / norm) * v->velocity;

    /* Per-voice short feedback delay. At sub-10 ms times this behaves like a
     * resonant comb, adding the metallic rings used in Sophie's references.
     * The bounded buffer and one interpolated read keep it cheap and smooth;
     * zero mix is a true bypass apart from the buffer write. */
    float delay_samples = p->ring_time * 0.001f * (float)s->sample_rate;
    delay_samples = clampf(delay_samples, 1.0f, (float)(SOPHIE_MAX_DELAY_SAMPLES - 2));
    float read = (float)v->delay_pos - delay_samples;
    while (read < 0.0f) read += (float)SOPHIE_MAX_DELAY_SAMPLES;
    int r0 = (int)read;
    int rnext = (r0 + 1) % SOPHIE_MAX_DELAY_SAMPLES;
    float frac = read - (float)r0;
    float delayed = v->delay_buf[r0] * (1.0f - frac) + v->delay_buf[rnext] * frac;
    float tone = 0.02f + p->ring_tone * 0.0098f;
    v->delay_lp += tone * (delayed - v->delay_lp);
    delayed = v->delay_lp;
    float ring_fb = p->ring_feedback * 0.01f;
    v->delay_buf[v->delay_pos] = clampf(dry + delayed * ring_fb, -1.0f, 1.0f);
    v->delay_pos = (v->delay_pos + 1) % SOPHIE_MAX_DELAY_SAMPLES;
    float mix = p->ring_mix * 0.01f;
    out = dry * (1.0f - mix) + delayed * mix;

    /* The per-pad filter is deliberately last: crusher, drive and ring delay
     * all create fresh high-frequency material, and the filter must be able to
     * tame the complete sound. It sits outside the delay feedback loop so a
     * cutoff change shapes the output without rewriting the loop's decay. */
    float fc = 40.0f * powf(400.0f, p->cutoff * 0.01f);
    float f = clampf(2.0f * sinf(SOPHIE_PI * fc / (float)s->sample_rate), 0.001f, 0.95f);
    float q = clampf(1.0f - p->resonance * 0.009f, 0.05f, 1.0f);
    v->filter_low += f * v->filter_band;
    float high = out - v->filter_low - q * v->filter_band;
    v->filter_band += f * high;
    float notch = high + v->filter_low;
    if (p->filter_type == 0) out = v->filter_low;
    else if (p->filter_type == 1) out = high;
    else if (p->filter_type == 2) out = notch;
    else if (p->filter_type == 4) out = v->filter_band;
    else if (p->filter_type == 3) {
        /* DJ-style sweep: low-pass at the left, band-pass in the middle,
         * high-pass at the right, with equal-power-ish crossfades. */
        float pos = clampf(p->cutoff * 0.01f, 0.0f, 1.0f);
        if (pos < 0.5f) {
            float t = pos * 2.0f;
            out = v->filter_low * (1.0f - t) + v->filter_band * t;
        } else {
            float t = (pos - 0.5f) * 2.0f;
            out = v->filter_band * (1.0f - t) + high * t;
        }
    }
    return out;
}

static void sophie_render(void *instance, int16_t *out, int frames) {
    sophie_t *s = instance;
    if (!s || !out || frames <= 0) return;

    for (int i = 0; i < frames; ++i) {
        float mono = 0.0f;
        for (int j = 0; j < SOPHIE_VOICES; ++j) mono += render_voice(s, &s->voices[j]);
        mono *= 0.24f;
        int sample = (int)lrintf(clampf(mono, -1.0f, 1.0f) * 30000.0f);
        out[i * 2] = (int16_t)sample;
        out[i * 2 + 1] = (int16_t)sample;
    }
}

static plugin_api_v2_t g_api = {
    .api_version = MOVE_PLUGIN_API_VERSION_2,
    .create_instance = sophie_create,
    .destroy_instance = sophie_destroy,
    .on_midi = sophie_midi,
    .set_param = sophie_set,
    .get_param = sophie_get,
    .get_error = sophie_error,
    .render_block = sophie_render,
};

__attribute__((visibility("default")))
plugin_api_v2_t *move_plugin_init_v2(const host_api_v1_t *host) {
    g_host = host;
    return &g_api;
}
