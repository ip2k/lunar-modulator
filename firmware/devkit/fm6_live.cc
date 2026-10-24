/* SPDX-License-Identifier: MIT */
#include "fm6_live.h"
#include "fm1_engine.h"
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_dx7;
static unsigned char memory[65536] __attribute__((aligned(16)));
static float output[128];
static void *instance;
static uint32_t case_frame, total_frames;
static uint32_t pcm_hash;
static struct lunar_fm6_live_status state;
static const unsigned patches[] = {0, 19, 25};
static const unsigned voices[] = {1, 4, 8, 12};

extern "C" int lunar_devkit_fm6_live_init(void) {
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, 44100.f, 64};
    const fm1_engine_t *e = &fm1_engine_dx7;
    if (e->instance_size(&host) > sizeof(memory)) return 0;
    if (instance) e->destroy(instance);
    instance = e->create(memory, &host);
    case_frame = total_frames = 0;
    pcm_hash = 2166136261u;
    memset(&state, 0, sizeof(state));
    return instance != 0;
}

extern "C" void lunar_devkit_fm6_live_render(int16_t *out) {
    const fm1_engine_t *e = &fm1_engine_dx7;
    if (!instance) { memset(out, 0, 64 * 4 * sizeof(*out)); return; }
    if (!case_frame) {
        state.patch = patches[state.test_case / 4];
        state.voices = voices[state.test_case % 4];
        e->set_param(instance, 0, static_cast<float>(state.patch));
        for (unsigned n = 0; n < state.voices; ++n)
            e->note_on(instance, 36 + n * 3, 100);
        ++state.note_batches;
    }
    /* Block boundaries are deliberate. Six seconds held, two seconds release;
     * all 12 patch/polyphony cases repeat in a 96-second cycle. */
    if (case_frame < 6 * 44100u && case_frame + 64 >= 6 * 44100u) {
        for (unsigned n = 0; n < state.voices; ++n)
            e->note_off(instance, 36 + n * 3);
        ++state.note_batches;
    }
    e->render(instance, output, 64);
    for (unsigned i = 0; i < 64; ++i) for (unsigned ch = 0; ch < 2; ++ch) {
        float x = output[2*i+ch];
        uint32_t bits; memcpy(&bits, &x, sizeof(bits));
        if ((bits & 0x7f800000u) == 0x7f800000u) { ++state.invalid; x = 0; }
        /* Quiet fixed -18 dB gain, with the same ~50 ms startup ramp as the
         * reference. Bound before float-to-int conversion, including infinity. */
        x *= 4096.f;
        if (total_frames + i < 2205u) x *= (total_frames + i + 1) / 2205.f;
        if (x > 32767.f) { ++state.clipped; x = 32767.f; }
        if (x < -32768.f) { ++state.clipped; x = -32768.f; }
        out[4*i+ch] = out[4*i+ch+2] = static_cast<int16_t>(x);
        /* Fingerprint the exact converted stereo stream, not float samples.
         * Explicit byte order makes host and target comparisons independent
         * of the host's native endianness. No UART work in the audio IRQ. */
        const uint16_t word = static_cast<uint16_t>(out[4*i+ch]);
        pcm_hash = (pcm_hash ^ (word & 255u)) * 16777619u;
        pcm_hash = (pcm_hash ^ (word >> 8)) * 16777619u;
    }
    /* Saturate startup counter; long soaks must never restart the ramp. */
    if (total_frames < 2205u) total_frames += 64;
    case_frame += 64;
    if (case_frame >= 8 * 44100u) {
        state.completed_case = state.test_case;
        state.completed_hash = pcm_hash;
        ++state.completed_cases;
        pcm_hash = 2166136261u;
        case_frame = 0;
        if (++state.test_case == 12) { state.test_case = 0; ++state.cycles; }
    }
}

extern "C" void lunar_devkit_fm6_live_status(struct lunar_fm6_live_status *out) {
    *out = state;
}
