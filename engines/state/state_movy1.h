/* state_movy1.h -- movy1 lines as binary items (state_movy1.c). MIT licence. */
#ifndef STATE_MOVY1_H_
#define STATE_MOVY1_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_MOVY1_LINE_MAX 16384u

/* Encodes one line (without its LF) as an item into out; returns its
 * length, or 0 when it does not fit cap (or the line is past 65,535 B). */
size_t fm1_movy1_encode(const char *line, size_t n, uint8_t *out, size_t cap);

/* A line's text in pieces (at most 64 bytes each). Returns 1 to go on. */
typedef int (*fm1_movy1_text_fn)(void *ctx, const char *s, size_t n, int first, int last);

/* The next byte of the items, pulled: 1, or 0 at their end. */
typedef int (*fm1_movy1_pull_t)(void *ctx, uint8_t *b);

/* Decodes one item, pulling its bytes; its text goes to fn in pieces of at
 * most 64 bytes, so no line is ever held whole. 1, 0 for a malformed or
 * cut item (or a line past 16 KiB), -1 when fn stopped. */
int fm1_movy1_decode(fm1_movy1_pull_t get, void *gctx, fm1_movy1_text_fn fn, void *ctx);

#ifdef __cplusplus
}
#endif

#endif /* STATE_MOVY1_H_ */
