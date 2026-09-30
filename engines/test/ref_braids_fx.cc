// ref_braids_fx.cc -- fm1-ref-braids-fx: the vendored Mutable Instruments
// classes behind Shapes, Plate, Ensemble and Diffuse, driven the way their own
// firmware drives them, with none of our wrappers in the way. The reference
// for tests/test_engines_reference_braids_fx.py; method and results in
// engines/reference-braids-fx.md (docs/11 §8, stage A's exit test).
//
//   fm1-ref-braids-fx braids --shape N --pitch P --timbre T --color C
//                            [--samples N] [--block 24] [--strike-block B]...
//                            [--jitter-draw 0|1] [--seed S] --out raw.wav
//       braids::MacroOscillator as braids/braids.cc's RenderBlock drives it:
//       96 kHz, one 24-sample block at a time, set_shape, set_parameters and
//       set_pitch (1/128 semitone, 60 << 7 = middle C) before every block,
//       Strike() before each block B given (repeatable; 0 by default), sync
//       buffer all zero. Block 0 is struck whatever --strike-block says:
//       DigitalOscillator::Init sets its strike flag, and set_shape strikes
//       when the shape changes from the zeroed one. --block must be even:
//       eleven of Braids' digital renderers write two samples per loop pass
//       and run off the end of an odd-sized buffer. A --samples that is not a
//       multiple of --block ends with a full block rendered into scratch and
//       cut short, so the oscillator only ever sees whole blocks.
//       Writes the raw int16 output as a 16-bit mono WAV, nothing after it
//       (Braids' VCA, bit and rate reduction and signature waveshaper are
//       firmware, not oscillator).
//       The shapes that draw on stmlib::Random share its one global generator,
//       which starts at 0x21 here as in fm1-render; --seed S starts it
//       elsewhere. By default nothing else draws from it, as in fm1-render, so
//       a single Shapes voice sees the same random numbers as this oscillator.
//       Braids' firmware does not: RenderBlock's VCO jitter source draws one
//       Random::GetWord() per block, before the oscillator renders, whatever
//       the drift setting (braids.cc, vco_jitter_source.h). --jitter-draw 1
//       adds that draw, for statistical comparisons against the firmware.
//
//   fm1-ref-braids-fx fx --effect plate|ensemble|diffuse
//                        [--input impulse|noise|sine|silence | --input-file F]
//                        [--seconds S] [--rate HZ] [caller settings] [overrides]
//                        [--compensate HOST] [--right-delay N [--right-width W]]
//                        --out fx.wav
//       One upstream effect class on a mono input fed to both channels (or a
//       file's two), set up as its upstream caller sets it up:
//         plate     rings::Reverb as rings/dsp/part.cc (string-and-reverb
//                   model): --damping D --brightness B give time 0.35 + 0.63 D,
//                   lp 0.3 + 0.6 B, amount 0.1 + 0.5 D, diffusion 0.625,
//                   input gain 0.2. Blocks of 24 (Rings' kMaxBlockSize).
//         ensemble  plaits::Ensemble as the string machine
//                   (engine2/string_machine_engine.cc): --timbre T gives
//                   amount |T - 0.5| * 2 and depth 0.35 + 0.65 T. Blocks of 12.
//         diffuse   plaits::Diffuser as the particle engine
//                   (engine/particle_engine.cc): --morph M gives diffusion
//                   (2|M - 0.5|)^2 below M = 0.5, else 0; amount 0.8 d^2,
//                   rt 0.25 + 0.5 d. Blocks of 12.
//       --amount, --time, --lp, --diffusion, --input-gain (plate), --depth
//       (ensemble) and --rt (diffuse) override a computed setting.
//       --compensate HOST applies engines/mi-fx.md's rate rule to the loop
//       settings: g^(native/HOST) for plate time and diffuse rt,
//       1 - (1 - k)^(native/HOST) for plate lp. --right-delay N replaces the
//       right channel x with x + W (late - x), late being x N samples later
//       and W --right-width (default 1): the line Ensemble's Width builds.
//       Plate sums the two channels; diffuse runs on the left one alone, as
//       the particle engine's mono signal.
//       The classes have no sample rate; --rate (default: the class's native
//       rate, 48,000 Hz for Rings, 47,872.34 Hz for Plaits) sets only the
//       sample count, the sine input's frequency and the WAV header. The inputs
//       are fm1-render's own, sample for sample; --input-file F.wav reads a
//       mono or stereo 32-bit float WAV instead (all of its frames; --seconds
//       is ignored), for the stereo signal of an effect earlier in a chain.
//       Writes a stereo 32-bit float WAV.
//
// Both modes print one line of JSON describing what ran. Desktop only; not
// part of the firmware. MIT licence.

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "braids/macro_oscillator.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/fx/diffuser.h"
#include "plaits/dsp/fx/ensemble.h"
#include "rings/dsp/fx/reverb.h"
#include "stmlib/utils/random.h"

