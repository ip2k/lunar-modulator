// ref_plaits.cc -- fm1-ref-plaits: the upstream reference for Macro, Macro
// Heavy and Six-Op FM (engines/reference-plaits.md).
//
// Render mode runs the vendored, unmodified plaits::Voice (plaits/dsp/voice.cc)
// the way the module's firmware drives it: one Voice with all 24 engines
// initialised in one 16 KB shared buffer, Voice::Render called with a Patch and
// Modulations every kBlockSize (12) frames at 47,872.34 Hz, and the frames it
// fills -- the module's DAC words -- written as a 16-bit WAV, OUT left and AUX
// right. One note: TRIG and LEVEL patched (as the fm1 wrappers drive their
// engines), TRIG only ("ping"), or free-running.
//
//   fm1-ref-plaits --engine 8 --note 69 --harmonics 0.2 --timbre 0.5 --morph 0.8
//                  --seconds 0.6 --gate 0.3 --out ref.wav
//
// Voice delays TRIG by one millisecond (four blocks) before the engines see
// it, and LEVEL not at all. By default the reference leads the TRIG input by
// those four blocks so the engine sees the edge at t = 0, where the wrappers
// put it, and selects the engine at t = 0 as well (a pre-roll engine renders
// the lead-in, silent), so the engine's Reset() coincides with the wrappers'
// note-on reset. --literal drops both: the engine is selected from the first
// block and TRIG and LEVEL arrive together, as on the module.
//
// --delay-blocks N starts the note N blocks (12 samples each) into the render,
// with the engine still selected at t = 0, so upstream can be compared with
// itself. For Six-Op, 1 moves the note to the other half of SixOpEngine's
// staggered 24-sample chunks, which mostly leaves the onset where it was, and
// 2 moves it a whole chunk (reference-plaits.md, "Six-Op, across all 96
// patches").
//
// stmlib::Random is one global generator (seed 0x21). --seed N sets its state
// after Voice::Init, so the engines with internal randomness can be rendered
// as independent realisations and compared statistically.
//
// --host-rate HZ renders what the wrappers deliver to a host at that rate:
// they run Plaits at 47,872.34 Hz and resample the voice mix with
// fm1_resampler.h (mi_macro.cc). The Voice renders the same 12-sample blocks
// as above, on demand; the note-on (--at S, default 0) and the note-off
// (--gate S) land on the first block rendered after fm1-render would apply
// them, at the start of the first host block (--host-frames N, default 64)
// at or after their time, which a dry run of the resampler's pulls finds.
// Blocks before the note's are silence (the wrapper has no voice yet); the
// engine is selected at the note, TRIG leading as above. The DAC words,
// times --host-gain G (0.25 by default: Volume 1, one voice) over 32,768,
// are resampled to HZ and written as fm1-render writes its output: OUT
// left, AUX right, x 32,767, rounded, at fm1's scale, so that the full-scale
// words do not clip on the way and fm1 compares at --gain 1. A host above
// 47,872.34 Hz or below a quarter of it is refused, as the wrappers refuse
// it. --host-rate 47872.34 gives the words x G, unresampled.
//
// Compare mode reads a reference WAV and an fm1-render WAV (any 16-bit PCM
// WAV; a 47,872 Hz header means 47,872.34) and prints, as JSON, the measures
// tests/test_engines_reference_plaits.py asserts:
// - waveform, at equal rates: best-lag normalised cross-correlation, the
//   least-squares gain, and the error at the expected gain in dBFS;
// - level against the expected gain, and the largest and mean distance
//   between the two RMS envelopes, in dB;
// - timing after an event (--t0): 20 dB decay times, the time stretch that
//   best maps one envelope onto the other, and the ratio of decay rates;
// - spectrum: the pitch shift in cents (log-frequency correlation of the
//   magnitude spectra), the shift of the smoothed spectral envelope, the
//   spectral centroid shift, and a 1/6-octave log-spectral distance.
//
//   fm1-ref-plaits --compare ref.wav fm1.wav [--gain 0.25] [--from S] [--to S] ...
//
// MIT licence (this file). Plaits is Emilie Gillet's (MIT, vendored in
// third_party/mutable); nothing here changes it.

#include <algorithm>
#include <climits>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "fm1_resampler.h"
#include "stmlib/dsp/hysteresis_quantizer.h"
#include "stmlib/utils/buffer_allocator.h"
#include "stmlib/utils/random.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/fm/patch.h"
#include "plaits/dsp/voice.h"
#include "plaits/resources.h"

