// dx7_voice.cc -- DX7 voice data for the FM6 engine: ranges, unpacking and
// the SysEx reader (dx7_voice.h, fm1_dx7.h).
//
// The dump formats are the DX7's own: a single voice (VCED) is
// F0 43 0n 00 01 1B, 155 data bytes, a checksum, F7; a bank (VMEM) is
// F0 43 0n 09 20 00, 4,096 data bytes (32 voices of 128 packed bytes), a
// checksum, F7. The checksum makes the data bytes and itself sum to 0 in
// seven bits. n is the MIDI channel, ignored here.
//
// Our own code. MIT licence (this file).

#include "dx7_voice.h"

#include <string.h>

#include "msfa.h"

namespace fm1 {
namespace dx7 {

namespace {

// The largest value of each byte of an operator, in VCED order
// (fm1_dx7_op_fields below names them; tests/test_engines_dx7.py checks the
// two agree).
const uint8_t kOpMax[kOpBytes] = {
  99, 99, 99, 99,   // R1..R4
  99, 99, 99, 99,   // L1..L4
  99, 99, 99,       // break point, left and right depth
  3, 3,             // left and right curve
  7,                // rate scaling
  3,                // amplitude modulation sensitivity
  7,                // key velocity sensitivity
  99,               // output level
  1,                // mode: ratio, fixed
  31, 99,           // coarse, fine
  14,               // detune (7 = none)
};

// ... and of the voice's own bytes, from the pitch envelope to transpose.
const uint8_t kVoiceMax[V_NAME - V_PR1] = {
  99, 99, 99, 99,   // PR1..PR4
  99, 99, 99, 99,   // PL1..PL4
  31,               // algorithm (0 = algorithm 1)
  7,                // feedback
  1,                // oscillator key sync
  99, 99, 99, 99,   // LFO speed, delay, pitch and amplitude depth
  1,                // LFO key sync
  5,                // LFO wave: triangle, saw down, saw up, square, sine, S/H
  7,                // pitch modulation sensitivity
  48,               // transpose (24 = none)
};

}  // namespace

const uint8_t kInitVoice[kVoiceBytes] = {
  // operators 6..2: output level 0
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7,
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7,
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7,
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7,
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 7,
  // operator 1: output level 99
  99, 99, 99, 99, 99, 99, 99, 0, 39, 0, 0, 0, 0, 0, 0, 0, 99, 0, 1, 0, 7,
  99, 99, 99, 99, 50, 50, 50, 50,          // pitch envelope: flat
  0, 0, 1,                                 // algorithm 1, feedback 0, key sync
  35, 0, 0, 0, 1, 0, 3,                    // LFO
  24,                                      // transpose: none
  'I', 'N', 'I', 'T', ' ', 'V', 'O', 'I', 'C', 'E',
  0x3F,
};

void Sanitize(uint8_t v[kVoiceBytes]) {
  for (int op = 0; op < 6; ++op) {
    uint8_t *o = v + op * kOpBytes;
    for (int i = 0; i < kOpBytes; ++i) {
      if (o[i] > kOpMax[i]) o[i] = kOpMax[i];
    }
  }
  for (int i = V_PR1; i < V_NAME; ++i) {
    if (v[i] > kVoiceMax[i - V_PR1]) v[i] = kVoiceMax[i - V_PR1];
  }
  for (int i = V_NAME; i < V_NAME + (int)FM1_DX7_NAME_BYTES; ++i) {
    if (v[i] < 32 || v[i] > 126) v[i] = ' ';
  }
  v[V_OPSW] = 0x3F;
}

void FromPacked(const uint8_t packed[kPackedBytes], uint8_t v[kVoiceBytes]) {
  // UnpackPatch reads and writes plain char; the bytes are 7-bit here
  // (ParseSysex refuses anything else) and are clamped after.
  char bulk[kPackedBytes];
  char out[kVoiceBytes];
  for (int i = 0; i < kPackedBytes; ++i) bulk[i] = static_cast<char>(packed[i] & 0x7F);
  fm1_msfa::UnpackPatch(bulk, out);
  for (int i = 0; i < kVoiceBytes; ++i) v[i] = static_cast<uint8_t>(out[i]) & 0x7F;
  Sanitize(v);
}

void ToPacked(const uint8_t vced[FM1_DX7_VCED_BYTES], uint8_t packed[kPackedBytes]) {
  uint8_t v[kVoiceBytes];
  FromVced(vced, v);
  for (int op = 0; op < 6; ++op) {
    const uint8_t *o = v + op * kOpBytes;
    uint8_t *p = packed + op * 17;
    memcpy(p, o, 11);                                       // rates, levels, break point, depths
    p[11] = static_cast<uint8_t>(o[OP_LC] | o[OP_RC] << 2);
    p[12] = static_cast<uint8_t>(o[OP_RS] | o[OP_DET] << 3);
    p[13] = static_cast<uint8_t>(o[OP_AMS] | o[OP_KVS] << 2);
    p[14] = o[OP_OL];
    p[15] = static_cast<uint8_t>(o[OP_MODE] | o[OP_FC] << 1);
    p[16] = o[OP_FF];
  }
  memcpy(packed + 102, v + V_PR1, 9);                       // pitch envelope, algorithm
  packed[111] = static_cast<uint8_t>(v[V_FB] | v[V_OKS] << 3);
  memcpy(packed + 112, v + V_LFS, 4);                       // LFO speed, delay, depths
  packed[116] = static_cast<uint8_t>(v[V_LKS] | v[V_LFW] << 1 | v[V_LPMS] << 4);
  memcpy(packed + 117, v + V_TRNSP, 1 + FM1_DX7_NAME_BYTES);   // transpose, name
}

void FromVced(const uint8_t data[FM1_DX7_VCED_BYTES], uint8_t v[kVoiceBytes]) {
  memcpy(v, data, FM1_DX7_VCED_BYTES);
  Sanitize(v);
}

void Name(const uint8_t v[kVoiceBytes], char out[FM1_DX7_NAME_BYTES + 1]) {
  unsigned n = FM1_DX7_NAME_BYTES;
  memcpy(out, v + V_NAME, n);
  while (n > 0 && out[n - 1] == ' ') --n;
  out[n] = '\0';
}

int ParseSysex(const uint8_t *data, size_t len, unsigned slot, StoreFn store, void *ctx,
               fm1_dx7_sysex_result_t *res) {
  fm1_dx7_sysex_result_t r;
  memset(&r, 0, sizeof(r));
  slot %= FM1_DX7_USER_SLOTS;
  r.first_slot = static_cast<uint16_t>(slot);
  bool first = true;
  uint8_t voice[kVoiceBytes];
  bool framed = false;
  size_t i = 0;
  while (data && i < len) {
    if (data[i] != 0xF0) { ++i; ++r.outside; continue; }
    framed = true;
    // The message runs to the next status byte; a well-formed one ends at F7.
    size_t end = i + 1;
    while (end < len && data[end] < 0x80) ++end;
    if (end >= len || data[end] != 0xF7) {   // truncated, or another status byte
      ++r.skipped;
      ++r.truncated;
      i = end;
      continue;
    }
    const uint8_t *m = data + i;
    const size_t n = end - i + 1;            // F0 .. F7
    const bool yamaha = n >= 8 && m[1] == 0x43 && (m[2] & 0xF0) == 0x00;
    const unsigned count = yamaha ? (unsigned(m[4]) << 7 | m[5]) : 0;
    const bool vced = yamaha && m[3] == 0x00 && count == FM1_DX7_VCED_BYTES &&
                      n == FM1_DX7_VCED_BYTES + 8;
    const bool vmem = yamaha && m[3] == 0x09 && count == FM1_DX7_VMEM_BYTES &&
                      n == FM1_DX7_VMEM_BYTES + 8;
    if (!vced && !vmem) {
      // A voice or bank dump's header (format 0 or 9) with another byte
      // count or length is a broken dump; anything else is not ours.
      ++r.skipped;
      if (yamaha && (m[3] == 0x00 || m[3] == 0x09)) ++r.wrong_size; else ++r.foreign;
      i = end + 1;
      continue;
    }
    unsigned sum = 0;
    for (unsigned k = 0; k < count; ++k) sum += m[6 + k];
    if (((0x80u - (sum & 0x7Fu)) & 0x7Fu) != m[6 + count]) ++r.bad_checksums;
    ++r.messages;
    if (vced) {
      FromVced(m + 6, voice);
      store(ctx, slot, voice);
      if (first) r.first_slot = static_cast<uint16_t>(slot);
      slot = (slot + 1) % FM1_DX7_USER_SLOTS;
      ++r.voices;
    } else {
      for (unsigned k = 0; k < FM1_DX7_USER_SLOTS; ++k) {
        FromPacked(m + 6 + k * kPackedBytes, voice);
        store(ctx, k, voice);
      }
      if (first) r.first_slot = 0;
      r.voices = static_cast<uint16_t>(r.voices + FM1_DX7_USER_SLOTS);
    }
    first = false;
    i = end + 1;
  }
  // A bank's data alone, as some collections keep it: exactly 4,096 bytes
  // with no SysEx framing at all.
  if (data && !framed && len == FM1_DX7_VMEM_BYTES) {
    for (unsigned k = 0; k < FM1_DX7_USER_SLOTS; ++k) {
      FromPacked(data + k * kPackedBytes, voice);
      store(ctx, k, voice);
    }
    r.first_slot = 0;
    r.voices = FM1_DX7_USER_SLOTS;
    r.raw = 1;
    r.outside = 0;
  }
  if (res) *res = r;
  return r.voices;
}

}  // namespace dx7
}  // namespace fm1