namespace {

// ---------------------------------------------------------------------------
// WAV output
// ---------------------------------------------------------------------------

void Put32(FILE *f, uint32_t v) {
  uint8_t b[4] = { uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24) };
  fwrite(b, 1, 4, f);
}

void Put16(FILE *f, uint16_t v) {
  uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) };
  fwrite(b, 1, 2, f);
}

void Header(FILE *f, uint16_t tag, uint16_t channels, uint32_t rate, uint16_t bits,
            uint32_t data_bytes) {
  const uint16_t align = static_cast<uint16_t>(channels * bits / 8);
  fwrite("RIFF", 1, 4, f); Put32(f, 36 + data_bytes); fwrite("WAVE", 1, 4, f);
  fwrite("fmt ", 1, 4, f); Put32(f, 16); Put16(f, tag); Put16(f, channels);
  Put32(f, rate); Put32(f, rate * align); Put16(f, align); Put16(f, bits);
  fwrite("data", 1, 4, f); Put32(f, data_bytes);
}

bool WritePcm16(const char *path, const std::vector<int16_t> &x, uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  Header(f, 1, 1, rate, 16, static_cast<uint32_t>(x.size() * 2));
  for (size_t i = 0; i < x.size(); ++i) Put16(f, static_cast<uint16_t>(x[i]));
  return fclose(f) == 0;
}

bool WriteFloatStereo(const char *path, const std::vector<float> &l,
                      const std::vector<float> &r, uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  Header(f, 3, 2, rate, 32, static_cast<uint32_t>(l.size() * 8));
  for (size_t i = 0; i < l.size(); ++i) {
    uint32_t a, b;
    memcpy(&a, &l[i], 4);
    memcpy(&b, &r[i], 4);
    Put32(f, a);
    Put32(f, b);
  }
  return fclose(f) == 0;
}

void Usage() {
  fprintf(stderr,
      "usage: fm1-ref-braids-fx braids --shape N --pitch P --timbre T --color C\n"
      "                         [--samples N] [--block EVEN] [--strike-block B]...\n"
      "                         [--jitter-draw 0|1] [--seed S] --out F.wav\n"
      "       fm1-ref-braids-fx fx --effect plate|ensemble|diffuse\n"
      "                         [--input impulse|noise|sine|silence | --input-file F.wav]\n"
      "                         [--seconds S] [--rate HZ]\n"
      "                         [--damping D --brightness B | --timbre T | --morph M]\n"
      "                         [--amount A] [--time G] [--lp K] [--diffusion K]\n"
      "                         [--input-gain G] [--depth D] [--rt G] [--compensate HOST]\n"
      "                         [--right-delay N [--right-width W]]\n"
      "                         --out F.wav\n");
}

uint32_t Get32(const uint8_t *p) {
  return p[0] | p[1] << 8 | p[2] << 16 | static_cast<uint32_t>(p[3]) << 24;
}

float GetFloat(const uint8_t *p) {
  const uint32_t bits = Get32(p);
  float x;
  memcpy(&x, &bits, 4);
  return x;
}

