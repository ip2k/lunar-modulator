// drum_voices.h -- the four voices of Drums (drums.cc) that this repository
// writes itself: rim, clap, cowbell and cymbal. The kick, snare and hi-hat
// voices are Mutable Instruments Plaits' drum classes, used as they are.
//
// Each voice follows the structure of a published analysis of the analogue
// circuit it is after; the code, the constants and the simplifications are
// ours, except three small pieces taken from Plaits' hi_hat.h (Emilie Gillet,
// MIT, credited below and in the engine's credits): the SwingVCA curve, the
// six-oscillator bank's ratios, and the cymbal's clocked noise blended in
// against the metal (Plaits' own addition to its 808 hat, "not at all part
// of the 808 circuit" in its comment). Nothing else is copied from anywhere:
//   - Cowbell: Werner, Abel and Smith, "More cowbell: a physically-informed,
//     circuit-bendable, digital model of the TR-808 cowbell" (AES 137th
//     Convention, paper 9207, 2014): two rectangular oscillators near 540
//     and 800 Hz at a 0.4798 duty cycle, an envelope with a sharp attack and
//     a two-stage decay, swing-type VCAs, a band-pass [verified: the
//     paper's text]. The envelope times (about 50 ms, then about 500 ms) and
//     the band-pass centre (about 880 Hz) are a blog's, not the paper's
//     [reported: Baratatronix].
//   - Cymbal: Werner, Abel and Smith, "The TR-808 cymbal: a physically-
//     informed, circuit-bendable, digital model" (ICMC|SMC 2014, CC BY 3.0):
//     a bank of six square oscillators summed into band-passes near 3,440
//     and 7,100 Hz, swing-type VCAs on separate envelopes, high-passes
//     [verified: the paper's text]. Here: two bands, two envelopes, one
//     high-pass. The bank is the one Plaits' 808 hi-hat uses (its
//     SquareNoise ratios), which is the paper's set with its four fixed
//     oscillators an octave up, so the hats and cymbals share one metal;
//     Snap blends in clocked noise as Plaits' HiHat does (the same clock
//     rate, 16 to 32 times f0, and the same squared amount).
//   - Clap: the TR-808 hand clap as described by Baratatronix: white noise
//     through a band-pass near 1 kHz, a sawtooth envelope of three short
//     bursts and a longer fourth, and a separate decaying "reverb" envelope,
//     two VCAs in parallel [reported].
//   - Rim: two band-passes pinged by a short pulse, after the TR-808 rim
//     shot's two bridged-T oscillators near 455 Hz and 1,667 Hz [reported],
//     clipped and high-passed; the structure Mutable Instruments Peaks uses
//     for its snare body (MIT).
//
// The swing VCA is Plaits' SwingVCA curve (plaits/dsp/drums/hi_hat.h, Emilie
// Gillet, MIT), written out here so these voices need no Plaits header but
// dsp.h. Every voice renders at Plaits' rate (47,872.34 Hz, the rate the
// kit runs at; drums.cc) in Plaits' 12-sample blocks, draws its noise from
// a state the caller keeps (one per pad), and uses no libm: frequencies go
// through stmlib's lookup tables and polynomial tangents, decays are
// 1 - 1/(time x rate) per sample.
//
// MIT licence (this file).

#ifndef FM1_DRUM_VOICES_H_
#define FM1_DRUM_VOICES_H_

#include <stddef.h>
#include <stdint.h>

#include "stmlib/dsp/dsp.h"
#include "stmlib/dsp/filter.h"
#include "stmlib/dsp/units.h"

#include "plaits/dsp/dsp.h"