namespace {

// ---------------------------------------------------------------------------
// Render mode: plaits::Voice as the module drives it.

// The module's shared engine buffer: Voice::Init hands the same 16 KB to every
// engine in turn (allocator->Free() before each Init). The particle engine's
// diffuser takes all of it (plaits-heavy.md), so it can be no smaller.
alignas(16) char shared_buffer[16384];
// Static like the module's globals, so it starts zeroed as in the module's
// .bss.
plaits::Voice voice;

const char *const kEngineNames[plaits::kMaxEngines] = {
  "VirtualAnalogVCFEngine", "PhaseDistortionEngine", "SixOpEngine bank 1",
  "SixOpEngine bank 2", "SixOpEngine bank 3", "WaveTerrainEngine",
  "StringMachineEngine", "ChiptuneEngine", "VirtualAnalogEngine",
  "WaveshapingEngine", "FMEngine", "GrainEngine", "AdditiveEngine",
  "WavetableEngine", "ChordEngine", "SpeechEngine", "SwarmEngine",
  "NoiseEngine", "ParticleEngine", "StringEngine", "ModalEngine",
  "BassDrumEngine", "SnareDrumEngine", "HiHatEngine",
};

// Voice::Render writes TRIG into a DelayLine and reads it at kTriggerDelay.
// DelayLine::Read(d) returns the sample written d - 1 writes before the
// latest (plaits/dsp/physical_modelling/delay_line.h), so TRIG reaches the
// engines kTriggerDelay - 1 blocks late: 48 samples, the "1ms" of voice.cc.
const int kTriggerLagBlocks = plaits::kTriggerDelay - 1;

void RenderUsage() {
  fprintf(stderr,
      "usage: fm1-ref-plaits --engine N [--note F] [--harmonics H] [--timbre T]\n"
      "         [--morph M] [--decay D] [--colour C] [--level L] [--seconds S]\n"
      "         [--gate S] [--mode trigger|ping|free] [--literal]\n"
      "         [--fm-amount A] [--timbre-amount A] [--morph-amount A]\n"
      "         [--delay-blocks N] [--seed N] [--out FILE.wav]\n"
      "         [--host-rate HZ [--host-frames N] [--host-gain G] [--at S]]\n"
      "       fm1-ref-plaits --compare REF.wav FM1.wav [options]  (see source)\n"
      "N is Plaits' engine index, 0..23. The WAV holds the module's DAC words,\n"
      "OUT left and AUX right, at 47,872 Hz (kCorrectedSampleRate, 47,872.34);\n"
      "with --host-rate, those words x G resampled to HZ as the wrappers do\n"
      "(not with --literal or --delay-blocks).\n");
}

// What fm1-render writes for an engine's sample (host/render.cc, WriteWav).
int16_t ToPcm(float x) {
  if (!(x == x)) x = 0.0f;
  if (x > 1.0f) x = 1.0f;
  if (x < -1.0f) x = -1.0f;
  return static_cast<int16_t>(lrintf(x * 32767.0f));
}

// The first host sample at which fm1-render applies an event at time t: the
// start of the first block of `frames` whose time, pos / rate, is at or after
// t. Beyond `limit` (the render's length) it never applies.
uint64_t HostEventPos(double t, float rate, uint64_t frames, uint64_t limit) {
  uint64_t pos = 0;
  while (!(t <= pos / static_cast<double>(rate)) && pos < limit) pos += frames;
  return pos;
}

bool WriteWav16(const char *path, const std::vector<int16_t> &lr, uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  const uint32_t data_bytes = static_cast<uint32_t>(lr.size() * 2);
  uint8_t h[44];
  memcpy(h, "RIFF", 4);
  const uint32_t riff = 36 + data_bytes;
  auto put32 = [&h](int at, uint32_t v) {
    h[at] = uint8_t(v); h[at + 1] = uint8_t(v >> 8);
    h[at + 2] = uint8_t(v >> 16); h[at + 3] = uint8_t(v >> 24);
  };
  auto put16 = [&h](int at, uint16_t v) { h[at] = uint8_t(v); h[at + 1] = uint8_t(v >> 8); };
  put32(4, riff);
  memcpy(h + 8, "WAVEfmt ", 8);
  put32(16, 16); put16(20, 1); put16(22, 2); put32(24, rate); put32(28, rate * 4);
  put16(32, 4); put16(34, 16);
  memcpy(h + 36, "data", 4);
  put32(40, data_bytes);
  fwrite(h, 1, sizeof(h), f);
  for (size_t i = 0; i < lr.size(); ++i) {
    const uint16_t v = static_cast<uint16_t>(lr[i]);
    const uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) };
    fwrite(b, 1, 2, f);
  }
  return fclose(f) == 0;
}

// Six-op engines: which of the bank's 32 patches HARMONICS selects, as
// SixOpEngine::Render quantises it (steady state from a fresh quantizer).
int SixOpPatchIndex(float harmonics) {
  stmlib::HysteresisQuantizer2 q;
  q.Init(32, 0.005f, false);
  return q.Process(harmonics * 1.02f);
}

