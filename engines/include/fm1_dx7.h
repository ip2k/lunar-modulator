/* fm1_dx7.h -- DX7 voice data for the FM6 engine (engine id "dx7",
 * engines/src/msfa_dx7.cc; engines/msfa.md).
 *
 * FM6 plays the 155-parameter voice of the six-operator FM keyboards of the
 * early 1980s, and reads that voice in the two SysEx dumps those keyboards
 * send: a single voice (VCED, 163 bytes: F0 43 0n 00 01 1B, 155 data bytes,
 * a checksum, F7) and a bank of 32 (VMEM, 4,104 bytes: F0 43 0n 09 20 00,
 * 4,096 data bytes, a checksum, F7). This is the engine-side import: a host
 * (fm1-render --sysex, the virtual FM-1's "Load DX7 patches") hands it the
 * bytes of a .syx file and it stores the voices in the instance's 32 user
 * slots, which the Patch parameter lists after the built-in bank as
 * "User 1".."User 32". A host that keeps a user bank of its own reads a file
 * with fm1_dx7_read_sysex, which needs no instance, and gives an instance
 * its voices with fm1_dx7_set_user_voice.
 *
 * And the way out (2026-10-06, notes/2026-10-06-state-files.md ST8): a
 * user slot's voice reads back with fm1_dx7_get_user_voice, and
 * fm1_dx7_pack_voice, fm1_dx7_write_voice and fm1_dx7_write_bank turn
 * voices into the same dumps, so a bank leaves as a .syx file the
 * keyboards and every editor read. fm1_dx7_op_fields and
 * fm1_dx7_voice_fields name the VCED values, for files and editors.
 *
 * Plain C99, our own code. MIT licence, like the rest of this repository.
 */
#ifndef FM1_DX7_H_
#define FM1_DX7_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_DX7_USER_SLOTS 32u     /* user slots in an instance */
#define FM1_DX7_VCED_BYTES 155u    /* a single voice's data */
#define FM1_DX7_VMEM_BYTES 4096u   /* a 32-voice bank's data, 128 per voice */
#define FM1_DX7_NAME_BYTES 10u

typedef struct fm1_dx7_sysex_result {
  uint16_t voices;          /* voices stored */
  uint16_t first_slot;      /* user slot (0-based) the first of them went to */
  uint16_t messages;        /* VCED and VMEM dumps found */
  uint16_t bad_checksums;   /* of those, how many had a wrong checksum
                               (stored all the same, as the keyboards'
                               editors do; many published files have one) */
  uint16_t skipped;         /* other SysEx messages, or broken ones, ignored:
                               foreign + truncated + wrong_size */
  uint16_t foreign;         /* of those, whole messages that are not a voice
                               or bank dump (another maker's, another format) */
  uint16_t truncated;       /* ...messages cut short: the file ends, or another
                               status byte comes, before their F7 */
  uint16_t wrong_size;      /* ...a voice or bank dump's header with a byte
                               count or a length that is not the format's */
  uint16_t raw;             /* 1: the file was a bank's 4,096 data bytes with
                               no SysEx framing */
  uint16_t reserved;        /* 0 */
  uint32_t outside;         /* bytes outside any SysEx message (0 for raw) */
} fm1_dx7_sysex_result_t;

/* Store the DX7 voices in data[0..len) in an FM6 instance's user slots:
 * every VCED and VMEM dump in it, in order (a .syx file may hold several),
 * or, for a file with no SysEx framing that is exactly 4,096 bytes, that
 * bank's raw data. A VMEM dump fills slots 0..31; a VCED dump fills slot
 * `slot` (0..31), the next one slot + 1, and so on, wrapping. Every value is
 * clamped to its range and the name to printable ASCII, so any bytes are
 * safe to load. Sounding notes keep the voice they started with; the next
 * note on a user slot plays what is stored now. Returns the number of
 * voices stored (also in res->voices when res is not NULL); 0 when nothing
 * was recognised, which leaves the slots as they were.
 * Thread: as set_param (the audio task, or with it stopped). */
int fm1_dx7_load_sysex(void *self, const uint8_t *data, size_t len, unsigned slot,
                       fm1_dx7_sysex_result_t *res);

/* The name stored in user slot `slot` (0..31), NUL-terminated into
 * out[11], trailing spaces trimmed; "" for a slot out of range. */
