// ref_room.cc -- fm1-ref-room: the vendored Mutable Instruments classes
// behind Room, clouds::Diffuser and clouds::Reverb, driven the way Clouds'
// granular processor drives them (clouds/dsp/granular_processor.cc,
// GranularProcessor::Process: the diffuser, then the reverb, in place, in
// the codec's 32-frame blocks), with none of Room's wrapper in the way. The
// reference for tests/test_engines_reference_room.py; method and results in
// engines/README.md ("Room").
//
//   fm1-ref-room [--input impulse|noise|sine|silence | --input-file F.wav]
//                [--seconds S] [--rate HZ] [--reverb R --feedback F]
//                [--blur B] [--amount A] [--time G] [--lp K] [--diffusion K]
//                [--input-gain G] [--compensate HOST] --out F.wav
//
//   Clouds' settings, from its reverb and feedback knobs with freeze off:
//   reverb_amount = 0.95 R, amount 0.54 reverb_amount, time 0.35 + 0.63
//   reverb_amount, lp 0.6 + 0.37 F, diffusion 0.7, input gain 0.2. --blur
//   is the diffuser's amount (Clouds sets it from Texture or Density; 0 by
//   default). --amount, --time, --lp, --diffusion and --input-gain override
//   a computed setting. --compensate HOST applies Room's rate rule to the
//   loop settings with Room's own functions (src/fx_room_math.h): time^r
//   and 1 - (1 - lp)^r, r = 32,000 / HOST, nothing at r = 1.
//
//   The classes have no sample rate: --rate (default 32,000 Hz, Clouds'
//   own) sets only the sample count, the sine input's frequency and the WAV
//   header. The inputs are fm1-render's own, sample for sample, on both
//   channels; --input-file reads a mono or stereo 32-bit float WAV instead
//   (all of its frames; --seconds is ignored). Writes a stereo 32-bit float
//   WAV and prints one line of JSON describing what ran.
//
// Contraction is off for this file as for src/fx_room.cc, so the classes'
// arithmetic rounds here exactly as it does in Room: the reverb stores
// 12-bit words, and one fused multiply-add on one side would sooner or later
// flip a truncation. Desktop only; not part of the firmware. MIT licence.

#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "clouds/dsp/frame.h"
#include "clouds/dsp/fx/diffuser.h"
#include "clouds/dsp/fx/reverb.h"

#include "../src/fx_room_math.h"

namespace {

const float kCloudsRate = 32000.0f;
const size_t kCloudsBlock = 32;               // clouds.cc: codec.Start(32, ...)

// Static storage, as on the module: the processor is a global and its
// buffers come from a static arena, so every state starts at zero.
clouds::Diffuser g_diffuser;
clouds::Reverb g_reverb;
float g_diffuser_buffer[2048];
uint16_t g_reverb_buffer[16384];

void Put32(FILE *f, uint32_t v) {
  uint8_t b[4] = { uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24) };
  fwrite(b, 1, 4, f);
}

void Put16(FILE *f, uint16_t v) {
  uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) };
  fwrite(b, 1, 2, f);
}

bool WriteFloatStereo(const char *path, const std::vector<clouds::FloatFrame> &x,
                      uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  const uint32_t data = static_cast<uint32_t>(x.size() * 8);
  fwrite("RIFF", 1, 4, f); Put32(f, 36 + data); fwrite("WAVE", 1, 4, f);
  fwrite("fmt ", 1, 4, f); Put32(f, 16); Put16(f, 3); Put16(f, 2);
  Put32(f, rate); Put32(f, rate * 8); Put16(f, 8); Put16(f, 32);
  fwrite("data", 1, 4, f); Put32(f, data);
  for (size_t i = 0; i < x.size(); ++i) {
    uint32_t a, b;
    memcpy(&a, &x[i].l, 4);
    memcpy(&b, &x[i].r, 4);
    Put32(f, a);
    Put32(f, b);
  }
  return fclose(f) == 0;
}

uint32_t Get32(const uint8_t *p) {
  return p[0] | p[1] << 8 | p[2] << 16 | static_cast<uint32_t>(p[3]) << 24;
}

// A mono or stereo 32-bit float WAV as frames (a mono file's twice).
bool ReadFloatWav(const char *path, std::vector<clouds::FloatFrame> *out) {
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
      out->resize(frames);
      for (size_t i = 0; i < frames; ++i) {
        const uint8_t *frame = &d[body + 4u * channels * i];
        uint32_t a = Get32(frame), b = Get32(frame + 4u * (channels - 1u));
        memcpy(&(*out)[i].l, &a, 4);
        memcpy(&(*out)[i].r, &b, 4);
      }
      return true;
    }
    pos = body + size + (size & 1);
  }
  return false;
}

void Usage() {
  fprintf(stderr,
      "usage: fm1-ref-room [--input impulse|noise|sine|silence | --input-file F.wav]\n"
      "                    [--seconds S] [--rate HZ] [--reverb R] [--feedback F]\n"
      "                    [--blur B] [--amount A] [--time G] [--lp K] [--diffusion K]\n"
      "                    [--input-gain G] [--compensate HOST] --out F.wav\n");
}

struct Setting {                     // a computed value an option may override
  float value;
  bool set;
  Setting() : value(0.0f), set(false) { }
  float Or(float computed) const { return set ? value : computed; }
};

}  // namespace