int RenderMain(int argc, char **argv) {
  int engine = -1;
  float note = 60.0f, harmonics = 0.5f, timbre = 0.5f, morph = 0.5f;
  float decay = 0.5f, colour = 0.5f, level = 100.0f / 127.0f;
  float fm_amount = 0.0f, timbre_amount = 0.0f, morph_amount = 0.0f;
  double seconds = 1.0, gate = -1.0;
  std::string mode = "trigger";
  bool literal = false;
  bool seeded = false;
  long delay_blocks = 0;
  unsigned long seed = 0;
  const char *out_path = NULL;
  const char *host_rate_arg = NULL;   // --host-rate: the wrappers' output at that rate
  long host_frames = 64;
  float host_gain = 0.25f;
  double note_at = 0.0;
  bool at_given = false;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--literal") { literal = true; continue; }
    const char *next = i + 1 < argc ? argv[i + 1] : NULL;
    if (!next) { RenderUsage(); return 2; }
    ++i;
    if (a == "--engine") engine = atoi(next);
    else if (a == "--note") note = static_cast<float>(atof(next));
    else if (a == "--harmonics") harmonics = static_cast<float>(atof(next));
    else if (a == "--timbre") timbre = static_cast<float>(atof(next));
    else if (a == "--morph") morph = static_cast<float>(atof(next));
    else if (a == "--decay") decay = static_cast<float>(atof(next));
    else if (a == "--colour") colour = static_cast<float>(atof(next));
    else if (a == "--level") level = static_cast<float>(atof(next));
    else if (a == "--fm-amount") fm_amount = static_cast<float>(atof(next));
    else if (a == "--timbre-amount") timbre_amount = static_cast<float>(atof(next));
    else if (a == "--morph-amount") morph_amount = static_cast<float>(atof(next));
    else if (a == "--seconds") seconds = atof(next);
    else if (a == "--gate") gate = atof(next);
    else if (a == "--mode") mode = next;
    else if (a == "--seed") { seed = strtoul(next, NULL, 0); seeded = true; }
    else if (a == "--delay-blocks") delay_blocks = atol(next);
    else if (a == "--out") out_path = next;
    else if (a == "--host-rate") host_rate_arg = next;
    else if (a == "--host-frames") host_frames = atol(next);
    else if (a == "--host-gain") host_gain = static_cast<float>(atof(next));
    else if (a == "--at") { note_at = atof(next); at_given = true; }
    else { RenderUsage(); return 2; }
  }
  const bool host_mode = host_rate_arg != NULL;
  if (engine < 0 || engine >= plaits::kMaxEngines || seconds <= 0.0 || delay_blocks < 0 ||
      (mode != "trigger" && mode != "ping" && mode != "free") ||
      (host_mode && (literal || delay_blocks || host_frames < 1 || !(note_at >= 0.0))) ||
      (!host_mode && at_given)) {
    RenderUsage();
    return 2;
  }
  if (gate < 0.0) gate = seconds;
  const bool trigger_patched = mode != "free";
  const bool level_patched = mode == "trigger";

  const size_t kBlock = plaits::kBlockSize;
  const double rate = plaits::kCorrectedSampleRate;
  long blocks = static_cast<long>(ceil(seconds * rate / kBlock));
  long gate_blocks = static_cast<long>(floor(gate * rate / kBlock + 0.5));

  // Host-rate mode: which blocks the wrapper renders when. A dry run of the
  // resampler, fed zeros one sample at a time as fm1_resampler_needed asks,
  // gives the 47,872.34 Hz samples pulled before each host sample; an event
  // applied before host sample p reaches the first block not yet rendered,
  // ceil(pulled(p) / 12) [the same pull loop as mi_macro.cc's Render].
  float host_rate = 0.0f;
  uint32_t host_total = 0;
  long on_block = 0, off_block = LONG_MAX;
  if (host_mode) {
    host_rate = static_cast<float>(atof(host_rate_arg));   // as fm1-render parses --rate
    fm1_resampler_t dry;
    if (!fm1_resampler_init(&dry, plaits::kCorrectedSampleRate, host_rate)) {
      fprintf(stderr, "the resampler refuses %s Hz from %.2f Hz, as the wrappers do\n",
              host_rate_arg, rate);
      return 2;
    }
    host_total = static_cast<uint32_t>(seconds * host_rate);   // as fm1-render's total
    const uint64_t on_pos = HostEventPos(note_at, host_rate, host_frames, host_total);
    const uint64_t off_pos = HostEventPos(note_at + gate, host_rate, host_frames, host_total);
    const float zero = 0.0f;
    uint64_t pulled = 0, pulled_on = 0, pulled_off = 0;
    for (uint32_t f = 0; f < host_total; ++f) {
      if (f == on_pos) pulled_on = pulled;
      if (f == off_pos) pulled_off = pulled;
      while (fm1_resampler_needed(&dry)) pulled += fm1_resampler_push(&dry, &zero, 1);
      fm1_resampler_pop(&dry);
    }
    blocks = static_cast<long>((pulled + kBlock - 1) / kBlock);
    on_block = on_pos < host_total ? static_cast<long>((pulled_on + kBlock - 1) / kBlock)
                                   : blocks;   // never: silence throughout
    // fm1-render applies note-offs before note-ons within a block, so an off
    // in the note-on's own block comes first and the note is held.
    if (off_pos < host_total && off_pos != on_pos) {
      off_block = static_cast<long>((pulled_off + kBlock - 1) / kBlock);
    }
    delay_blocks = on_block;
    gate_blocks = off_block == LONG_MAX ? LONG_MAX / 2 : off_block - on_block;
  }

  stmlib::BufferAllocator allocator(shared_buffer, sizeof(shared_buffer));
  voice.Init(&allocator);
  if (seeded) stmlib::Random::Seed(static_cast<uint32_t>(seed));

  // Knobs: the note is the patch's (the module's V/OCT input would be
  // averaged with the previous block's value in Voice::Render); attenuverters
  // at the given amounts, centred (0) by default, as the wrappers apply no
  // internal-envelope modulation.
  plaits::Patch patch;
  patch.note = note;
  patch.harmonics = harmonics;
  patch.timbre = timbre;
  patch.morph = morph;
  patch.frequency_modulation_amount = fm_amount;
  patch.timbre_modulation_amount = timbre_amount;
  patch.morph_modulation_amount = morph_amount;
  patch.engine = engine;
  patch.decay = decay;
  patch.lpg_colour = colour;

  plaits::Modulations mod;
  memset(&mod, 0, sizeof(mod));
  mod.trigger_patched = trigger_patched;
  mod.level_patched = level_patched;

  // Aligned: lead TRIG by the delay, and render the lead-in on another
  // engine (GrainEngine: no arena, no randomness, silent with LEVEL at 0).
  // In host-rate mode the lead-in runs up to the note's block, which writes
  // silence: the wrapper has no voice before the note.
  const long lead = (!literal && trigger_patched) ? kTriggerLagBlocks : 0;
  const int preroll_engine = engine == 11 ? 8 : 11;
  const long engine_from = host_mode ? on_block : 0;   // the engine is selected here

  std::vector<int16_t> lr;
  lr.reserve(static_cast<size_t>(blocks) * kBlock * 2);
  plaits::Voice::Frame frames[plaits::kBlockSize];
  for (long b = std::min(0L, engine_from - lead); b < blocks; ++b) {
    patch.engine = b < engine_from ? preroll_engine : engine;
    const long trig_at = b + lead - delay_blocks;   // TRIG input now reaches the engine then
    const long at = b - delay_blocks;               // the note's own time
    mod.trigger = (trigger_patched && trig_at >= 0 && trig_at < gate_blocks) ? 1.0f : 0.0f;
    mod.level = (at >= 0 && at < gate_blocks) ? level : 0.0f;
    voice.Render(patch, mod, frames, kBlock);
    if (b < 0) continue;
    const bool silent = b < engine_from;
    const int16_t none = 0;
    for (size_t n = 0; n < kBlock; ++n) {
      lr.push_back(silent ? none : frames[n].out);
      lr.push_back(silent ? none : frames[n].aux);
    }
  }
  if (!host_mode) {
    lr.resize(static_cast<size_t>(seconds * rate) * 2);
  } else {
    // The wrapper's mix of one voice is the word x G / 32,768 (G = 0.25 x
    // Volume), the same float; resampled per channel, written as fm1-render
    // writes it.
    const size_t n_in = lr.size() / 2;
    const float scale = host_gain / 32768.0f;
    std::vector<float> in(n_in), y(host_total);
    std::vector<int16_t> out(2 * static_cast<size_t>(host_total));
    for (int ch = 0; ch < 2; ++ch) {
      for (size_t i = 0; i < n_in; ++i) in[i] = lr[2 * i + ch] * scale;
      fm1_resampler_t rs;
      fm1_resampler_init(&rs, plaits::kCorrectedSampleRate, host_rate);
      const uint32_t made = fm1_resampler_process(&rs, in.data(), static_cast<uint32_t>(n_in),
                                                  NULL, y.data(), host_total);
      if (made != host_total) {
        fprintf(stderr, "internal: %u of %u host-rate frames\n", made, host_total);
        return 1;
      }
      for (uint32_t i = 0; i < host_total; ++i) out[2 * i + ch] = ToPcm(y[i]);
    }
    lr.swap(out);
  }

  double peak[2] = { 0, 0 }, sum2[2] = { 0, 0 };
  for (size_t i = 0; i < lr.size(); ++i) {
    const double x = lr[i] / 32768.0;
    peak[i & 1] = std::max(peak[i & 1], fabs(x));
    sum2[i & 1] += x * x;
  }
  const size_t n_frames = lr.size() / 2;
  const uint32_t wav_rate = host_mode ? static_cast<uint32_t>(lrintf(host_rate))   // as fm1-render
                                      : static_cast<uint32_t>(lrint(rate));
  if (out_path && !WriteWav16(out_path, lr, wav_rate)) {
    fprintf(stderr, "cannot write %s\n", out_path);
    return 1;
  }

  printf("{\"tool\":\"fm1-ref-plaits\",\"engine\":%d,\"engine_name\":\"%s\","
         "\"active_engine\":%d,\"rate\":%.2f,\"block\":%zu,\"frames\":%zu,"
         "\"mode\":\"%s\",\"aligned\":%s,\"trigger_lag_samples\":%d,"
         "\"lead_blocks\":%ld,\"preroll_engine\":%d,\"shared_buffer\":%zu,"
         "\"note\":%g,\"harmonics\":%g,\"timbre\":%g,\"morph\":%g,\"decay\":%g,"
         "\"colour\":%g,\"level\":%g,\"gate\":%g,\"delay_blocks\":%ld,",
         engine, kEngineNames[engine], voice.active_engine(), rate, kBlock, n_frames,
         mode.c_str(), lead ? "true" : "false",
         kTriggerLagBlocks * static_cast<int>(kBlock), lead, lead ? preroll_engine : -1,
         sizeof(shared_buffer), note, harmonics, timbre, morph, decay, colour, level, gate,
         delay_blocks);
  // Unseeded, the generator is where Voice::Init left it: stmlib's initial
  // state, as in fm1-render (no engine draws from it in Init).
  if (seeded) printf("\"seed\":%lu,", seed & 0xFFFFFFFFul);
  else printf("\"seed\":null,");
  if (host_mode) {
    printf("\"host\":{\"rate\":%g,\"frames\":%ld,\"gain\":%g,\"out_frames\":%u,"
           "\"native_blocks\":%ld,\"on_block\":%ld,",
           host_rate, host_frames, host_gain, host_total, blocks, on_block);
    if (off_block == LONG_MAX) printf("\"off_block\":null,");
    else printf("\"off_block\":%ld,", off_block);
    printf("\"resampler_delay\":%d},", host_rate == static_cast<float>(rate) ? 0
                                                                            : FM1_RESAMPLER_DELAY);
  }
  if (engine >= 2 && engine <= 4) {
    const int index = SixOpPatchIndex(harmonics);
    plaits::fm::Patch p;
    p.Unpack(plaits::fm_patches_table[engine - 2] + index * plaits::fm::Patch::SYX_SIZE);
    char name[11];
    for (int i = 0; i < 10; ++i) {
      const char c = static_cast<char>(p.name[i]);
      name[i] = (c == '"' || c == '\\' || c < 32) ? '_' : c;
    }
    name[10] = 0;
    int end = 10;
    while (end > 0 && name[end - 1] == ' ') name[--end] = 0;
    printf("\"sixop\":{\"bank\":%d,\"slot\":%d,\"patch\":%d,\"name\":\"%s\","
           "\"transpose\":%d,\"key_sync\":%d},",
           engine - 2, index, (engine - 2) * 32 + index, name, p.transpose, p.reset_phase ? 1 : 0);
  }
  printf("\"out_peak\":%.6f,\"out_rms\":%.6f,\"aux_peak\":%.6f,\"aux_rms\":%.6f}\n",
         peak[0], n_frames ? sqrt(sum2[0] / n_frames) : 0.0,
         peak[1], n_frames ? sqrt(sum2[1] / n_frames) : 0.0);
  return 0;
}