namespace fm1 {
namespace drum_voices {

const float kRate = plaits::kCorrectedSampleRate;

// stmlib's random generator (stmlib/utils/random.h), on a state the caller
// keeps: the same sequence Random::GetWord gives from that state.
inline uint32_t NextWord(uint32_t *state) {
  *state = *state * 1664525u + 1013904223u;
  return *state;
}

// White noise in [-1, 1).
inline float Noise(uint32_t *state) {
  return static_cast<float>(NextWord(state)) * (1.0f / 2147483648.0f) - 1.0f;
}

// The per-sample factor of an exponential decay with this time constant in
// seconds, without libm: 1 - 1 / (time x rate), within 0.1 % of exp(-1 /
// (time x rate)) for any time over 10 ms.
inline float DecayFactor(float seconds) {
  const float samples = seconds * kRate;
  return samples > 1.0f ? 1.0f - 1.0f / samples : 0.0f;
}

// Plaits' SwingVCA: one polarity passes four times the gain, the other a
// tenth, then a soft saturation; the bias makes the envelope itself heard.
inline float Swing(float s, float gain) {
  s *= s > 0.0f ? 4.0f : 0.1f;
  s = s / (1.0f + (s < 0.0f ? -s : s));
  return (s + 0.1f) * gain;
}

inline float Clamp(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }

// A frequency in cycles per sample from Hz, scaled by `semitones`.
inline float Hz(float hz, float semitones) {
  return hz / kRate * stmlib::SemitonesToRatio(Clamp(semitones, -120.0f, 120.0f));
}

// The rim shot: two band-passes, a fundamental and a mode 3.66 times
// higher (1,667 / 455 Hz), pinged by a 0.1 ms pulse, clipped as the
// circuit's output transistor clips, with a short noise click (Snap) and a
// high-pass. Tone balances the two modes, Decay sets their Q (a ring of
// about 5 to 45 ms at 455 Hz).
class Rim {
 public:
  void Init() {
    low_.Init();
    high_.Init();
    hp_.Init();
    pulse_ = 0;
    height_ = 0.0f;
    click_ = 0.0f;
  }

  void Render(bool trigger, float accent, float f0, float tone, float decay, float snap,
              uint32_t *rng, float *out, size_t size) {
    const float f1 = Clamp(f0, 1e-6f, 0.2f);
    const float f2 = Clamp(f0 * 3.66f, 1e-6f, 0.45f);
    const float q = 8.0f * stmlib::SemitonesToRatio(decay * 36.0f);
    low_.set_f_q<stmlib::FREQUENCY_FAST>(f1, q);
    high_.set_f_q<stmlib::FREQUENCY_FAST>(f2, q * 0.6f);
    hp_.set_f<stmlib::FREQUENCY_FAST>(Hz(240.0f, 0.0f));
    const float g_low = 1.0f - 0.7f * tone;
    const float g_high = 0.3f + 0.9f * tone;
    if (trigger) {
      pulse_ = 5;                       // 0.1 ms
      height_ = 0.3f + 0.7f * accent;
      click_ = snap * (0.3f + 0.7f * accent);
    }
    const float click_decay = 1.0f - 1.0f / (0.0015f * kRate);   // 1.5 ms
    for (size_t i = 0; i < size; ++i) {
      float x = 0.0f;
      if (pulse_) {
        --pulse_;
        x = height_;
      }
      float body = low_.Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(x) * g_low +
                   high_.Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(x) * g_high;
      body = stmlib::SoftClip(body * 6.0f);
      const float n = Noise(rng) * click_;
      click_ *= click_decay;
      out[i] = 2.0f * hp_.Process<stmlib::FILTER_MODE_HIGH_PASS>(body + n);
    }
    if (click_ < 1e-20f) click_ = 0.0f;   // gone: no denormals while the body rings
  }

 private:
  stmlib::Svf low_;
  stmlib::Svf high_;
  stmlib::OnePole hp_;
  int pulse_;
  float height_;
  float click_;
};

// The hand clap: band-passed white noise under two envelopes in parallel,
// three short sawtooth bursts and a fourth twice as long (the claps), and
// a decaying tail (the "reverb"). Snap tightens the bursts (14 ms apart down
// to 6 ms), Decay sets the tail (25 ms to 0.4 s), Tone the brightness after
// the band-pass.
class Clap {
 public:
  void Init() {
    bp_.Init();
    lp_ = 0.0f;
    burst_ = 4;
    count_ = 0;
    level_ = 0.0f;
    tail_ = 0.0f;
  }

