/* fm1_num.h -- exact numbers for the state files (notes/2026-10-06-state-
 * files.md §7.2, §7.3): decimal text to float32 and back, Q1.14 amounts as
 * percent, and integers, all exact and all ours, so native builds, the
 * WebAssembly module and the device agree bit for bit (libc's strtod and
 * printf are not used).
 *
 *   decimal -> float32   the exact decimal, rounded to the nearest float32,
 *                        ties to even. A fast path (at most 7 digits and a
 *                        power of ten a float32 holds exactly: one correctly
 *                        rounded division or multiplication) and an exact
 *                        path (a candidate, then compared with the midpoints
 *                        to its neighbours in big integers).
 *   float32 -> decimal   the shortest decimal (at most 9 significant digits)
 *                        that reads back to the same bits, chosen with the
 *                        exact reader above, formatted as ECMAScript's
 *                        Number::toString formats it (0.41, 420, 5e-7); -0 is 0.
 *   percent <-> Q1.14    q = round(percent x 16384 / 100), ties away from
 *                        zero, exact on the decimal after clamping to
 *                        +-100; the writer's percent is the shortest (at
 *                        most 3 decimals) that maps back.
 *
 * Input is JSON number text (fm1_json.h has checked its grammar), at most
 * FM1_NUM_MAX characters. C99, no heap, no libm. MIT licence.
 */
#ifndef FM1_NUM_H_
#define FM1_NUM_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_NUM_MAX 32u

enum {
  FM1_NUM_OK = 0,
  FM1_NUM_SYNTAX,             /* not a JSON number */
  FM1_NUM_RANGE,              /* beyond a float32, or beyond the integer's range */
  FM1_NUM_NOT_INT,            /* a fraction or an exponent where an integer belongs */
  FM1_NUM_CLAMPED             /* Q1.14: beyond +-100 %, clamped (still written) */
};

/* JSON number text to the nearest float32 (ties to even). "-0" gives -0.0f.
 * FM1_NUM_RANGE when it rounds beyond FLT_MAX. */
int fm1_num_f32(const char *s, size_t n, float *out);
/* The same, through the exact path only (tests compare the two). */
int fm1_num_f32_exact(const char *s, size_t n, float *out);

/* JSON number text that must be an integer (no '.', no exponent) within
 * [lo, hi]: FM1_NUM_NOT_INT, or FM1_NUM_RANGE outside. */
int fm1_num_int(const char *s, size_t n, int64_t lo, int64_t hi, int64_t *out);

/* Percent text to Q1.14 (-16384..16384). FM1_NUM_CLAMPED when the value
 * was beyond +-100 (out is then +-16384). */
int fm1_num_q14(const char *s, size_t n, int16_t *out);

/* The canonical text of float32 bits (NaN and infinities give 0: a writer
 * never has them). Writes at most 16 characters and a NUL; returns the
 * length. */
size_t fm1_num_f32_text(uint32_t bits, char out[24]);

/* The canonical percent of a Q1.14 value (clamped to +-16384): at most 3
 * decimals, the shortest that maps back. Returns the length. */
size_t fm1_num_q14_text(int q, char out[16]);

/* Float bits, by value: no type punning through pointers. */
uint32_t fm1_num_bits(float f);
float fm1_num_float(uint32_t bits);

#ifdef __cplusplus
}
#endif

#endif /* FM1_NUM_H_ */