void fm1_dx7_user_name(const void *self, unsigned slot, char out[FM1_DX7_NAME_BYTES + 1]);

/* What fm1_dx7_read_sysex hands each voice to: its slot (0..31) and its 155
 * VCED data bytes, every value in range and the name printable. */
typedef void (*fm1_dx7_store_fn)(void *ctx, unsigned slot,
                                 const uint8_t vced[FM1_DX7_VCED_BYTES]);

/* Read the DX7 voices in data[0..len) as fm1_dx7_load_sysex does, slot for
 * slot, but into store(ctx, slot, vced) instead of an instance: for a host
 * that keeps a user bank of its own, or checks a file before it loads it.
 * Fills res when not NULL; returns the number of voices. No instance, no
 * allocation; any thread. */
int fm1_dx7_read_sysex(const uint8_t *data, size_t len, unsigned slot, fm1_dx7_store_fn store,
                       void *ctx, fm1_dx7_sysex_result_t *res);

/* Store one voice, its 155 VCED data bytes (clamped and cleaned as a dump's
 * are), in user slot `slot` (0..31) of an FM6 instance. Sounding notes keep
 * the voice they started with. 1, or 0 for a slot out of range.
 * Thread: as set_param. */
int fm1_dx7_set_user_voice(void *self, unsigned slot, const uint8_t vced[FM1_DX7_VCED_BYTES]);

/* User slot `slot`'s voice (0..31) as its 155 VCED data bytes, in range
 * and with the name printable: what fm1_dx7_set_user_voice stored, or the
 * INIT VOICE an untouched slot holds. 1, or 0 for a slot out of range (vced
 * untouched). Thread: as set_param. */
int fm1_dx7_get_user_voice(const void *self, unsigned slot, uint8_t vced[FM1_DX7_VCED_BYTES]);

#define FM1_DX7_PACKED_BYTES 128u        /* one voice in a VMEM bank */
#define FM1_DX7_VOICE_SYSEX_BYTES 163u   /* a VCED dump, F0 .. F7 */
#define FM1_DX7_BANK_SYSEX_BYTES 4104u   /* a VMEM dump, F0 .. F7 */

/* One voice's 155 VCED data bytes packed into a VMEM bank's 128 (the
 * inverse of the bank reader's unpacking): each value clamped to its range
 * and the name made printable first, as a load does, so packing a voice
 * and reading it back gives the same 155 bytes. */
void fm1_dx7_pack_voice(const uint8_t vced[FM1_DX7_VCED_BYTES], uint8_t packed[FM1_DX7_PACKED_BYTES]);

/* A single-voice dump: F0 43 0n 00 01 1B, the 155 bytes (clamped and
 * cleaned as above), the checksum, F7, with n the MIDI channel (0..15;
 * others wrap). Writes FM1_DX7_VOICE_SYSEX_BYTES and returns that. */
size_t fm1_dx7_write_voice(const uint8_t vced[FM1_DX7_VCED_BYTES], unsigned channel,
                           uint8_t out[FM1_DX7_VOICE_SYSEX_BYTES]);

/* A 32-voice bank dump: F0 43 0n 09 20 00, voices[0..31] packed, the
 * checksum, F7. A NULL voice is the INIT VOICE. Writes
 * FM1_DX7_BANK_SYSEX_BYTES and returns that. fm1_dx7_read_sysex of the
 * result gives the 32 voices back, byte for byte. */
size_t fm1_dx7_write_bank(const uint8_t *const voices[FM1_DX7_USER_SLOTS], unsigned channel,
                          uint8_t out[FM1_DX7_BANK_SYSEX_BYTES]);

/* The VCED values by name, for files and editors: an operator's 21 (R1 ..
 * DET, in the order each of a voice's six operators keeps them, OP6
 * first) and the voice's 19 between the operators and the name (PR1 ..
 * TRNSP), each with its largest value (the smallest is 0). */
typedef struct fm1_dx7_field {
  const char *name;
  uint8_t max;
} fm1_dx7_field_t;
#define FM1_DX7_OP_FIELDS 21u
#define FM1_DX7_VOICE_FIELDS 19u
extern const fm1_dx7_field_t fm1_dx7_op_fields[FM1_DX7_OP_FIELDS];
extern const fm1_dx7_field_t fm1_dx7_voice_fields[FM1_DX7_VOICE_FIELDS];

#ifdef __cplusplus
}
#endif

#endif /* FM1_DX7_H_ */
