/*
 * PSX Verb Audio FX Plugin - Authentic PlayStation 1 SPU Reverb
 *
 * EXACT port from CVCHothouse/PSXVerb reference implementation.
 * All preset values use authentic SPU register hex values.
 *
 * PSX SPU Reverb operates at 22.05kHz internally (half of 44.1kHz).
 * This implementation uses:
 * - Halfband 39-tap FIR for 2:1 decimation/interpolation
 * - WorkArea circular int16 buffer emulating SPU RAM with saturating writes
 * - Authentic PSX SPU register values for 6 presets (exact hex from psx-spx)
 * - Full PSX algorithm: Same/Diff reflections -> Comb -> APF1 -> APF2
 *
 * Parameters:
 * - preset: 0-5 (Room, Studio S/M/L, Hall, Space Echo)
 * - decay: Wall reflection feedback scaling (0.0-1.0)
 * - mix: Dry/wet blend (0.0-1.0)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "audio_fx_api_v1.h"

/* Audio FX API v2 - instance-based */
#define AUDIO_FX_API_VERSION_2 2
#define AUDIO_FX_INIT_V2_SYMBOL "move_audio_fx_init_v2"

typedef struct audio_fx_api_v2 {
    uint32_t api_version;
    void* (*create_instance)(const char *module_dir, const char *config_json);
    void (*destroy_instance)(void *instance);
    void (*process_block)(void *instance, int16_t *audio_inout, int frames);
    void (*set_param)(void *instance, const char *key, const char *val);
    int (*get_param)(void *instance, const char *key, char *buf, int buf_len);
} audio_fx_api_v2_t;

typedef audio_fx_api_v2_t* (*audio_fx_init_v2_fn)(const host_api_v1_t *host);

#define SAMPLE_RATE 48000       /* Move hardware sample rate */
#define PSX_NATIVE_RATE 44100   /* PSX native sample rate */
#define PSX_INTERNAL_RATE 22050 /* PSX SPU runs at half sample rate */
#define RATE_SCALE ((float)SAMPLE_RATE / (float)PSX_NATIVE_RATE)  /* ~1.088 */

/* ============================================================================
 * HALFBAND 39-TAP FIR FILTER
 * Exact port from Halfband39.h
 * ============================================================================ */

#define HB_TAPS 39
#define HB_STATE_SIZE 64  /* Power of 2 >= 39 */
#define HB_STATE_MASK 63  /* 0x3F for fast wrap */

/* Halfband FIR coefficients - EXACT from reference Halfband39.h */
static const float g_hb_coeffs[HB_TAPS] = {
    -0.000275135f,  /* 0 */
     0.0f,          /* 1 */
    -0.001467466f,  /* 2 */
     0.0f,          /* 3 */
    -0.004356503f,  /* 4 */
     0.0f,          /* 5 */
    -0.009765625f,  /* 6 */
     0.0f,          /* 7 */
    -0.018493652f,  /* 8 */
     0.0f,          /* 9 */
    -0.031494141f,  /* 10 */
     0.0f,          /* 11 */
    -0.050598145f,  /* 12 */
     0.0f,          /* 13 */
    -0.079833984f,  /* 14 */
     0.0f,          /* 15 */
    -0.130859375f,  /* 16 */
     0.0f,          /* 17 */
    -0.281494141f,  /* 18 */
     0.632812500f,  /* 19 - CENTER TAP */
    -0.281494141f,  /* 20 */
     0.0f,          /* 21 */
    -0.130859375f,  /* 22 */
     0.0f,          /* 23 */
    -0.079833984f,  /* 24 */
     0.0f,          /* 25 */
    -0.050598145f,  /* 26 */
     0.0f,          /* 27 */
    -0.031494141f,  /* 28 */
     0.0f,          /* 29 */
    -0.018493652f,  /* 30 */
     0.0f,          /* 31 */
    -0.009765625f,  /* 32 */
     0.0f,          /* 33 */
    -0.004356503f,  /* 34 */
     0.0f,          /* 35 */
    -0.001467466f,  /* 36 */
     0.0f,          /* 37 */
    -0.000275135f,  /* 38 */
};

/* Polyphase Phase 0: coeffs at even indices [0, 2, 4, ..., 38] */
static const float g_hb_phase0[20] = {
    -0.000275135f, -0.001467466f, -0.004356503f, -0.009765625f,
    -0.018493652f, -0.031494141f, -0.050598145f, -0.079833984f,
    -0.130859375f, -0.281494141f,  0.632812500f, -0.281494141f,
    -0.130859375f, -0.079833984f, -0.050598145f, -0.031494141f,
    -0.018493652f, -0.009765625f, -0.004356503f, -0.001467466f
};

/* Polyphase Phase 1: coeffs at odd indices (all zeros for halfband) */
static const float g_hb_phase1[19] = {
    0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
    0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f
};

typedef struct {
    float state[HB_STATE_SIZE];
    int pos;
} halfband_t;

static void halfband_init(halfband_t *hb) {
    memset(hb->state, 0, sizeof(hb->state));
    hb->pos = 0;
}

/* Decimate: 44.1kHz -> 22.05kHz (2 samples in, 1 out)
 * Exact port from Halfband39::Decimate */