int main(int argc, char **argv) {
  std::string input = "impulse";
  double seconds = 1.0;
  float rate = kCloudsRate, compensate = 0.0f;
  float reverb = 0.5f, feedback = 0.0f, blur = 0.0f;
  const char *out = NULL, *input_file = NULL;
  Setting amount, time, lp, diffusion, input_gain;
  for (int i = 1; i + 1 < argc; i += 2) {
    const std::string a = argv[i];
    const char *v = argv[i + 1];
    const float f = static_cast<float>(atof(v));
    if (a == "--input") input = v;
    else if (a == "--input-file") input_file = v;
    else if (a == "--seconds") seconds = atof(v);
    else if (a == "--rate") rate = f;
    else if (a == "--compensate") compensate = f;
    else if (a == "--reverb") reverb = f;
    else if (a == "--feedback") feedback = f;
    else if (a == "--blur") blur = f;
    else if (a == "--amount") { amount.value = f; amount.set = true; }
    else if (a == "--time") { time.value = f; time.set = true; }
    else if (a == "--lp") { lp.value = f; lp.set = true; }
    else if (a == "--diffusion") { diffusion.value = f; diffusion.set = true; }
    else if (a == "--input-gain") { input_gain.value = f; input_gain.set = true; }
    else if (a == "--out") out = v;
    else { Usage(); return 2; }
  }
  if ((argc - 1) % 2 != 0 || !out || !(seconds > 0.0) || !(rate > 0.0f) ||
      compensate < 0.0f ||
      (input != "impulse" && input != "noise" && input != "sine" && input != "silence")) {
    Usage();
    return 2;
  }
  std::vector<clouds::FloatFrame> x;
  if (input_file && (!ReadFloatWav(input_file, &x) || x.empty())) {
    fprintf(stderr, "cannot read %s as a 32-bit float WAV\n", input_file);
    return 2;
  }

  // GranularProcessor::Process, freeze off (freeze_lp_ 0).
  float reverb_amount = reverb * 0.95f;
  if (reverb_amount < 0.0f) reverb_amount = 0.0f;
  if (reverb_amount > 1.0f) reverb_amount = 1.0f;
  const float s_amount = amount.Or(reverb_amount * 0.54f);
  const float s_diffusion = diffusion.Or(0.7f);
  float s_time = time.Or(0.35f + 0.63f * reverb_amount);
  const float s_gain = input_gain.Or(0.2f);
  float s_lp = lp.Or(0.6f + 0.37f * feedback);
  const float r = compensate > 0.0f ? kCloudsRate / compensate : 1.0f;
  if (compensate > 0.0f && r != 1.0f) {               // Room's rate rule
    s_time = RoomPow(s_time, r);
    s_lp = 1.0f - RoomPow(1.0f - s_lp, r);
  }

  g_diffuser.Init(g_diffuser_buffer);
  g_diffuser.set_amount(blur);
  g_reverb.Init(g_reverb_buffer);
  g_reverb.set_amount(s_amount);
  g_reverb.set_diffusion(s_diffusion);
  g_reverb.set_time(s_time);
  g_reverb.set_input_gain(s_gain);
  g_reverb.set_lp(s_lp);

  // fm1-render's inputs, sample for sample (engines/host/render.cc).
  if (!input_file) {
    const uint32_t total = static_cast<uint32_t>(seconds * rate);
    x.resize(total);
    uint32_t noise = 0x12345678u;
    double sine_phase = 0.0;
    for (uint32_t i = 0; i < total; ++i) {
      float v = 0.0f;
      if (input == "impulse") {
        v = i == 0 ? 1.0f : 0.0f;
      } else if (input == "noise") {
        noise = noise * 1664525u + 1013904223u;
        v = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
      } else if (input == "sine") {
        v = 0.5f * static_cast<float>(sin(sine_phase));
        sine_phase += 2.0 * 3.141592653589793 * 440.0 / rate;
      }
      x[i].l = x[i].r = v;
    }
  }

  for (size_t pos = 0; pos < x.size(); pos += kCloudsBlock) {
    const size_t n = x.size() - pos < kCloudsBlock ? x.size() - pos : kCloudsBlock;
    g_diffuser.Process(&x[pos], n);
    g_reverb.Process(&x[pos], n);
  }

  float peak = 0.0f;
  double sum2 = 0.0;
  uint32_t nonfinite = 0;
  for (size_t i = 0; i < x.size(); ++i) {
    const float s[2] = { x[i].l, x[i].r };
    for (int c = 0; c < 2; ++c) {
      if (!std::isfinite(s[c])) { ++nonfinite; continue; }
      if (fabsf(s[c]) > peak) peak = fabsf(s[c]);
      sum2 += static_cast<double>(s[c]) * s[c];
    }
  }
  if (!WriteFloatStereo(out, x, static_cast<uint32_t>(lrintf(rate)))) {
    fprintf(stderr, "cannot write %s\n", out);
    return 1;
  }
  printf("{\"classes\":\"clouds::Diffuser, clouds::Reverb\",\"input\":\"%s\","
         "\"rate\":%.9g,\"compensate\":%.9g,\"native_over_host\":%.9g,\"block\":%zu,"
         "\"frames\":%zu,\"blur\":%.9g,\"amount\":%.9g,\"time\":%.9g,\"lp\":%.9g,"
         "\"diffusion\":%.9g,\"input_gain\":%.9g,\"peak\":%.6f,\"rms\":%.6f,"
         "\"nonfinite\":%u}\n",
         input_file ? "file" : input.c_str(), rate, compensate, r, kCloudsBlock, x.size(), blur,
         s_amount, s_time, s_lp, s_diffusion, s_gain, peak,
         x.empty() ? 0.0 : sqrt(sum2 / (2.0 * x.size())), nonfinite);
  return 0;
}