// ---------------------------------------------------------------------------
// Compare mode.

struct Wav {
  double rate;
  int channels;
  std::vector<std::vector<double> > ch;
};

const double kPi = 3.14159265358979323846;

uint32_t Le32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | (uint32_t(p[3]) << 24); }
uint16_t Le16(const uint8_t *p) { return static_cast<uint16_t>(p[0] | (p[1] << 8)); }

// 16-bit PCM only (what both renderers write). A 47,872 Hz header is Plaits'
// kCorrectedSampleRate, which a WAV header cannot hold.
bool ReadWav(const char *path, Wav *w) {
  FILE *f = fopen(path, "rb");
  if (!f) return false;
  std::vector<uint8_t> d;
  uint8_t buf[65536];
  size_t n;
  while ((n = fread(buf, 1, sizeof(buf), f)) > 0) d.insert(d.end(), buf, buf + n);
  fclose(f);
  if (d.size() < 12 || memcmp(&d[0], "RIFF", 4) || memcmp(&d[8], "WAVE", 4)) return false;
  size_t pos = 12;
  int channels = 0, bits = 0;
  uint32_t rate = 0;
  while (pos + 8 <= d.size()) {
    const uint32_t len = Le32(&d[pos + 4]);
    const size_t body = pos + 8;
    if (body + len > d.size()) return false;
    if (!memcmp(&d[pos], "fmt ", 4) && len >= 16) {
      if (Le16(&d[body]) != 1) return false;
      channels = Le16(&d[body + 2]);
      rate = Le32(&d[body + 4]);
      bits = Le16(&d[body + 14]);
    } else if (!memcmp(&d[pos], "data", 4)) {
      if (bits != 16 || channels < 1) return false;
      const size_t frames = len / (2 * channels);
      w->channels = channels;
      w->rate = rate == 47872 ? plaits::kCorrectedSampleRate : rate;
      w->ch.assign(channels, std::vector<double>(frames));
      for (size_t i = 0; i < frames; ++i) {
        for (int c = 0; c < channels; ++c) {
          const size_t at = body + 2 * (i * channels + c);
          w->ch[c][i] = static_cast<int16_t>(Le16(&d[at])) / 32768.0;
        }
      }
      return true;
    }
    pos = body + len + (len & 1);
  }
  return false;
}

void Fft(std::vector<std::complex<double> > &a) {
  const size_t n = a.size();
  for (size_t i = 1, j = 0; i < n; ++i) {
    size_t bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) std::swap(a[i], a[j]);
  }
  for (size_t len = 2; len <= n; len <<= 1) {
    const double ang = -2.0 * kPi / static_cast<double>(len);
    const std::complex<double> wl(cos(ang), sin(ang));
    for (size_t i = 0; i < n; i += len) {
      std::complex<double> w(1.0, 0.0);
      for (size_t k = 0; k < len / 2; ++k) {
        const std::complex<double> u = a[i + k], v = a[i + k + len / 2] * w;
        a[i + k] = u + v;
        a[i + k + len / 2] = u - v;
        w *= wl;
      }
    }
  }
}

// Magnitude spectrum of x[a, b) (Hann window, zero-padded to 4x or more).
struct Spectrum {
  double bin_hz;
  std::vector<double> mag;
  double total;        // sum of mag^2 over [0, Nyquist]
  double ms;           // the windowed segment's mean square, per unit window power
  double MagAt(double hz) const {
    const double k = hz / bin_hz;
    const size_t i = static_cast<size_t>(k);
    if (i + 1 >= mag.size()) return 0.0;
    const double t = k - i;
    return mag[i] + (mag[i + 1] - mag[i]) * t;
  }
};