namespace {

// The checksum of a dump's data: it makes the data and itself sum to 0 in
// seven bits.
uint8_t Checksum(const uint8_t *data, size_t n) {
  unsigned sum = 0;
  for (size_t k = 0; k < n; ++k) sum += data[k];
  return static_cast<uint8_t>((0x80u - (sum & 0x7Fu)) & 0x7Fu);
}

// fm1_dx7_read_sysex's store, from ParseSysex's: msfa's voice is the VCED
// data in its order with the operator byte after it.
struct ReadCtx {
  fm1_dx7_store_fn store;
  void *ctx;
};

void ReadStore(void *ctx, unsigned slot, const uint8_t v[fm1::dx7::kVoiceBytes]) {
  const ReadCtx *c = static_cast<const ReadCtx *>(ctx);
  c->store(c->ctx, slot, v);
}

}  // namespace

extern "C" int fm1_dx7_read_sysex(const uint8_t *data, size_t len, unsigned slot,
                                  fm1_dx7_store_fn store, void *ctx, fm1_dx7_sysex_result_t *res) {
  if (!store) {
    if (res) memset(res, 0, sizeof(*res));
    return 0;
  }
  ReadCtx c = { store, ctx };
  return fm1::dx7::ParseSysex(data, len, slot, ReadStore, &c, res);
}

