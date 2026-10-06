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

#ifdef __cplusplus
}
#endif

#endif /* FM1_DX7_H_ */