Spectrum Analyse(const std::vector<double> &x, size_t a, size_t b, double rate) {
  Spectrum s;
  s.total = s.ms = 0.0;
  if (b > x.size()) b = x.size();
  if (a >= b) { s.bin_hz = 1.0; return s; }
  const size_t len = b - a;
  size_t n = 1;
  while (n < 4 * len) n <<= 1;
  std::vector<std::complex<double> > buf(n);
  double sxw = 0, sw = 0;
  for (size_t i = 0; i < len; ++i) {
    const double w = 0.5 - 0.5 * cos(2.0 * kPi * (i + 0.5) / len);
    buf[i] = x[a + i] * w;
    sxw += x[a + i] * w * x[a + i] * w;
    sw += w * w;
  }
  Fft(buf);
  s.bin_hz = rate / n;
  s.mag.resize(n / 2 + 1);
  for (size_t i = 0; i <= n / 2; ++i) {
    s.mag[i] = std::abs(buf[i]);
    s.total += s.mag[i] * s.mag[i];
  }
  s.ms = sw > 0 ? sxw / sw : 0.0;
  return s;
}

// Pitch shift of b relative to a, in cents: the log-frequency shift that best
// correlates the two magnitude spectra (every partial of a chord, a detuned
// swarm or an inharmonic bell moves by the same amount).
void PitchShift(const Spectrum &a, const Spectrum &b, double lo, double hi, int range,
                double *cents, double *corr) {
  *cents = NAN;
  *corr = NAN;
  const int n = static_cast<int>(floor(1200.0 * log2(hi / lo)));
  if (n < 2 * range + 10 || a.mag.empty() || b.mag.empty()) return;
  std::vector<double> A(n), B(n);
  for (int g = 0; g < n; ++g) {
    const double hz = lo * pow(2.0, g / 1200.0);
    A[g] = a.MagAt(hz);
    B[g] = b.MagAt(hz);
  }
  std::vector<double> c(2 * range + 1);
  for (int s = -range; s <= range; ++s) {
    double ab = 0, aa = 0, bb = 0;
    for (int g = std::max(0, -s); g < std::min(n, n - s); ++g) {
      ab += A[g] * B[g + s];
      aa += A[g] * A[g];
      bb += B[g + s] * B[g + s];
    }
    c[s + range] = (aa > 0 && bb > 0) ? ab / sqrt(aa * bb) : 0.0;
  }
  int best = 0;
  for (int i = 1; i < static_cast<int>(c.size()); ++i) if (c[i] > c[best]) best = i;
  double offset = 0.0;
  if (best > 0 && best + 1 < static_cast<int>(c.size())) {
    const double y0 = c[best - 1], y1 = c[best], y2 = c[best + 1];
    const double den = y0 - 2 * y1 + y2;
    if (den < 0) offset = 0.5 * (y0 - y2) / den;
  }
  *cents = best - range + offset;
  *corr = c[best];
}

// Power in 1/6-octave bands from lo to hi, normalised to a total of 1 (so two
// rates' spectra compare band for band). Empty if silent. *share is the part
// of the whole spectrum's power the bands hold.
std::vector<double> BandPowers(const Spectrum &a, double lo, double hi,
                               std::vector<double> *centres, std::vector<double> *widths,
                               double *share) {
  std::vector<double> p;
  if (centres) centres->clear();
  if (widths) widths->clear();
  for (double f0 = lo; f0 < hi; f0 *= pow(2.0, 1.0 / 6.0)) {
    const double f1 = std::min(hi, f0 * pow(2.0, 1.0 / 6.0));
    double e = 0;
    for (size_t k = static_cast<size_t>(ceil(f0 / a.bin_hz)); k < a.mag.size() && k * a.bin_hz < f1; ++k)
      e += a.mag[k] * a.mag[k];
    p.push_back(e);
    if (centres) centres->push_back(sqrt(f0 * f1));
    if (widths) widths->push_back(f1 - f0);
  }
  double total = 0;
  for (size_t i = 0; i < p.size(); ++i) total += p[i];
  if (share) *share = a.total > 0 ? total / a.total : 0.0;
  if (!(total > 0)) return std::vector<double>();
  for (size_t i = 0; i < p.size(); ++i) p[i] /= total;
  return p;
}

// Log-spectral distance between two BandPowers. Both are floored at the
// higher of `floor_db` below the loudest band of either and noise[i], the
// share band i would hold of white noise at the quantisation limit; one floor
// for both, so bands that only the fm1 side's coarser quantisation (a quarter
// of full scale at Volume 1) lifts above the other's do not count.
double BandLsd(const std::vector<double> &pa, const std::vector<double> &pb, double floor_db,
               const std::vector<double> &noise) {
  if (pa.empty() || pa.size() != pb.size()) return NAN;
  double m = 0;
  for (size_t i = 0; i < pa.size(); ++i) m = std::max(m, std::max(pa[i], pb[i]));
  const double fl = m * pow(10.0, -floor_db / 10.0);
  double sum = 0;
  for (size_t i = 0; i < pa.size(); ++i) {
    const double f = std::max(fl, noise[i]);
    const double d = 10.0 * log10(std::max(pa[i], f) / std::max(pb[i], f));
    sum += d * d;
  }
  return sqrt(sum / pa.size());
}

// Shift in cents of b's spectral envelope against a's: both power spectra
// averaged over +/-1/24 octave around each point of a 1-cent grid, in dB
// floored 50 dB under their peaks, then the shift that maximises the Pearson
// correlation. Unlike PitchShift it ignores fine structure, so it follows a
// resonance or a filter through noise, and a pitch through a random texture.
double EnvelopeShift(const Spectrum &a, const Spectrum &b, double lo, double hi, int range,
                     double *corr) {
  *corr = NAN;
  const int n = static_cast<int>(floor(1200.0 * log2(hi / lo)));
  if (n < 2 * range + 10 || a.mag.empty() || b.mag.empty()) return NAN;
  std::vector<double> A(n), B(n);
  const Spectrum *s[2] = { &a, &b };
  std::vector<double> *out[2] = { &A, &B };
  for (int k = 0; k < 2; ++k) {
    const Spectrum &sp = *s[k];
    std::vector<double> cum(sp.mag.size() + 1, 0.0);
    for (size_t i = 0; i < sp.mag.size(); ++i) cum[i + 1] = cum[i] + sp.mag[i] * sp.mag[i];
    double peak = -400.0;
    for (int g = 0; g < n; ++g) {
      const double hz = lo * pow(2.0, g / 1200.0);
      size_t i0 = static_cast<size_t>(hz * pow(2.0, -1.0 / 24.0) / sp.bin_hz);
      size_t i1 = static_cast<size_t>(hz * pow(2.0, 1.0 / 24.0) / sp.bin_hz) + 1;
      i1 = std::min(i1, sp.mag.size());
      i0 = std::min(i0, i1 - 1);
      const double v = 10.0 * log10((cum[i1] - cum[i0]) / (i1 - i0) + 1e-30);
      (*out[k])[g] = v;
      peak = std::max(peak, v);
    }
    for (int g = 0; g < n; ++g) (*out[k])[g] = std::max((*out[k])[g], peak - 50.0);
  }
  std::vector<double> c(2 * range + 1);
  for (int sh = -range; sh <= range; ++sh) {
    const int g0 = std::max(0, -sh), g1 = std::min(n, n - sh);
    double ma = 0, mb = 0;
    for (int g = g0; g < g1; ++g) { ma += A[g]; mb += B[g + sh]; }
    ma /= (g1 - g0);
    mb /= (g1 - g0);
    double ab = 0, aa = 0, bb = 0;
    for (int g = g0; g < g1; ++g) {
      const double x = A[g] - ma, y = B[g + sh] - mb;
      ab += x * y; aa += x * x; bb += y * y;
    }
    c[sh + range] = (aa > 0 && bb > 0) ? ab / sqrt(aa * bb) : 0.0;
  }
  int best = 0;
  for (int i = 1; i < static_cast<int>(c.size()); ++i) if (c[i] > c[best]) best = i;
  double offset = 0.0;
  if (best > 0 && best + 1 < static_cast<int>(c.size())) {
    const double y0 = c[best - 1], y1 = c[best], y2 = c[best + 1];
    const double den = y0 - 2 * y1 + y2;
    if (den < 0) offset = 0.5 * (y0 - y2) / den;
  }
  *corr = c[best];
  return best - range + offset;
}