extern "C" void fm1_dx7_pack_voice(const uint8_t vced[FM1_DX7_VCED_BYTES],
                                   uint8_t packed[FM1_DX7_PACKED_BYTES]) {
  fm1::dx7::ToPacked(vced, packed);
}

extern "C" size_t fm1_dx7_write_voice(const uint8_t vced[FM1_DX7_VCED_BYTES], unsigned channel,
                                      uint8_t out[FM1_DX7_VOICE_SYSEX_BYTES]) {
  uint8_t v[fm1::dx7::kVoiceBytes];
  fm1::dx7::FromVced(vced, v);
  const uint8_t head[6] = { 0xF0, 0x43, static_cast<uint8_t>(channel & 0x0F), 0x00, 0x01, 0x1B };
  memcpy(out, head, sizeof(head));
  memcpy(out + 6, v, FM1_DX7_VCED_BYTES);
  out[6 + FM1_DX7_VCED_BYTES] = Checksum(out + 6, FM1_DX7_VCED_BYTES);
  out[7 + FM1_DX7_VCED_BYTES] = 0xF7;
  return FM1_DX7_VOICE_SYSEX_BYTES;
}

extern "C" size_t fm1_dx7_write_bank(const uint8_t *const voices[FM1_DX7_USER_SLOTS],
                                     unsigned channel, uint8_t out[FM1_DX7_BANK_SYSEX_BYTES]) {
  const uint8_t head[6] = { 0xF0, 0x43, static_cast<uint8_t>(channel & 0x0F), 0x09, 0x20, 0x00 };
  memcpy(out, head, sizeof(head));
  for (unsigned k = 0; k < FM1_DX7_USER_SLOTS; ++k) {
    const uint8_t *v = voices && voices[k] ? voices[k] : fm1::dx7::kInitVoice;
    fm1::dx7::ToPacked(v, out + 6 + k * FM1_DX7_PACKED_BYTES);
  }
  out[6 + FM1_DX7_VMEM_BYTES] = Checksum(out + 6, FM1_DX7_VMEM_BYTES);
  out[7 + FM1_DX7_VMEM_BYTES] = 0xF7;
  return FM1_DX7_BANK_SYSEX_BYTES;
}

// The names files and editors use for the VCED values (the DX7's own
// abbreviations); the ranges are the ones every load clamps to.
extern "C" const fm1_dx7_field_t fm1_dx7_op_fields[FM1_DX7_OP_FIELDS] = {
  { "R1", 99 }, { "R2", 99 }, { "R3", 99 }, { "R4", 99 },
  { "L1", 99 }, { "L2", 99 }, { "L3", 99 }, { "L4", 99 },
  { "BP", 99 }, { "LD", 99 }, { "RD", 99 }, { "LC", 3 }, { "RC", 3 },
  { "RS", 7 }, { "AMS", 3 }, { "KVS", 7 }, { "OL", 99 }, { "M", 1 },
  { "FC", 31 }, { "FF", 99 }, { "DET", 14 },
};

extern "C" const fm1_dx7_field_t fm1_dx7_voice_fields[FM1_DX7_VOICE_FIELDS] = {
  { "PR1", 99 }, { "PR2", 99 }, { "PR3", 99 }, { "PR4", 99 },
  { "PL1", 99 }, { "PL2", 99 }, { "PL3", 99 }, { "PL4", 99 },
  { "ALG", 31 }, { "FB", 7 }, { "OKS", 1 },
  { "LFS", 99 }, { "LFD", 99 }, { "LPMD", 99 }, { "LAMD", 99 },
  { "LKS", 1 }, { "LFW", 5 }, { "LPMS", 7 }, { "TRNSP", 48 },
};