  void Render(bool trigger, float accent, float f0, float tone, float decay, float snap,
              uint32_t *rng, float *out, size_t size) {
    bp_.set_f_q<stmlib::FREQUENCY_FAST>(Clamp(f0, 1e-6f, 0.45f), 1.6f);
    const int spacing = static_cast<int>((0.006f + 0.008f * (1.0f - snap)) * kRate);
    const float tail_decay = DecayFactor(0.1f * stmlib::SemitonesToRatio((decay - 0.5f) * 48.0f));
    const float lp = Clamp(0.08f * stmlib::SemitonesToRatio(tone * 42.0f), 0.0f, 1.0f);
    if (trigger) {
      level_ = 0.3f + 0.7f * accent;
      tail_ = level_;
      burst_ = 0;
      count_ = 0;
    }
    for (size_t i = 0; i < size; ++i) {
      float burst = 0.0f;
      if (burst_ < 4) {
        const int length = burst_ < 3 ? spacing : 2 * spacing;
        burst = level_ * (1.0f - static_cast<float>(count_) / static_cast<float>(length));
        if (++count_ >= length) {
          count_ = 0;
          ++burst_;
        }
      }
      tail_ *= tail_decay;
      const float gain = burst + 0.45f * tail_;
      const float y = bp_.Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(Noise(rng)) * gain;
      ONE_POLE(lp_, y, lp);
      out[i] = lp_ * 3.0f;
    }
  }

 private:
  stmlib::Svf bp_;
  float lp_;
  int burst_;
  int count_;
  float level_;
  float tail_;
};

// The cowbell: two rectangular oscillators at f0 and 1.4815 f0 (540 and
// 800 Hz at the voicing's pitch), duty 0.4798, through a swing VCA on a
// two-stage envelope (a fast stage, its height set by Snap, over a slow one
// set by Decay, 0.075 to 1.2 s), then two band-passes in series (fourth
// order), centred by Tone an octave either side of 880 Hz.
class Cowbell {
 public:
  void Init() {
    phase_[0] = phase_[1] = 0u;
    fast_ = slow_ = 0.0f;
    bp_[0].Init();
    bp_[1].Init();
  }

  void Render(bool trigger, float accent, float f0, float tone, float decay, float snap,
              float *out, size_t size) {
    const uint32_t inc0 = static_cast<uint32_t>(Clamp(f0, 0.0f, 0.45f) * 4294967296.0f);
    const uint32_t inc1 = static_cast<uint32_t>(Clamp(f0 * 1.4815f, 0.0f, 0.45f) * 4294967296.0f);
    const uint32_t duty = 2060725309u;    // 0.4798 x 2^32
    const float fc = Clamp(Hz(880.0f, (tone - 0.5f) * 24.0f), 1e-6f, 0.45f);
    bp_[0].set_f_q<stmlib::FREQUENCY_FAST>(fc, 2.2f);
    bp_[1].set_f_q<stmlib::FREQUENCY_FAST>(fc, 2.2f);
    const float fast_decay = DecayFactor(0.025f);
    const float slow_decay = DecayFactor(0.3f * stmlib::SemitonesToRatio((decay - 0.5f) * 48.0f));
    if (trigger) {
      const float a = 0.3f + 0.7f * accent;
      fast_ = a * (0.2f + 1.6f * snap);
      slow_ = a * 0.5f;
    }
    for (size_t i = 0; i < size; ++i) {
      phase_[0] += inc0;
      phase_[1] += inc1;
      const float s = (phase_[0] < duty ? 0.5f : -0.5f) + (phase_[1] < duty ? 0.5f : -0.5f);
      const float vca = Swing(s, fast_ + slow_);
      fast_ *= fast_decay;
      slow_ *= slow_decay;
      out[i] = 2.7f * bp_[1].Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(
          bp_[0].Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(vca));
    }
    if (fast_ < 1e-20f) fast_ = 0.0f;     // gone: no denormals while the slow stage rings
  }

