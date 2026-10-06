/* fm1_dx7.h -- DX7 voice data for the FM6 engine (engine id "dx7",
 * engines/src/msfa_dx7.cc; engines/msfa.md).
 *
 * FM6 plays the 155-parameter voice of the six-operator FM keyboards of the
 * early 1980s, and reads that voice in the two SysEx dumps those keyboards
 * send: a single voice (VCED, 163 bytes: F0 43 0n 00 01 1B, 155 data bytes,
 * a checksum, F7) and a bank of 32 (VMEM, 4,104 bytes: F0 43 0n 09 20 00,
 * 4,096 data bytes, a checksum, F7). This is the engine-side import: a host
 * (fm1-render --sysex today, the virtual FM-1 later) hands it the bytes of a
 * .syx file and it stores the voices in the instance's 32 user slots, which
 * the Patch parameter lists after the built-in bank as "User 1".."User 32".
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
  uint16_t skipped;         /* other SysEx messages, or broken ones, ignored */
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

#ifdef __cplusplus
}
#endif

#endif /* FM1_DX7_H_ */