// A mono or stereo 32-bit float WAV as two channels (a mono file's twice).
bool ReadFloatWav(const char *path, std::vector<float> *l, std::vector<float> *r) {
  FILE *f = fopen(path, "rb");
  if (!f) return false;
  std::vector<uint8_t> d;
  uint8_t buf[4096];
  size_t got;
  while ((got = fread(buf, 1, sizeof(buf), f)) > 0) d.insert(d.end(), buf, buf + got);
  fclose(f);
  if (d.size() < 12 || memcmp(&d[0], "RIFF", 4) != 0 || memcmp(&d[8], "WAVE", 4) != 0) {
    return false;
  }
  uint16_t tag = 0, channels = 0, bits = 0;
  for (size_t pos = 12; pos + 8 <= d.size();) {
    const uint32_t size = Get32(&d[pos + 4]);
    const size_t body = pos + 8;
    if (size > d.size() - body) return false;
    if (memcmp(&d[pos], "fmt ", 4) == 0 && size >= 16) {
      tag = static_cast<uint16_t>(d[body] | d[body + 1] << 8);
      channels = static_cast<uint16_t>(d[body + 2] | d[body + 3] << 8);
      bits = static_cast<uint16_t>(d[body + 14] | d[body + 15] << 8);
    } else if (memcmp(&d[pos], "data", 4) == 0) {
      if (tag != 3 || bits != 32 || channels < 1 || channels > 2) return false;
      const size_t frames = size / (4u * channels);
      l->resize(frames);
      r->resize(frames);
      for (size_t i = 0; i < frames; ++i) {
        const uint8_t *frame = &d[body + 4u * channels * i];
        (*l)[i] = GetFloat(frame);
        (*r)[i] = GetFloat(frame + 4u * (channels - 1u));
      }
      return true;
    }
    pos = body + size + (size & 1);
  }
  return false;
}

// ---------------------------------------------------------------------------
// braids
// ---------------------------------------------------------------------------

// Static storage, as Braids' global `MacroOscillator osc`: zero before Init,
// which matters because Init leaves shape_ and the digital oscillator's
// previous shape as they were.
braids::MacroOscillator g_osc;

const size_t kBraidsMaxBlock = 24;   // braids.cc kBlockSize; the oscillator's
                                     // temp buffers hold 24 samples
const uint32_t kBraidsRate = 96000;