 private:
  uint32_t phase_[2];
  float fast_;
  float slow_;
  stmlib::Svf bp_[2];
};

// The cymbal: six square oscillators (Plaits' 808 hi-hat bank at 2 f0,
// 414 Hz and up at the voicing's pitch), with clocked noise blended in by
// Snap, split into a low band near 3,440 Hz and a high band near 7,100 Hz
// (Tone moves both an octave either side), each through a swing VCA on its
// own envelope: the low band dies in a third of the high band's time,
// which Decay sets (0.1 to 3.2 s). A high-pass under the low band ends it.
class Cymbal {
 public:
  void Init() {
    for (int i = 0; i < 6; ++i) phase_[i] = 0u;
    low_env_ = high_env_ = 0.0f;
    noise_clock_ = 0.0f;
    noise_sample_ = 0.0f;
    low_.Init();
    high_.Init();
    hp_.Init();
  }

  void Render(bool trigger, float accent, float f0, float tone, float decay, float snap,
              uint32_t *rng, float *out, size_t size) {
    static const float kRatios[6] = { 1.0f, 1.304f, 1.466f, 1.787f, 1.932f, 2.536f };
    uint32_t inc[6];
    for (int i = 0; i < 6; ++i) {
      inc[i] = static_cast<uint32_t>(Clamp(2.0f * f0 * kRatios[i], 0.0f, 0.499f) * 4294967296.0f);
    }
    const float shift = (tone - 0.5f) * 24.0f;
    low_.set_f_q<stmlib::FREQUENCY_FAST>(Clamp(Hz(3440.0f, shift), 1e-6f, 0.45f), 1.8f);
    high_.set_f_q<stmlib::FREQUENCY_FAST>(Clamp(Hz(7100.0f, shift), 1e-6f, 0.45f), 1.8f);
    hp_.set_f_q<stmlib::FREQUENCY_FAST>(Clamp(Hz(1800.0f, shift), 1e-6f, 0.45f), 0.8f);
    const float time = 0.1f * stmlib::SemitonesToRatio(decay * 60.0f);
    const float high_decay = DecayFactor(time);
    const float low_decay = DecayFactor(time * 0.33f);
    const float noisiness = snap * snap;
    const float noise_f = Clamp(f0 * (16.0f + 16.0f * (1.0f - noisiness)), 0.0f, 0.5f);
    if (trigger) {
      low_env_ = high_env_ = 0.3f + 0.7f * accent;
    }
    for (size_t i = 0; i < size; ++i) {
      uint32_t bits = 0;
      for (int k = 0; k < 6; ++k) {
        phase_[k] += inc[k];
        bits += phase_[k] >> 31;
      }
      float metal = 0.33f * static_cast<float>(bits) - 1.0f;
      noise_clock_ += noise_f;
      if (noise_clock_ >= 1.0f) {
        noise_clock_ -= 1.0f;
        noise_sample_ = 0.5f * Noise(rng);
      }
      metal += noisiness * (noise_sample_ - metal);
      const float lo = Swing(low_.Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(metal),
                             low_env_);
      const float hi = Swing(high_.Process<stmlib::FILTER_MODE_BAND_PASS_NORMALIZED>(metal),
                             high_env_);
      low_env_ *= low_decay;
      high_env_ *= high_decay;
      out[i] = 1.8f * hp_.Process<stmlib::FILTER_MODE_HIGH_PASS>(lo + hi);
    }
  }

 private:
  uint32_t phase_[6];
  float low_env_;
  float high_env_;
  float noise_clock_;
  float noise_sample_;
  stmlib::Svf low_;
  stmlib::Svf high_;
  stmlib::Svf hp_;
};

}  // namespace drum_voices
}  // namespace fm1

#endif  // FM1_DRUM_VOICES_H_