// Power-weighted mean of log2(frequency) over the bands, in cents: where the
// spectrum's weight sits, for signals without a pitch (noise, particles).
double CentroidCents(const std::vector<double> &p, const std::vector<double> &centres) {
  if (p.empty()) return NAN;
  double s = 0;
  for (size_t i = 0; i < p.size(); ++i) s += p[i] * 1200.0 * log2(centres[i]);
  return s;
}

// RMS in dB of window [t, t + w) seconds, shifted by `shift` samples.
double WindowDb(const std::vector<double> &x, double rate, double t, double w, long shift) {
  const long a = static_cast<long>(floor(t * rate)) + shift;
  const long b = static_cast<long>(floor((t + w) * rate)) + shift;
  double s = 0;
  long n = 0;
  for (long i = a; i < b; ++i, ++n) {
    if (i >= 0 && i < static_cast<long>(x.size())) s += x[i] * x[i];
  }
  return n ? 10.0 * log10(s / n + 1e-20) : -200.0;
}

// Time for the envelope (5 ms windows, 1 ms hop) to fall `db` below its peak,
// or below its level just before t0 when t0 >= 0. NaN if it never does.
double DecayTime(const std::vector<double> &x, double rate, double t0, double db) {
  const double w = 0.005, hop = 0.001;
  const double dur = x.size() / rate;
  std::vector<double> env;
  for (double t = 0; t + w <= dur; t += hop) env.push_back(WindowDb(x, rate, t, w, 0));
  if (env.empty()) return NAN;
  size_t start;
  double level;
  if (t0 >= 0) {
    const long k = static_cast<long>(floor((t0 - w) / hop));
    if (k < 0 || k >= static_cast<long>(env.size())) return NAN;
    start = static_cast<size_t>(k);
    level = env[start];
  } else {
    start = std::max_element(env.begin(), env.end()) - env.begin();
    level = env[start];
  }
  const double target = level - db;
  for (size_t k = start + 1; k < env.size(); ++k) {
    if (env[k] < target) {
      const double f = (env[k - 1] - target) / (env[k - 1] - env[k]);
      const double tk = (k - 1 + f) * hop;
      return tk - (t0 >= 0 ? t0 - w : start * hop);
    }
  }
  return NAN;
}

// Envelope in dB on a 1 ms grid, each point the RMS of a window centred on it.
std::vector<double> Envelope(const std::vector<double> &x, double rate, double w) {
  std::vector<double> env;
  const double dur = x.size() / rate;
  for (double t = 0; t <= dur; t += 0.001) env.push_back(WindowDb(x, rate, t - w / 2, w, 0));
  return env;
}

double EnvAt(const std::vector<double> &env, double t) {
  const double k = t / 0.001;
  const size_t i = static_cast<size_t>(k);
  if (k < 0 || i + 1 >= env.size()) return NAN;
  return env[i] + (env[i + 1] - env[i]) * (k - i);
}

// Time stretch of y against x after the event at t0: the factor a for which
// y's envelope at t0 + a*tau best matches x's at t0 + tau, over the tau where
// x is within floor_db of its loudest point after t0. The level offset is
// removed (median difference), so only timing is fitted. `resid` is the mean
// absolute dB difference left at the best a.
void StretchFit(const std::vector<double> &x, double rx, const std::vector<double> &y,
                double ry, double t0, double w, double floor_db, double lo, double hi,
                double *alpha, double *resid) {
  *alpha = NAN;
  *resid = NAN;
  const std::vector<double> ex = Envelope(x, rx, w), ey = Envelope(y, ry, w);
  const double span = std::min(x.size() / rx - t0, (y.size() / ry - t0) / hi) - w;
  if (span <= 0.01) return;
  std::vector<double> tau, ref;
  double peak = -200.0;
  for (double t = 0; t <= span; t += 0.001) peak = std::max(peak, EnvAt(ex, t0 + t));
  for (double t = 0; t <= span; t += 0.001) {
    const double v = EnvAt(ex, t0 + t);
    if (v > peak - floor_db) { tau.push_back(t); ref.push_back(v); }
  }
  if (tau.size() < 10) return;
  std::vector<double> d(tau.size());
  double best = 1e9;
  for (double a = lo; a <= hi + 1e-9; a += 0.0005) {
    for (size_t k = 0; k < tau.size(); ++k) {
      d[k] = std::max(EnvAt(ey, t0 + a * tau[k]), peak - floor_db - 20) - ref[k];
    }
    std::vector<double> s(d);
    std::nth_element(s.begin(), s.begin() + s.size() / 2, s.end());
    const double med = s[s.size() / 2];
    double cost = 0;
    for (size_t k = 0; k < d.size(); ++k) cost += fabs(d[k] - med);
    cost /= d.size();
    if (cost < best) { best = cost; *alpha = a; *resid = cost; }
  }
}