int RunBraids(int argc, char **argv) {
  long shape = -1, pitch = -1, timbre = -1, color = -1;
  long samples = 9600, block = 24, jitter_draw = 0;
  std::vector<long> strike_blocks;
  long long seed = -1;
  bool bad_strike = false;
  const char *out = NULL;
  for (int i = 2; i + 1 < argc; i += 2) {
    const std::string a = argv[i];
    const char *v = argv[i + 1];
    if (a == "--shape") shape = strtol(v, NULL, 0);
    else if (a == "--pitch") pitch = strtol(v, NULL, 0);
    else if (a == "--timbre") timbre = strtol(v, NULL, 0);
    else if (a == "--color") color = strtol(v, NULL, 0);
    else if (a == "--samples") samples = strtol(v, NULL, 0);
    else if (a == "--block") block = strtol(v, NULL, 0);
    else if (a == "--strike-block") {
      strike_blocks.push_back(strtol(v, NULL, 0));
      if (strike_blocks.back() < 0) bad_strike = true;
    }
    else if (a == "--jitter-draw") jitter_draw = strtol(v, NULL, 0);
    else if (a == "--seed") seed = strtoll(v, NULL, 0);
    else if (a == "--out") out = v;
    else { Usage(); return 2; }
  }
  if ((argc - 2) % 2 != 0 || !out || shape < 0 ||
      shape > braids::MACRO_OSC_SHAPE_LAST_ACCESSIBLE_FROM_META || pitch < 0 ||
      pitch > 32767 || timbre < 0 || timbre > 32767 || color < 0 || color > 32767 ||
      samples <= 0 || block <= 0 || block > static_cast<long>(kBraidsMaxBlock) ||
      (block & 1) || bad_strike || (jitter_draw != 0 && jitter_draw != 1)) {
    Usage();
    return 2;
  }
  if (strike_blocks.empty()) strike_blocks.push_back(0);   // a trigger at the start

  std::vector<int16_t> pcm(static_cast<size_t>(samples));
  int16_t scratch[kBraidsMaxBlock];
  uint8_t sync[kBraidsMaxBlock] = { 0 };
  g_osc.Init();
  if (seed >= 0) stmlib::Random::Seed(static_cast<uint32_t>(seed));
  const uint32_t random_start = stmlib::Random::state();
  size_t pos = 0;
  for (long b = 0; pos < pcm.size(); ++b) {
    const size_t n = pcm.size() - pos < static_cast<size_t>(block)
        ? pcm.size() - pos : static_cast<size_t>(block);
    g_osc.set_shape(static_cast<braids::MacroOscillatorShape>(shape));
    g_osc.set_parameters(static_cast<int16_t>(timbre), static_cast<int16_t>(color));
    if (jitter_draw) stmlib::Random::GetWord();       // braids.cc: jitter_source.Render
    g_osc.set_pitch(static_cast<int16_t>(pitch));
    if (std::find(strike_blocks.begin(), strike_blocks.end(), b) != strike_blocks.end()) {
      g_osc.Strike();
    }
    // Always a whole block: the last one goes through scratch and is cut.
    g_osc.Render(sync, scratch, static_cast<size_t>(block));
    std::copy(scratch, scratch + n, &pcm[pos]);
    pos += n;
  }

  int peak = 0;
  double sum2 = 0.0;
  for (size_t i = 0; i < pcm.size(); ++i) {
    const int a = pcm[i] < 0 ? -pcm[i] : pcm[i];
    if (a > peak) peak = a;
    sum2 += static_cast<double>(pcm[i]) * pcm[i];
  }
  if (!WritePcm16(out, pcm, kBraidsRate)) {
    fprintf(stderr, "cannot write %s\n", out);
    return 1;
  }
  printf("{\"mode\":\"braids\",\"shape\":%ld,\"pitch\":%ld,\"timbre\":%ld,\"color\":%ld,"
         "\"rate\":%u,\"block\":%ld,\"strike_blocks\":[",
         shape, pitch, timbre, color, kBraidsRate, block);
  for (size_t i = 0; i < strike_blocks.size(); ++i) {
    printf("%s%ld", i ? "," : "", strike_blocks[i]);
  }
  printf("],\"jitter_draw\":%ld,\"samples\":%ld,\"peak\":%d,\"rms\":%.3f,"
         "\"random_start\":%u,\"random_end\":%u}\n",
         jitter_draw, samples, peak, sqrt(sum2 / pcm.size()), random_start,
         stmlib::Random::state());
  return 0;
}

// ---------------------------------------------------------------------------
// fx
// ---------------------------------------------------------------------------

// Rings' kSampleRate (rings/dsp/dsp.h, not vendored) and its block size.
const float kRingsRate = 48000.0f;
const size_t kRingsBlock = 24;

// Static storage, as on the modules: Rings' reverb_buffer and Part are
// globals, Plaits' effect memory comes from a static arena.
rings::Reverb g_reverb;
uint16_t g_reverb_buffer[32768];
plaits::Ensemble g_ensemble;
plaits::Ensemble::E::T g_ensemble_buffer[1024];
plaits::Diffuser g_diffuser;
uint16_t g_diffuser_buffer[8192];

struct Setting {                     // a computed value an option may override
  float value;
  bool set;
  Setting() : value(0.0f), set(false) { }
  float Or(float computed) const { return set ? value : computed; }
};