static float halfband_decimate(halfband_t *hb, float x0, float x1) {
    /* Push two new samples */
    hb->state[hb->pos] = x0;
    hb->pos = (hb->pos + 1) & HB_STATE_MASK;  /* wrap at 64 */
    hb->state[hb->pos] = x1;
    hb->pos = (hb->pos + 1) & HB_STATE_MASK;

    /* Convolve with ALL 39 taps (CRITICAL: must process all taps to prevent aliasing) */
    float sum = 0.0f;
    int idx = hb->pos;
    for (int i = 0; i < HB_TAPS; ++i) {
        idx = (idx - 1) & HB_STATE_MASK;
        sum += g_hb_coeffs[i] * hb->state[idx];
    }
    return sum;
}

/* Interpolate: 22.05kHz -> 44.1kHz (1 sample in, 2 out)
 * Exact port from Halfband39::Interpolate */
static void halfband_interpolate(halfband_t *hb, float in_tick, float *out_s0, float *out_s1) {
    /* Push upsampled input (zero-stuff: [in, 0]) */
    hb->state[hb->pos] = in_tick;
    hb->pos = (hb->pos + 1) & HB_STATE_MASK;

    /* Phase 0: even coefficients (produces sample 0) */
    float sum0 = 0.0f;
    int idx = hb->pos;
    for (int i = 0; i < 20; ++i) {  /* 20 even taps */
        idx = (idx - 1) & HB_STATE_MASK;
        sum0 += g_hb_phase0[i] * hb->state[idx];
    }

    /* Phase 1: odd coefficients (produces sample 1) */
    hb->state[hb->pos] = 0.0f;  /* zero-stuffed sample */
    hb->pos = (hb->pos + 1) & HB_STATE_MASK;

    float sum1 = 0.0f;
    idx = hb->pos;
    for (int i = 0; i < 19; ++i) {  /* 19 odd taps */
        idx = (idx - 1) & HB_STATE_MASK;
        sum1 += g_hb_phase1[i] * hb->state[idx];
    }

    *out_s0 = sum0 * 2.0f;  /* Compensate for zero-stuffing */
    *out_s1 = sum1 * 2.0f;
}

/* ============================================================================
 * WORK AREA - SPU RAM EMULATION
 * Exact port from WorkArea.h
 * ============================================================================ */

#define WORK_MAX_SIZE 65536  /* Maximum work area size */

/* Conversion constants - exact from WorkArea.h */
static const float kInt16ToFloat = 1.0f / 32768.0f;
static const float kFloatToInt16 = 32768.0f;

typedef struct {
    int16_t *buf;
    uint32_t size_mask;  /* size - 1, for fast wrap with & */
    uint32_t base;       /* Current base position (advances each tick) */
} workarea_t;


/* Read at relative offset from current base (for IIR: base - 1)
 * Exact port from WorkArea::ReadRelative */
static inline float workarea_read_relative(const workarea_t *wa, int32_t offset) {
    uint32_t idx = (wa->base + offset) & wa->size_mask;
    return (float)wa->buf[idx] * kInt16ToFloat;
}

/* Write at relative offset from current base with 16-bit saturation
 * Exact port from WorkArea::WriteRelative */
static inline void workarea_write_relative(workarea_t *wa, int32_t offset, float value) {
    int32_t val_int = (int32_t)(value * kFloatToInt16);
    /* Saturate to int16 range [-32768, 32767] */
    if (val_int > 32767) val_int = 32767;
    if (val_int < -32768) val_int = -32768;
    uint32_t idx = (wa->base + offset) & wa->size_mask;
    wa->buf[idx] = (int16_t)val_int;
}

/* Advance base pointer (called once per tick)
 * Exact port from WorkArea::Advance */
static inline void workarea_advance(workarea_t *wa, uint32_t n) {
    wa->base = (wa->base + n) & wa->size_mask;
}

/* ============================================================================
 * PSX PRESETS - EXACT SPU Register Values from PsxPreset.h
 * All coefficients stored as int16_t hex values, converted at runtime
 * ============================================================================ */

typedef struct {
    /* All-pass filter parameters */
    uint16_t dAPF1, dAPF2;           /* APF displacement offsets */
    int16_t vIIR;                    /* Reflection volume 1 (IIR feedback) */
    int16_t vCOMB1, vCOMB2, vCOMB3, vCOMB4;  /* Comb filter volumes */
    int16_t vWALL;                   /* Reflection volume 2 (wall reflection) */
    int16_t vAPF1, vAPF2;            /* APF volumes */

    /* Same-side reflection addresses and offsets */
    uint16_t mLSAME, mRSAME;         /* Memory addresses for same-side reflections */
    uint16_t dLSAME, dRSAME;         /* Displacement offsets for same-side */

    /* Different-side reflection addresses and offsets (cross-channel) */
    uint16_t mLDIFF, mRDIFF;         /* Memory addresses for different-side */
    uint16_t dLDIFF, dRDIFF;         /* Displacement offsets for different-side */

    /* Comb filter addresses */
    uint16_t mLCOMB1, mRCOMB1;
    uint16_t mLCOMB2, mRCOMB2;
    uint16_t mLCOMB3, mRCOMB3;
    uint16_t mLCOMB4, mRCOMB4;

    /* All-pass filter addresses */
    uint16_t mLAPF1, mRAPF1;
    uint16_t mLAPF2, mRAPF2;

    /* Input volumes */
    int16_t vLIN, vRIN;

    /* Output volumes */
    int16_t vLOUT, vROUT;

    /* Work area size (in bytes) */
    uint32_t work_size;

    const char *name;
} psx_preset_t;