// Decay rate in dB per second after the event at t0 (the envelope peak when
// t0 is 0): a least-squares line through the envelope (window w, 1 ms hop)
// from its level at t0 down to `span_db` below it. The ratio of two such
// rates is the time stretch between them when one decay is a stretched copy
// of the other, and a line through several beats of a chord averages them
// out. NaN when the envelope does not fall 10 dB.
double DecayRate(const std::vector<double> &x, double rate, double t0, double w, double span_db) {
  const std::vector<double> env = Envelope(x, rate, w);
  size_t k0;
  if (t0 > 0) {
    const long k = static_cast<long>(floor((t0 - w / 2) / 0.001));
    if (k < 0 || k >= static_cast<long>(env.size())) return NAN;
    k0 = static_cast<size_t>(k);
  } else {
    k0 = std::max_element(env.begin(), env.end()) - env.begin();
  }
  const double start = env[k0], stop = start - span_db;
  double st = 0, sv = 0, stt = 0, stv = 0, lowest = start;
  int n = 0;
  for (size_t k = k0; k < env.size() && env[k] >= stop; ++k, ++n) {
    const double t = (k - k0) * 0.001;
    st += t; sv += env[k]; stt += t * t; stv += t * env[k];
    lowest = std::min(lowest, env[k]);
  }
  if (n < 10 || start - lowest < 10.0) return NAN;
  const double den = n * stt - st * st;
  return den > 0 ? -(n * stv - st * sv) / den : NAN;
}

void CompareUsage() {
  fprintf(stderr,
      "usage: fm1-ref-plaits --compare REF.wav FM1.wav [--ref-channel C]\n"
      "         [--fm1-channel C] [--gain G] [--from S] [--to S] [--max-lag-ms MS]\n"
      "         [--env-window-ms MS] [--env-floor-db DB] [--t0 S] [--decay-db DB]\n"
      "         [--stretch-window-ms MS] [--stretch-lo A] [--stretch-hi A]\n"
      "         [--pitch-lo HZ] [--pitch-hi HZ] [--pitch-range CENTS]\n"
      "         [--lsd-lo HZ] [--lsd-hi HZ] [--lsd-floor-db DB] [--noise-dbfs DB]\n"
      "         [--no-timing]\n"
      "--from/--to bound the waveform, level, envelope and spectral metrics;\n"
      "--t0 is the event the decay time and stretch are measured from (default:\n"
      "the note-on at 0 for the stretch, the envelope peak for the decay).\n");
}

void JsonNum(const char *key, double v, bool comma = true) {
  if (std::isfinite(v)) printf("\"%s\":%.6g", key, v);
  else printf("\"%s\":null", key);
  if (comma) putchar(',');
}

