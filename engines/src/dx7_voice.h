// dx7_voice.h -- DX7 voice data for the FM6 engine (src/msfa_dx7.cc): the
// voice as msfa plays it, reading it from a bank or a SysEx dump, and
// keeping every value in its range.
//
// A voice here is msfa's 156-byte layout (msfa's patch.cc and dx7note.cc):
// the 155 parameters of a VCED single-voice dump, in its order (the sixth
// operator's 21 first, the first operator's last, then the pitch envelope,
// algorithm, feedback, LFO, transpose and the 10-character name), and the
// operator on/off byte msfa's UnpackPatch adds, always 0x3F here.
//
// Our own code; msfa's UnpackPatch (third_party/msfa/patch.cc, Apache-2.0)
// does the unpacking. MIT licence (this file).

#ifndef FM1_DX7_VOICE_H_
#define FM1_DX7_VOICE_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_dx7.h"

namespace fm1 {
namespace dx7 {

const int kVoiceBytes = 156;          // msfa's unpacked voice
const int kPackedBytes = 128;         // a voice in a VMEM bank
const int kOpBytes = 21;              // one operator, the sixth first

// Offsets in an operator's 21 bytes and in the voice (VCED order).
enum {
  OP_R1 = 0, OP_L1 = 4, OP_BP = 8, OP_LD = 9, OP_RD = 10, OP_LC = 11, OP_RC = 12,
  OP_RS = 13, OP_AMS = 14, OP_KVS = 15, OP_OL = 16, OP_MODE = 17, OP_FC = 18,
  OP_FF = 19, OP_DET = 20,
  V_PR1 = 126, V_PL1 = 130, V_ALG = 134, V_FB = 135, V_OKS = 136, V_LFS = 137,
  V_LFD = 138, V_LPMD = 139, V_LAMD = 140, V_LKS = 141, V_LFW = 142, V_LPMS = 143,
  V_TRNSP = 144, V_NAME = 145, V_OPSW = 155
};

// The keyboards' "INIT VOICE": algorithm 1, the first operator alone at
// output level 99, ratio 1, an organ envelope; what an empty user slot holds.
extern const uint8_t kInitVoice[kVoiceBytes];

// Clamp every parameter of v to its range, the name to printable ASCII
// (anything else becomes a space) and the operator byte to 0x3F.
void Sanitize(uint8_t v[kVoiceBytes]);

// One voice from a VMEM bank's 128 packed bytes (msfa's UnpackPatch), then
// sanitised.
void FromPacked(const uint8_t packed[kPackedBytes], uint8_t v[kVoiceBytes]);

// One voice's VCED data bytes, sanitised, packed into a VMEM bank's 128:
// FromPacked's inverse for every voice in range.
void ToPacked(const uint8_t vced[FM1_DX7_VCED_BYTES], uint8_t packed[kPackedBytes]);

// One voice from a VCED dump's 155 data bytes, sanitised.
void FromVced(const uint8_t data[FM1_DX7_VCED_BYTES], uint8_t v[kVoiceBytes]);

// Calls store(ctx, slot, voice) for every voice in a SysEx file (fm1_dx7.h,
// fm1_dx7_load_sysex) and fills res; returns the number of voices.
typedef void (*StoreFn)(void *ctx, unsigned slot, const uint8_t v[kVoiceBytes]);
int ParseSysex(const uint8_t *data, size_t len, unsigned slot, StoreFn store, void *ctx,
               fm1_dx7_sysex_result_t *res);

// The name of voice v, trailing spaces trimmed, NUL-terminated in out[11].
void Name(const uint8_t v[kVoiceBytes], char out[FM1_DX7_NAME_BYTES + 1]);

}  // namespace dx7
}  // namespace fm1

#endif  // FM1_DX7_VOICE_H_