/* PSX SPU Reverb Presets - EXACT hex values from PsxPreset.h */
static const psx_preset_t g_presets[6] = {
    /* Room - exact from PsxPresets::kRoom */
    {
        .dAPF1 = 0x007D, .dAPF2 = 0x005B,
        .vIIR = 0x6D80, .vCOMB1 = 0x54B8, .vCOMB2 = (int16_t)0xBED0,
        .vCOMB3 = 0x0000, .vCOMB4 = 0x0000,
        .vWALL = (int16_t)0xBA80,
        .vAPF1 = 0x5800, .vAPF2 = 0x5300,
        .mLSAME = 0x04D6, .mRSAME = 0x0333,
        .dLSAME = 0x0334, .dRSAME = 0x01B5,
        .mLDIFF = 0x0000, .mRDIFF = 0x0000,
        .dLDIFF = 0x0000, .dRDIFF = 0x0000,
        .mLCOMB1 = 0x03F0, .mRCOMB1 = 0x0227,
        .mLCOMB2 = 0x0374, .mRCOMB2 = 0x01EF,
        .mLCOMB3 = 0x0000, .mRCOMB3 = 0x0000,
        .mLCOMB4 = 0x0000, .mRCOMB4 = 0x0000,
        .mLAPF1 = 0x01B4, .mRAPF1 = 0x0136,
        .mLAPF2 = 0x00B8, .mRAPF2 = 0x005C,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0x26C0,
        .name = "Room"
    },
    /* Studio Small - exact from PsxPresets::kStudioSmall */
    {
        .dAPF1 = 0x0033, .dAPF2 = 0x0025,
        .vIIR = 0x70F0, .vCOMB1 = 0x4FA8, .vCOMB2 = (int16_t)0xBCE0,
        .vCOMB3 = 0x4410, .vCOMB4 = (int16_t)0xC0F0,
        .vWALL = (int16_t)0x9C00,
        .vAPF1 = 0x5280, .vAPF2 = 0x4EC0,
        .mLSAME = 0x03E4, .mRSAME = 0x031B,
        .dLSAME = 0x031C, .dRSAME = 0x025D,
        .mLDIFF = 0x025C, .mRDIFF = 0x018E,
        .dLDIFF = 0x018F, .dRDIFF = 0x00B5,
        .mLCOMB1 = 0x03A4, .mRCOMB1 = 0x02AF,
        .mLCOMB2 = 0x0372, .mRCOMB2 = 0x0266,
        .mLCOMB3 = 0x022F, .mRCOMB3 = 0x0135,
        .mLCOMB4 = 0x01D2, .mRCOMB4 = 0x00B7,
        .mLAPF1 = 0x00B4, .mRAPF1 = 0x0080,
        .mLAPF2 = 0x004C, .mRAPF2 = 0x0026,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0x1F40,
        .name = "Studio S"
    },
    /* Studio Medium - exact from PsxPresets::kStudioMedium */
    {
        .dAPF1 = 0x00B1, .dAPF2 = 0x007F,
        .vIIR = 0x70F0, .vCOMB1 = 0x4FA8, .vCOMB2 = (int16_t)0xBCE0,
        .vCOMB3 = 0x4510, .vCOMB4 = (int16_t)0xBEF0,
        .vWALL = (int16_t)0xB4C0,
        .vAPF1 = 0x5280, .vAPF2 = 0x4EC0,
        .mLSAME = 0x0904, .mRSAME = 0x076B,
        .dLSAME = 0x076C, .dRSAME = 0x05ED,
        .mLDIFF = 0x05EC, .mRDIFF = 0x042E,
        .dLDIFF = 0x042F, .dRDIFF = 0x0265,
        .mLCOMB1 = 0x0824, .mRCOMB1 = 0x065F,
        .mLCOMB2 = 0x07A2, .mRCOMB2 = 0x0616,
        .mLCOMB3 = 0x050F, .mRCOMB3 = 0x0305,
        .mLCOMB4 = 0x0462, .mRCOMB4 = 0x02B7,
        .mLAPF1 = 0x0264, .mRAPF1 = 0x01B2,
        .mLAPF2 = 0x0100, .mRAPF2 = 0x0080,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0x4840,
        .name = "Studio M"
    },
    /* Studio Large - exact from PsxPresets::kStudioLarge */
    {
        .dAPF1 = 0x00E3, .dAPF2 = 0x00A9,
        .vIIR = 0x6F60, .vCOMB1 = 0x4FA8, .vCOMB2 = (int16_t)0xBCE0,
        .vCOMB3 = 0x4510, .vCOMB4 = (int16_t)0xBEF0,
        .vWALL = (int16_t)0xA680,
        .vAPF1 = 0x5680, .vAPF2 = 0x52C0,
        .mLSAME = 0x0DFB, .mRSAME = 0x0B58,
        .dLSAME = 0x0B59, .dRSAME = 0x08DA,
        .mLDIFF = 0x08D9, .mRDIFF = 0x05E9,
        .dLDIFF = 0x05EA, .dRDIFF = 0x031D,
        .mLCOMB1 = 0x0D09, .mRCOMB1 = 0x0A3C,
        .mLCOMB2 = 0x0BD9, .mRCOMB2 = 0x0973,
        .mLCOMB3 = 0x07EC, .mRCOMB3 = 0x04B0,
        .mLCOMB4 = 0x06EF, .mRCOMB4 = 0x03D2,
        .mLAPF1 = 0x031C, .mRAPF1 = 0x0238,
        .mLAPF2 = 0x0154, .mRAPF2 = 0x00AA,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0x6FE0,
        .name = "Studio L"
    },
    /* Hall - exact from PsxPresets::kHall */
    {
        .dAPF1 = 0x01A5, .dAPF2 = 0x0139,
        .vIIR = 0x6000, .vCOMB1 = 0x5000, .vCOMB2 = 0x4C00,
        .vCOMB3 = (int16_t)0xB800, .vCOMB4 = (int16_t)0xBC00,
        .vWALL = (int16_t)0xC000,
        .vAPF1 = 0x6000, .vAPF2 = 0x5C00,
        .mLSAME = 0x15BA, .mRSAME = 0x11BB,
        .dLSAME = 0x11C0, .dRSAME = 0x0DC3,
        .mLDIFF = 0x0DC0, .mRDIFF = 0x09C1,
        .dLDIFF = 0x09C2, .dRDIFF = 0x05C1,
        .mLCOMB1 = 0x14C2, .mRCOMB1 = 0x10BD,
        .mLCOMB2 = 0x11BC, .mRCOMB2 = 0x0DC1,
        .mLCOMB3 = 0x0BC4, .mRCOMB3 = 0x07C1,
        .mLCOMB4 = 0x0A00, .mRCOMB4 = 0x06CD,
        .mLAPF1 = 0x05C0, .mRAPF1 = 0x041A,
        .mLAPF2 = 0x0274, .mRAPF2 = 0x013A,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0xADE0,
        .name = "Hall"
    },
    /* Space Echo - exact from PsxPresets::kSpaceEcho */
    {
        .dAPF1 = 0x033D, .dAPF2 = 0x0231,
        .vIIR = 0x7E00, .vCOMB1 = 0x5000, .vCOMB2 = (int16_t)0xB400,
        .vCOMB3 = (int16_t)0xB000, .vCOMB4 = 0x4C00,
        .vWALL = (int16_t)0xB000,
        .vAPF1 = 0x6000, .vAPF2 = 0x5400,
        .mLSAME = 0x1ED6, .mRSAME = 0x1A31,
        .dLSAME = 0x1A32, .dRSAME = 0x15EF,
        .mLDIFF = 0x15EE, .mRDIFF = 0x1055,
        .dLDIFF = 0x1056, .dRDIFF = 0x0AE1,
        .mLCOMB1 = 0x1D14, .mRCOMB1 = 0x183B,
        .mLCOMB2 = 0x1BC2, .mRCOMB2 = 0x16B2,
        .mLCOMB3 = 0x1334, .mRCOMB3 = 0x0F2D,
        .mLCOMB4 = 0x11F6, .mRCOMB4 = 0x0C5D,
        .mLAPF1 = 0x0AE0, .mRAPF1 = 0x07A2,
        .mLAPF2 = 0x0464, .mRAPF2 = 0x0232,
        .vLIN = (int16_t)0x8000, .vRIN = (int16_t)0x8000,
        .vLOUT = (int16_t)0x8000, .vROUT = (int16_t)0x8000,
        .work_size = 0xF6C0,
        .name = "Space Echo"
    }
};