int CompareMain(int argc, char **argv) {
  const char *ref_path = argv[2], *fm1_path = argv[3];
  int ref_ch = 0, fm1_ch = 0, pitch_range = 150;
  double gain = 0.25, from = 0.0, to = -1.0, max_lag_ms = 5.0, env_w_ms = 10.0;
  double env_floor = 40.0, t0 = -1.0, decay_db = 20.0;
  double stretch_w_ms = 20.0, stretch_lo = 0.8, stretch_hi = 1.3;
  double pitch_lo = 40.0, pitch_hi = 12000.0, lsd_lo = 50.0, lsd_hi = 16000.0, lsd_floor = 50.0;
  double noise_dbfs = -80.0;
  bool timing = true;
  for (int i = 4; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--no-timing") { timing = false; continue; }
    const char *next = i + 1 < argc ? argv[i + 1] : NULL;
    if (!next) { CompareUsage(); return 2; }
    ++i;
    if (a == "--ref-channel") ref_ch = atoi(next);
    else if (a == "--fm1-channel") fm1_ch = atoi(next);
    else if (a == "--gain") gain = atof(next);
    else if (a == "--from") from = atof(next);
    else if (a == "--to") to = atof(next);
    else if (a == "--max-lag-ms") max_lag_ms = atof(next);
    else if (a == "--env-window-ms") env_w_ms = atof(next);
    else if (a == "--env-floor-db") env_floor = atof(next);
    else if (a == "--t0") t0 = atof(next);
    else if (a == "--decay-db") decay_db = atof(next);
    else if (a == "--stretch-window-ms") stretch_w_ms = atof(next);
    else if (a == "--stretch-lo") stretch_lo = atof(next);
    else if (a == "--stretch-hi") stretch_hi = atof(next);
    else if (a == "--pitch-lo") pitch_lo = atof(next);
    else if (a == "--pitch-hi") pitch_hi = atof(next);
    else if (a == "--pitch-range") pitch_range = atoi(next);
    else if (a == "--lsd-lo") lsd_lo = atof(next);
    else if (a == "--lsd-hi") lsd_hi = atof(next);
    else if (a == "--lsd-floor-db") lsd_floor = atof(next);
    else if (a == "--noise-dbfs") noise_dbfs = atof(next);
    else { CompareUsage(); return 2; }
  }
  Wav rw, fw;
  if (!ReadWav(ref_path, &rw) || !ReadWav(fm1_path, &fw)) {
    fprintf(stderr, "cannot read %s or %s (16-bit PCM WAV)\n", ref_path, fm1_path);
    return 1;
  }
  if (ref_ch < 0 || ref_ch >= rw.channels || fm1_ch < 0 || fm1_ch >= fw.channels ||
      gain == 0.0) {
    CompareUsage();
    return 2;
  }
  const std::vector<double> &x = rw.ch[ref_ch];
  const std::vector<double> &y = fw.ch[fm1_ch];
  const double rx = rw.rate, ry = fw.rate;
  const double dur = std::min(x.size() / rx, y.size() / ry);
  if (to < 0 || to > dur) to = dur;
  if (from < 0) from = 0;
  const bool same_rate = fabs(rx - ry) < 1e-3 * rx;
  const double sign = gain > 0 ? 1.0 : -1.0;

  // Waveform: best lag of y against x over [from, to), least-squares gain.
  double ncc = NAN, ls_gain = NAN, residual_db = NAN, err_dbfs = NAN;
  long lag = 0;
  if (same_rate) {
    const long a = static_cast<long>(from * rx), b = static_cast<long>(to * rx);
    const long max_lag = static_cast<long>(max_lag_ms * 1e-3 * rx);
    double sxx = 0;
    for (long n = a; n < b; ++n) sxx += x[n] * x[n];
    double best = -2.0;
    for (long l = -max_lag; l <= max_lag; ++l) {
      double sxy = 0, syy = 0;
      for (long n = a; n < b; ++n) {
        const long m = n + l;
        if (m < 0 || m >= static_cast<long>(y.size())) continue;
        sxy += x[n] * y[m];
        syy += y[m] * y[m];
      }
      if (!(sxx > 0) || !(syy > 0)) continue;
      const double c = sign * sxy / sqrt(sxx * syy);
      if (c > best) {
        best = c;
        lag = l;
        ncc = c;
        ls_gain = sxy / sxx;
      }
    }
    if (std::isfinite(ncc)) residual_db = 10.0 * log10(std::max(1.0 - ncc * ncc, 1e-15));
    // The error at the expected gain and the best lag, in dB of full scale:
    // independent of the signal's own level, so it can be held against the
    // 16-bit quantisation of the two WAVs.
    double se = 0;
    for (long n = a; n < b; ++n) {
      const long m = n + lag;
      const double ym = (m >= 0 && m < static_cast<long>(y.size())) ? y[m] : 0.0;
      const double e = ym / gain - x[n];
      se += e * e;
    }
    if (b > a) err_dbfs = 10.0 * log10(se / (b - a) + 1e-30);
  }

  // Level over [from, to), against the expected gain.
  double ex = 0, ey = 0;
  long nx = 0, ny = 0;
  for (long n = static_cast<long>(from * rx); n < static_cast<long>(to * rx); ++n, ++nx) ex += x[n] * x[n];
  for (long n = static_cast<long>(from * ry); n < static_cast<long>(to * ry); ++n, ++ny) ey += y[n] * y[n];
  const double level_db = (ex > 0 && ey > 0 && nx && ny)
      ? 10.0 * log10((ey / ny) / (gain * gain * (ex / nx))) : NAN;

  // Envelope distance: windowed RMS in dB over [from, to), y scaled by
  // 1/|gain| and shifted by the waveform lag when one was found, over windows
  // where either side is within env_floor dB of the reference's loudest one.
  const long env_shift = (same_rate && std::isfinite(ncc) && ncc > 0.5) ? lag : 0;
  const double w = env_w_ms * 1e-3, hop = w / 2;
  std::vector<double> ed_x, ed_y;
  double peak_db = -200.0;
  for (double t = from; t + w <= to; t += hop) {
    ed_x.push_back(WindowDb(x, rx, t, w, 0));
    ed_y.push_back(WindowDb(y, ry, t, w, env_shift) - 20.0 * log10(fabs(gain)));
    peak_db = std::max(peak_db, ed_x.back());
  }
  // Windows quieter than 10 dB above the quantisation limit say nothing.
  const double floor_db = std::max(peak_db - env_floor, noise_dbfs + 10.0);
  double env_max = 0, env_sum = 0;
  int env_n = 0;
  for (size_t k = 0; k < ed_x.size(); ++k) {
    if (ed_x[k] < floor_db && ed_y[k] < floor_db) continue;
    const double d = fabs(std::max(ed_y[k], floor_db - 20) - std::max(ed_x[k], floor_db - 20));
    env_max = std::max(env_max, d);
    env_sum += d;
    ++env_n;
  }

  double decay_x = NAN, decay_y = NAN, rate_x = NAN, rate_y = NAN;
  double stretch = NAN, stretch_resid = NAN;
  if (timing) {
    decay_x = DecayTime(x, rx, t0, decay_db);
    decay_y = DecayTime(y, ry, t0, decay_db);
    rate_x = DecayRate(x, rx, t0 >= 0 ? t0 : 0.0, stretch_w_ms * 1e-3, 30.0);
    rate_y = DecayRate(y, ry, t0 >= 0 ? t0 : 0.0, stretch_w_ms * 1e-3, 30.0);
    StretchFit(x, rx, y, ry, t0 >= 0 ? t0 : 0.0, stretch_w_ms * 1e-3, env_floor,
               stretch_lo, stretch_hi, &stretch, &stretch_resid);
  }

  // Spectra over [from, to).
  const Spectrum sx = Analyse(x, static_cast<size_t>(from * rx), static_cast<size_t>(to * rx), rx);
  const Spectrum sy = Analyse(y, static_cast<size_t>(from * ry), static_cast<size_t>(to * ry), ry);
  const double nyq = 0.45 * std::min(rx, ry);
  double pitch_cents, pitch_corr;
  PitchShift(sx, sy, pitch_lo, std::min(pitch_hi, nyq), pitch_range, &pitch_cents, &pitch_corr);
  std::vector<double> centres, widths;
  double share_x = 0;
  const std::vector<double> bx = BandPowers(sx, lsd_lo, std::min(lsd_hi, nyq), &centres, &widths,
                                            &share_x);
  const std::vector<double> by = BandPowers(sy, lsd_lo, std::min(lsd_hi, nyq), NULL, NULL, NULL);
  // White noise at noise_dbfs (reference scale) in each band, in the units
  // of bx: its power over the windowed segment's, times the band's share of
  // the spectrum, over the share the bands hold of the reference's power.
  std::vector<double> noise(widths.size(), 0.0);
  if (sx.ms > 0 && share_x > 0) {
    for (size_t i = 0; i < widths.size(); ++i)
      noise[i] = pow(10.0, noise_dbfs / 10.0) / sx.ms * widths[i] / (rx / 2) / share_x;
  }
  const double lsd = BandLsd(bx, by, lsd_floor, noise);
  double shift_corr;
  const double shift = EnvelopeShift(sx, sy, pitch_lo, std::min(pitch_hi, nyq), pitch_range,
                                     &shift_corr);
  const double centroid = CentroidCents(by, centres) - CentroidCents(bx, centres);

  printf("{");
  JsonNum("ref_rate", rx);
  JsonNum("fm1_rate", ry);
  JsonNum("from", from);
  JsonNum("to", to);
  JsonNum("gain", gain);
  JsonNum("ncc", ncc);
  printf("\"lag\":%ld,", lag);
  JsonNum("ls_gain", ls_gain);
  JsonNum("gain_db", std::isfinite(ls_gain) ? 20.0 * log10(fabs(ls_gain / gain)) : NAN);
  JsonNum("residual_db", residual_db);
  JsonNum("err_dbfs", err_dbfs);
  JsonNum("level_db", level_db);
  JsonNum("env_max_db", env_n ? env_max : NAN);
  JsonNum("env_mean_db", env_n ? env_sum / env_n : NAN);
  printf("\"env_windows\":%d,", env_n);
  JsonNum("ref_peak_db", peak_db);
  JsonNum("decay_ref_s", decay_x);
  JsonNum("decay_fm1_s", decay_y);
  JsonNum("decay_ratio", decay_y / decay_x);
  JsonNum("decay_rate_ref", rate_x);
  JsonNum("decay_rate_fm1", rate_y);
  JsonNum("slope_stretch", rate_x / rate_y);
  JsonNum("stretch", stretch);
  JsonNum("stretch_resid_db", stretch_resid);
  JsonNum("pitch_cents", pitch_cents);
  JsonNum("pitch_corr", pitch_corr);
  JsonNum("centroid_cents", centroid);
  JsonNum("shift_cents", shift);
  JsonNum("shift_corr", shift_corr);
  JsonNum("lsd_db", lsd, false);
  printf("}\n");
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc >= 4 && !strcmp(argv[1], "--compare")) return CompareMain(argc, argv);
  return RenderMain(argc, argv);
}