int RunFx(int argc, char **argv) {
  std::string effect, input = "impulse";
  double seconds = 1.0;
  float rate = 0.0f;
  float compensate = 0.0f;
  long right_delay = 0;
  float right_width = 1.0f;
  const char *out = NULL, *input_file = NULL;
  float damping = 0.5f, brightness = 0.5f, timbre = 1.0f, morph = 0.0f;
  Setting amount, time, lp, diffusion, input_gain, depth, rt;
  for (int i = 2; i + 1 < argc; i += 2) {
    const std::string a = argv[i];
    const char *v = argv[i + 1];
    const float f = static_cast<float>(atof(v));
    if (a == "--effect") effect = v;
    else if (a == "--input") input = v;
    else if (a == "--seconds") seconds = atof(v);
    else if (a == "--rate") rate = f;
    else if (a == "--compensate") compensate = f;
    else if (a == "--right-delay") right_delay = strtol(v, NULL, 0);
    else if (a == "--right-width") right_width = f;
    else if (a == "--input-file") input_file = v;
    else if (a == "--out") out = v;
    else if (a == "--damping") damping = f;
    else if (a == "--brightness") brightness = f;
    else if (a == "--timbre") timbre = f;
    else if (a == "--morph") morph = f;
    else if (a == "--amount") { amount.value = f; amount.set = true; }
    else if (a == "--time") { time.value = f; time.set = true; }
    else if (a == "--lp") { lp.value = f; lp.set = true; }
    else if (a == "--diffusion") { diffusion.value = f; diffusion.set = true; }
    else if (a == "--input-gain") { input_gain.value = f; input_gain.set = true; }
    else if (a == "--depth") { depth.value = f; depth.set = true; }
    else if (a == "--rt") { rt.value = f; rt.set = true; }
    else { Usage(); return 2; }
  }
  const bool is_plate = effect == "plate";
  const bool is_ensemble = effect == "ensemble";
  const bool is_diffuse = effect == "diffuse";
  if ((argc - 2) % 2 != 0 || !out || !(is_plate || is_ensemble || is_diffuse) ||
      (input != "impulse" && input != "noise" && input != "sine" && input != "silence") ||
      !(seconds > 0.0) || rate < 0.0f || compensate < 0.0f || right_delay < 0 ||
      !(right_width >= 0.0f && right_width <= 1.0f)) {
    Usage();
    return 2;
  }
  std::vector<float> file_l, file_r;
  if (input_file && (!ReadFloatWav(input_file, &file_l, &file_r) || file_l.empty())) {
    fprintf(stderr, "cannot read %s as a 32-bit float WAV\n", input_file);
    return 2;
  }
  const float native = is_plate ? kRingsRate : plaits::kCorrectedSampleRate;
  if (rate == 0.0f) rate = native;
  const float native_over_host = compensate > 0.0f ? native / compensate : 1.0f;

  // The upstream callers' settings.
  float s_amount = 0.0f, s_time = 0.0f, s_lp = 0.0f, s_diffusion = 0.0f;
  float s_gain = 0.0f, s_depth = 0.0f, s_rt = 0.0f;
  if (is_plate) {                                     // rings/dsp/part.cc
    s_amount = amount.Or(0.1f + damping * 0.5f);
    s_diffusion = diffusion.Or(0.625f);
    s_time = time.Or(0.35f + 0.63f * damping);
    s_gain = input_gain.Or(0.2f);
    s_lp = lp.Or(0.3f + brightness * 0.6f);
    if (compensate > 0.0f) {
      s_time = powf(s_time, native_over_host);
      s_lp = 1.0f - powf(1.0f - s_lp, native_over_host);
    }
    g_reverb.Init(g_reverb_buffer);
    g_reverb.set_amount(s_amount);
    g_reverb.set_diffusion(s_diffusion);
    g_reverb.set_time(s_time);
    g_reverb.set_input_gain(s_gain);
    g_reverb.set_lp(s_lp);
  } else if (is_ensemble) {                           // string_machine_engine.cc
    s_amount = amount.Or(fabsf(timbre - 0.5f) * 2.0f);
    s_depth = depth.Or(0.35f + 0.65f * timbre);
    g_ensemble.Init(g_ensemble_buffer);
    g_ensemble.Reset();
    g_ensemble.set_amount(s_amount);
    g_ensemble.set_depth(s_depth);
  } else {                                            // particle_engine.cc
    const float raw_diffusion_sqrt = 2.0f * fabsf(morph - 0.5f);
    const float raw_diffusion = raw_diffusion_sqrt * raw_diffusion_sqrt;
    const float d = morph < 0.5f ? raw_diffusion : 0.0f;
    s_diffusion = d;
    s_amount = amount.Or(0.8f * d * d);
    s_rt = rt.Or(0.5f * d + 0.25f);
    if (compensate > 0.0f) s_rt = powf(s_rt, native_over_host);
    g_diffuser.Init(g_diffuser_buffer);
    g_diffuser.Reset();
  }

  // fm1-render's inputs, sample for sample (engines/host/render.cc).
  const uint32_t total = input_file ? static_cast<uint32_t>(file_l.size())
                                    : static_cast<uint32_t>(seconds * rate);
  std::vector<float> left(total), right(total);
  uint32_t noise = 0x12345678u;
  double sine_phase = 0.0;
  for (uint32_t i = 0; i < total; ++i) {
    float x = 0.0f;
    if (input_file) {
      left[i] = file_l[i];
      right[i] = file_r[i];
      continue;
    } else if (input == "impulse") {
      x = i == 0 ? 1.0f : 0.0f;
    } else if (input == "noise") {
      noise = noise * 1664525u + 1013904223u;
      x = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
    } else if (input == "sine") {
      x = 0.5f * static_cast<float>(sin(sine_phase));
      sine_phase += 2.0 * 3.141592653589793 * 440.0 / rate;
    }
    left[i] = right[i] = x;
  }
  if (right_delay > 0) {                // Ensemble's Width line, on the right
    for (uint32_t i = total; i-- > 0;) {
      const float x = right[i];
      const float late = i >= static_cast<uint32_t>(right_delay) ? right[i - right_delay] : 0.0f;
      right[i] = x + right_width * (late - x);
    }
  }

  const size_t block = is_plate ? kRingsBlock : plaits::kBlockSize;
  for (size_t pos = 0; pos < total; pos += block) {
    const size_t n = total - pos < block ? total - pos : block;
    if (is_plate) {
      g_reverb.Process(&left[pos], &right[pos], n);
    } else if (is_ensemble) {
      g_ensemble.Process(&left[pos], &right[pos], n);
    } else {
      g_diffuser.Process(s_amount, s_rt, &left[pos], n);   // mono in place
      std::copy(&left[pos], &left[pos] + n, &right[pos]);
    }
  }

  float peak = 0.0f;
  double sum2 = 0.0;
  uint32_t nonfinite = 0;
  for (uint32_t i = 0; i < total; ++i) {
    const float s[2] = { left[i], right[i] };
    for (int c = 0; c < 2; ++c) {
      if (!std::isfinite(s[c])) { ++nonfinite; continue; }
      if (fabsf(s[c]) > peak) peak = fabsf(s[c]);
      sum2 += static_cast<double>(s[c]) * s[c];
    }
  }
  if (!WriteFloatStereo(out, left, right, static_cast<uint32_t>(lrintf(rate)))) {
    fprintf(stderr, "cannot write %s\n", out);
    return 1;
  }
  printf("{\"mode\":\"fx\",\"effect\":\"%s\",\"class\":\"%s\",\"input\":\"%s\","
         "\"native_rate\":%.9g,\"rate\":%.9g,\"compensate\":%.9g,\"native_over_host\":%.9g,"
         "\"block\":%zu,\"frames\":%u,\"right_delay\":%ld,\"right_width\":%.9g,"
         "\"amount\":%.9g,",
         effect.c_str(),
         is_plate ? "rings::Reverb" : is_ensemble ? "plaits::Ensemble" : "plaits::Diffuser",
         input_file ? "file" : input.c_str(), native, rate, compensate, native_over_host, block,
         total, right_delay, right_width, s_amount);
  if (is_plate) {
    printf("\"time\":%.9g,\"lp\":%.9g,\"diffusion\":%.9g,\"input_gain\":%.9g,",
           s_time, s_lp, s_diffusion, s_gain);
  } else if (is_ensemble) {
    printf("\"depth\":%.9g,", s_depth);
  } else {
    printf("\"diffusion\":%.9g,\"rt\":%.9g,", s_diffusion, s_rt);
  }
  printf("\"peak\":%.6f,\"rms\":%.6f,\"nonfinite\":%u}\n", peak,
         total ? sqrt(sum2 / (2.0 * total)) : 0.0, nonfinite);
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc >= 2 && strcmp(argv[1], "braids") == 0) return RunBraids(argc, argv);
  if (argc >= 2 && strcmp(argv[1], "fx") == 0) return RunFx(argc, argv);
  Usage();
  return 2;
}