/* ============================================================================
 * SCALED PRESET - Runtime float values converted from int16
 * Matches PsxReverb.h ScaledPreset struct
 * ============================================================================ */

typedef struct {
    uint16_t dAPF1, dAPF2;
    uint16_t dLSAME, dRSAME, dLDIFF, dRDIFF;
    uint16_t mLSAME, mRSAME, mLDIFF, mRDIFF;
    uint16_t mLCOMB1, mRCOMB1, mLCOMB2, mRCOMB2;
    uint16_t mLCOMB3, mRCOMB3, mLCOMB4, mRCOMB4;
    uint16_t mLAPF1, mRAPF1, mLAPF2, mRAPF2;
    float vIIR_f, vCOMB1_f, vCOMB2_f, vCOMB3_f, vCOMB4_f;
    float vWALL_f, vAPF1_f, vAPF2_f, vLIN_f, vRIN_f;
    float vLOUT_f, vROUT_f;
} scaled_preset_t;

/* ============================================================================
 * SHARED STATE (used by V2 API)
 * ============================================================================ */

static const host_api_v1_t *g_host = NULL;

/* Logging helper */
static void fx_log(const char *msg) {
    if (g_host && g_host->log) {
        char buf[256];
        snprintf(buf, sizeof(buf), "[psxverb] %s", msg);
        g_host->log(buf);
    }
}

/* Next power of 2 - exact from PsxReverb.h */
static uint32_t next_pow2(uint32_t v) {
    v--;
    v |= v >> 1;
    v |= v >> 2;
    v |= v >> 4;
    v |= v >> 8;
    v |= v >> 16;
    v++;
    return v;
}

/* Convert SPU signed 16-bit coefficient to float [-1.0, 1.0)
 * Exact from PsxPreset.h CoeffToFloat */
static inline float coeff_to_float(int16_t coeff) {
    return (float)coeff / 32768.0f;
}

/* Clamp float value to [min, max] - matches std::clamp */
static inline float clamp_f(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

/* Absolute value for float */
static inline float abs_f(float v) {
    return v < 0.0f ? -v : v;
}

/* Max of two floats */
static inline float max_f(float a, float b) {
    return a > b ? a : b;
}

/* Helper to extract a JSON number value by key */
static int json_get_number(const char *json, const char *key, float *out) {
    char search[64];
    snprintf(search, sizeof(search), "\"%s\":", key);
    const char *pos = strstr(json, search);
    if (!pos) return -1;
    pos += strlen(search);
    while (*pos == ' ') pos++;
    *out = (float)atof(pos);
    return 0;
}

/* ============================================================================
 * AUDIO FX API v2 - Instance-based
 * ============================================================================ */

typedef struct {
    int16_t *work_buffer;
    int preset_idx;
    float decay;
    float mix;
    float input_gain;
    float reverb_level;
    scaled_preset_t current;
    scaled_preset_t base;
    workarea_t work;
    halfband_t down_l, down_r;
    halfband_t up_l, up_r;
} psxverb_instance_t;

/* Helper to scale delay value from 44.1kHz to actual sample rate */
static inline uint16_t scale_delay(uint16_t delay) {
    return (uint16_t)(delay * RATE_SCALE);
}

/* v2 helper: scale preset with instance state - matches reference PsxReverb.h ScalePreset() */
static void v2_scale_preset(psxverb_instance_t *inst, const psx_preset_t *src, scaled_preset_t *dst) {
    /* Scale all delay offsets from 44.1kHz to 48kHz */
    dst->dAPF1 = scale_delay(src->dAPF1);
    dst->dAPF2 = scale_delay(src->dAPF2);
    dst->dLSAME = scale_delay(src->dLSAME);
    dst->dRSAME = scale_delay(src->dRSAME);
    dst->dLDIFF = scale_delay(src->dLDIFF);
    dst->dRDIFF = scale_delay(src->dRDIFF);

    /* Scale all memory addresses */
    dst->mLSAME = scale_delay(src->mLSAME);
    dst->mRSAME = scale_delay(src->mRSAME);
    dst->mLDIFF = scale_delay(src->mLDIFF);
    dst->mRDIFF = scale_delay(src->mRDIFF);
    dst->mLCOMB1 = scale_delay(src->mLCOMB1);
    dst->mRCOMB1 = scale_delay(src->mRCOMB1);
    dst->mLCOMB2 = scale_delay(src->mLCOMB2);
    dst->mRCOMB2 = scale_delay(src->mRCOMB2);
    dst->mLCOMB3 = scale_delay(src->mLCOMB3);
    dst->mRCOMB3 = scale_delay(src->mRCOMB3);
    dst->mLCOMB4 = scale_delay(src->mLCOMB4);
    dst->mRCOMB4 = scale_delay(src->mRCOMB4);
    dst->mLAPF1 = scale_delay(src->mLAPF1);
    dst->mRAPF1 = scale_delay(src->mRAPF1);
    dst->mLAPF2 = scale_delay(src->mLAPF2);
    dst->mRAPF2 = scale_delay(src->mRAPF2);

    /* Convert coefficients to float */
    dst->vIIR_f = coeff_to_float(src->vIIR);
    dst->vCOMB1_f = coeff_to_float(src->vCOMB1);
    dst->vCOMB2_f = coeff_to_float(src->vCOMB2);
    dst->vCOMB3_f = coeff_to_float(src->vCOMB3);
    dst->vCOMB4_f = coeff_to_float(src->vCOMB4);
    dst->vWALL_f = coeff_to_float(src->vWALL);
    dst->vAPF1_f = coeff_to_float(src->vAPF1);
    dst->vAPF2_f = coeff_to_float(src->vAPF2);
    dst->vLIN_f = coeff_to_float(src->vLIN);
    dst->vRIN_f = coeff_to_float(src->vRIN);
    dst->vLOUT_f = coeff_to_float(src->vLOUT);
    dst->vROUT_f = coeff_to_float(src->vROUT);
}

/* v2 helper: update decay - adaptive formula from shared_dsp/PsxReverb.h
 * Automatically calculates safe maximum scale per preset to prevent oscillation.
 * - 0-50% decay maps to [0.5x, 1.0x] (below authentic to authentic PSX)
 * - 50-100% decay maps to [1.0x, maxScale] (authentic to maximum safe)
 * - Final value clamped to [-0.995, 0.995] to prevent runaway feedback
 */
static void v2_update_decay(psxverb_instance_t *inst) {
    float base = inst->base.vWALL_f;
    if (base < 0) base = -base;  /* abs() */
    if (base < 1e-5f) base = 1e-5f;  /* avoid div by zero */

    /* Calculate maximum safe scale for this preset */
    float max_scale = 0.99f / base;
    if (max_scale < 0.5f) max_scale = 0.5f;
    if (max_scale > 10.0f) max_scale = 10.0f;

    float min_scale = 0.5f;
    float mid_scale = 1.0f;  /* authentic PSX at 50% */
    float mid_norm = 0.5f;

    float wall_scale;
    if (inst->decay <= mid_norm) {
        /* 0-50%: linear from 0.5x to 1.0x */
        float t = inst->decay / mid_norm;
        wall_scale = min_scale + t * (mid_scale - min_scale);
    } else {
        /* 50-100%: linear from 1.0x to maxScale */
        float t = (inst->decay - mid_norm) / (1.0f - mid_norm);
        wall_scale = mid_scale + t * (max_scale - mid_scale);
    }

    float target = inst->base.vWALL_f * wall_scale;
    /* Clamp to stable range */
    if (target > 0.995f) target = 0.995f;
    if (target < -0.995f) target = -0.995f;
    inst->current.vWALL_f = target;
}

/* v2 helper: apply preset */
static void v2_apply_preset(psxverb_instance_t *inst, int idx) {
    if (idx < 0 || idx >= 6) return;
    inst->preset_idx = idx;
    const psx_preset_t *p = &g_presets[idx];

    v2_scale_preset(inst, p, &inst->base);
    inst->current = inst->base;

    /* Apply input gain and reverb level */
    float in_scale = inst->input_gain * 2.0f;
    inst->current.vLIN_f = inst->base.vLIN_f * in_scale;
    inst->current.vRIN_f = inst->base.vRIN_f * in_scale;
    float out_scale = inst->reverb_level * 4.0f;
    inst->current.vLOUT_f = inst->base.vLOUT_f * out_scale;
    inst->current.vROUT_f = inst->base.vROUT_f * out_scale;

    v2_update_decay(inst);

    /* Initialize work area - matches reference PsxReverb.h Init()
     * work_size is in bytes at 44.1kHz, convert to samples at 48kHz */
    uint32_t work_size = next_pow2((uint32_t)(p->work_size * RATE_SCALE / sizeof(int16_t)));
    if (work_size > WORK_MAX_SIZE) work_size = WORK_MAX_SIZE;

    memset(inst->work_buffer, 0, work_size * sizeof(int16_t));
    inst->work.buf = inst->work_buffer;
    inst->work.size_mask = work_size - 1;
    inst->work.base = 0;
}

/* v2 API: create instance */
static void* v2_create_instance(const char *module_dir, const char *config_json) {
    psxverb_instance_t *inst = (psxverb_instance_t*)calloc(1, sizeof(psxverb_instance_t));
    if (!inst) return NULL;

    inst->work_buffer = (int16_t*)calloc(WORK_MAX_SIZE, sizeof(int16_t));
    if (!inst->work_buffer) {
        free(inst);
        return NULL;
    }

    /* Initialize state */
    inst->preset_idx = 4;       /* Default: Hall */
    inst->decay = 0.7f;         /* With formula 0.5+(d*0.5), 0.7 gives 0.85x wall feedback */
    inst->mix = 0.35f;
    inst->input_gain = 0.5f;
    inst->reverb_level = 0.5f;

    /* Initialize halfband filters */
    halfband_init(&inst->down_l);
    halfband_init(&inst->down_r);
    halfband_init(&inst->up_l);
    halfband_init(&inst->up_r);

    /* Apply default preset */
    v2_apply_preset(inst, inst->preset_idx);

    fx_log("PSX Verb v2 instance created");
    return inst;
}

/* v2 API: destroy instance */
static void v2_destroy_instance(void *instance) {
    psxverb_instance_t *inst = (psxverb_instance_t*)instance;
    if (!inst) return;

    if (inst->work_buffer) {
        free(inst->work_buffer);
    }
    free(inst);
    fx_log("PSX Verb v2 instance destroyed");
}

/* v2 API: process block */
static void v2_process_block(void *instance, int16_t *audio_inout, int frames) {
    psxverb_instance_t *inst = (psxverb_instance_t*)instance;
    if (!inst) return;

    const scaled_preset_t *p = &inst->current;

    for (int i = 0; i < frames; i += 2) {
        if (i + 1 >= frames) break;

        float in_l0 = audio_inout[i * 2] / 32768.0f;
        float in_r0 = audio_inout[i * 2 + 1] / 32768.0f;
        float in_l1 = audio_inout[(i + 1) * 2] / 32768.0f;
        float in_r1 = audio_inout[(i + 1) * 2 + 1] / 32768.0f;

        float Lin = halfband_decimate(&inst->down_l, in_l0, in_l1) * p->vLIN_f;
        float Rin = halfband_decimate(&inst->down_r, in_r0, in_r1) * p->vRIN_f;

        /* Same-side reflection */
        float lsame_fb = workarea_read_relative(&inst->work, p->dLSAME);
        float lsame_iir = workarea_read_relative(&inst->work, p->mLSAME - 1);
        float lsame_out = (Lin + lsame_fb * p->vWALL_f - lsame_iir) * p->vIIR_f + lsame_iir;
        workarea_write_relative(&inst->work, p->mLSAME, lsame_out);

        float rsame_fb = workarea_read_relative(&inst->work, p->dRSAME);
        float rsame_iir = workarea_read_relative(&inst->work, p->mRSAME - 1);
        float rsame_out = (Rin + rsame_fb * p->vWALL_f - rsame_iir) * p->vIIR_f + rsame_iir;
        workarea_write_relative(&inst->work, p->mRSAME, rsame_out);

        /* Different-side reflection */
        float ldiff_fb = workarea_read_relative(&inst->work, p->dRDIFF);
        float ldiff_iir = workarea_read_relative(&inst->work, p->mLDIFF - 1);
        float ldiff_out = (Lin + ldiff_fb * p->vWALL_f - ldiff_iir) * p->vIIR_f + ldiff_iir;
        workarea_write_relative(&inst->work, p->mLDIFF, ldiff_out);

        float rdiff_fb = workarea_read_relative(&inst->work, p->dLDIFF);
        float rdiff_iir = workarea_read_relative(&inst->work, p->mRDIFF - 1);
        float rdiff_out = (Rin + rdiff_fb * p->vWALL_f - rdiff_iir) * p->vIIR_f + rdiff_iir;
        workarea_write_relative(&inst->work, p->mRDIFF, rdiff_out);

        /* Comb filter bank */
        float Lout = p->vCOMB1_f * workarea_read_relative(&inst->work, p->mLCOMB1) +
                     p->vCOMB2_f * workarea_read_relative(&inst->work, p->mLCOMB2) +
                     p->vCOMB3_f * workarea_read_relative(&inst->work, p->mLCOMB3) +
                     p->vCOMB4_f * workarea_read_relative(&inst->work, p->mLCOMB4);

        float Rout = p->vCOMB1_f * workarea_read_relative(&inst->work, p->mRCOMB1) +
                     p->vCOMB2_f * workarea_read_relative(&inst->work, p->mRCOMB2) +
                     p->vCOMB3_f * workarea_read_relative(&inst->work, p->mRCOMB3) +
                     p->vCOMB4_f * workarea_read_relative(&inst->work, p->mRCOMB4);

        /* All-pass filter 1 */
        float lapf1_del = workarea_read_relative(&inst->work, p->mLAPF1 - p->dAPF1);
        Lout -= p->vAPF1_f * lapf1_del;
        workarea_write_relative(&inst->work, p->mLAPF1, Lout);
        Lout = Lout * p->vAPF1_f + lapf1_del;

        float rapf1_del = workarea_read_relative(&inst->work, p->mRAPF1 - p->dAPF1);
        Rout -= p->vAPF1_f * rapf1_del;
        workarea_write_relative(&inst->work, p->mRAPF1, Rout);
        Rout = Rout * p->vAPF1_f + rapf1_del;

        /* All-pass filter 2 */
        float lapf2_del = workarea_read_relative(&inst->work, p->mLAPF2 - p->dAPF2);
        Lout -= p->vAPF2_f * lapf2_del;
        workarea_write_relative(&inst->work, p->mLAPF2, Lout);
        Lout = Lout * p->vAPF2_f + lapf2_del;

        float rapf2_del = workarea_read_relative(&inst->work, p->mRAPF2 - p->dAPF2);
        Rout -= p->vAPF2_f * rapf2_del;
        workarea_write_relative(&inst->work, p->mRAPF2, Rout);
        Rout = Rout * p->vAPF2_f + rapf2_del;

        workarea_advance(&inst->work, 1);

        float out_l0, out_l1, out_r0, out_r1;
        halfband_interpolate(&inst->up_l, Lout * p->vLOUT_f, &out_l0, &out_l1);
        halfband_interpolate(&inst->up_r, Rout * p->vROUT_f, &out_r0, &out_r1);

        float dry_mix = 1.0f - inst->mix;
        float wet_mix = inst->mix;

        float final_l0 = clamp_f(in_l0 * dry_mix + out_l0 * wet_mix, -1.0f, 1.0f);
        float final_r0 = clamp_f(in_r0 * dry_mix + out_r0 * wet_mix, -1.0f, 1.0f);
        float final_l1 = clamp_f(in_l1 * dry_mix + out_l1 * wet_mix, -1.0f, 1.0f);
        float final_r1 = clamp_f(in_r1 * dry_mix + out_r1 * wet_mix, -1.0f, 1.0f);

        audio_inout[i * 2] = (int16_t)(final_l0 * 32767.0f);
        audio_inout[i * 2 + 1] = (int16_t)(final_r0 * 32767.0f);
        audio_inout[(i + 1) * 2] = (int16_t)(final_l1 * 32767.0f);
        audio_inout[(i + 1) * 2 + 1] = (int16_t)(final_r1 * 32767.0f);
    }
}

/* v2 API: set parameter */
static void v2_set_param(void *instance, const char *key, const char *val) {
    psxverb_instance_t *inst = (psxverb_instance_t*)instance;
    if (!inst || !key || !val) return;

    /* State restore from patch save */
    if (strcmp(key, "state") == 0) {
        float v;
        int preset_changed = 0;
        if (json_get_number(val, "preset", &v) == 0) {
            int idx = (int)v;
            if (idx >= 0 && idx < 6 && idx != inst->preset_idx) {
                inst->preset_idx = idx;
                preset_changed = 1;
            }
        }
        if (json_get_number(val, "decay", &v) == 0) { inst->decay = clamp_f(v, 0.0f, 1.0f); }
        if (json_get_number(val, "mix", &v) == 0) { inst->mix = clamp_f(v, 0.0f, 1.0f); }
        if (json_get_number(val, "input_gain", &v) == 0) { inst->input_gain = clamp_f(v, 0.0f, 1.0f); }
        if (json_get_number(val, "reverb_level", &v) == 0) { inst->reverb_level = clamp_f(v, 0.0f, 1.0f); }

        /* Apply preset (which also updates decay and gain settings) */
        if (preset_changed) {
            v2_apply_preset(inst, inst->preset_idx);
        } else {
            /* Update derived values without changing preset */
            v2_update_decay(inst);
            float in_scale = inst->input_gain * 2.0f;
            inst->current.vLIN_f = inst->base.vLIN_f * in_scale;
            inst->current.vRIN_f = inst->base.vRIN_f * in_scale;
            float out_scale = inst->reverb_level * 4.0f;
            inst->current.vLOUT_f = inst->base.vLOUT_f * out_scale;
            inst->current.vROUT_f = inst->base.vROUT_f * out_scale;
        }
        return;
    }

    if (strcmp(key, "preset") == 0 || strcmp(key, "model") == 0) {
        int idx = -1;
        /* Accept both string names and numeric indices */
        if (strcmp(val, "Room") == 0) idx = 0;
        else if (strcmp(val, "Studio S") == 0) idx = 1;
        else if (strcmp(val, "Studio M") == 0) idx = 2;
        else if (strcmp(val, "Studio L") == 0) idx = 3;
        else if (strcmp(val, "Hall") == 0) idx = 4;
        else if (strcmp(val, "Space Echo") == 0) idx = 5;
        else idx = atoi(val);
        if (idx >= 0 && idx < 6 && idx != inst->preset_idx) {
            v2_apply_preset(inst, idx);
        }
    } else if (strcmp(key, "decay") == 0) {
        inst->decay = clamp_f(atof(val), 0.0f, 1.0f);
        v2_update_decay(inst);
    } else if (strcmp(key, "mix") == 0) {
        inst->mix = clamp_f(atof(val), 0.0f, 1.0f);
    } else if (strcmp(key, "input_gain") == 0) {
        inst->input_gain = clamp_f(atof(val), 0.0f, 1.0f);
        float in_scale = inst->input_gain * 2.0f;
        inst->current.vLIN_f = inst->base.vLIN_f * in_scale;
        inst->current.vRIN_f = inst->base.vRIN_f * in_scale;
    } else if (strcmp(key, "reverb_level") == 0) {
        inst->reverb_level = clamp_f(atof(val), 0.0f, 1.0f);
        float out_scale = inst->reverb_level * 4.0f;
        inst->current.vLOUT_f = inst->base.vLOUT_f * out_scale;
        inst->current.vROUT_f = inst->base.vROUT_f * out_scale;
    }
}

/* v2 API: get parameter */
static int v2_get_param(void *instance, const char *key, char *buf, int buf_len) {
    psxverb_instance_t *inst = (psxverb_instance_t*)instance;
    if (!inst || !key || !buf || buf_len <= 0) return -1;

    if (strcmp(key, "preset") == 0 || strcmp(key, "model") == 0) {
        /* Return preset name for enum type compatibility */
        return snprintf(buf, buf_len, "%s", g_presets[inst->preset_idx].name);
    } else if (strcmp(key, "preset_name") == 0 || strcmp(key, "model_name") == 0) {
        return snprintf(buf, buf_len, "%s", g_presets[inst->preset_idx].name);
    } else if (strcmp(key, "preset_count") == 0) {
        return snprintf(buf, buf_len, "6");
    } else if (strcmp(key, "decay") == 0) {
        return snprintf(buf, buf_len, "%.2f", (double)inst->decay);
    } else if (strcmp(key, "mix") == 0) {
        return snprintf(buf, buf_len, "%.2f", (double)inst->mix);
    } else if (strcmp(key, "input_gain") == 0) {
        return snprintf(buf, buf_len, "%.2f", (double)inst->input_gain);
    } else if (strcmp(key, "reverb_level") == 0) {
        return snprintf(buf, buf_len, "%.2f", (double)inst->reverb_level);
    } else if (strcmp(key, "name") == 0) {
        return snprintf(buf, buf_len, "PSX Verb");
    } else if (strcmp(key, "state") == 0) {
        return snprintf(buf, buf_len,
            "{\"preset\":%d,\"decay\":%.4f,\"mix\":%.4f,"
            "\"input_gain\":%.4f,\"reverb_level\":%.4f}",
            inst->preset_idx, inst->decay, inst->mix,
            inst->input_gain, inst->reverb_level);
    }

    /* UI hierarchy for shadow parameter editor - flat list */
    if (strcmp(key, "ui_hierarchy") == 0) {
        const char *hierarchy = "{"
            "\"modes\":null,"
            "\"levels\":{"
                "\"root\":{"
                    "\"children\":null,"
                    "\"knobs\":[\"model\",\"decay\",\"mix\",\"reverb_level\"],"
                    "\"params\":[\"model\",\"decay\",\"mix\",\"input_gain\",\"reverb_level\"]"
                "}"
            "}"
        "}";
        int len = strlen(hierarchy);
        if (len < buf_len) {
            strcpy(buf, hierarchy);
            return len;
        }
        return -1;
    }

    /* Chain params metadata for shadow parameter editor */
    if (strcmp(key, "chain_params") == 0) {
        const char *params_json = "["
            "{\"key\":\"model\",\"name\":\"Model\",\"type\":\"enum\",\"options\":[\"Room\",\"Studio S\",\"Studio M\",\"Studio L\",\"Hall\",\"Space Echo\"],\"default\":\"Hall\"},"
            "{\"key\":\"decay\",\"name\":\"Decay\",\"type\":\"float\",\"min\":0,\"max\":1,\"default\":0.7,\"step\":0.01},"
            "{\"key\":\"mix\",\"name\":\"Mix\",\"type\":\"float\",\"min\":0,\"max\":1,\"default\":0.35,\"step\":0.01},"
            "{\"key\":\"input_gain\",\"name\":\"Input\",\"type\":\"float\",\"min\":0,\"max\":1,\"default\":0.5,\"step\":0.01},"
            "{\"key\":\"reverb_level\",\"name\":\"Level\",\"type\":\"float\",\"min\":0,\"max\":1,\"default\":0.5,\"step\":0.01}"
        "]";
        int len = strlen(params_json);
        if (len < buf_len) {
            strcpy(buf, params_json);
            return len;
        }
        return -1;
    }

    return -1;
}

/* v2 API table */
static audio_fx_api_v2_t g_fx_api_v2;

audio_fx_api_v2_t* move_audio_fx_init_v2(const host_api_v1_t *host) {
    g_host = host;

    memset(&g_fx_api_v2, 0, sizeof(g_fx_api_v2));
    g_fx_api_v2.api_version = AUDIO_FX_API_VERSION_2;
    g_fx_api_v2.create_instance = v2_create_instance;
    g_fx_api_v2.destroy_instance = v2_destroy_instance;
    g_fx_api_v2.process_block = v2_process_block;
    g_fx_api_v2.set_param = v2_set_param;
    g_fx_api_v2.get_param = v2_get_param;

    fx_log("PSX Verb v2 API initialized");
    return &g_fx_api_v2;
}
