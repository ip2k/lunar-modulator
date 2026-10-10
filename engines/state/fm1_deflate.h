/* fm1_deflate.h -- raw deflate (RFC 1951) for the binary container's
 * DEFLATED chunks (notes/2026-10-06-state-files.md §8.2), our own so the
 * firmware needs no zlib and every build writes the same bytes.
 *
 * Inflate pulls: it reads compressed bytes through a source callback and
 * gives out as many bytes as asked, keeping a 4 KiB window, its Huffman
 * tables and a 64-byte input buffer (about 5.5 KiB, transient while a chunk
 * is read). It refuses a back-reference past 4,096 bytes (the container's
 * window), past the bytes it has given, or output past the declared length.
 *
 * Deflate (desktop and simulator): greedy LZ77 over a 4,096-byte window
 * (hash chains of at most 128 steps) into one fixed-Huffman block. It is
 * deterministic, so a binary file is the same bytes from every build, and
 * tools/lunar_state.py does the same; any inflater (zlib's included) reads
 * it. C99, no heap, no libm. MIT licence. */
#ifndef FM1_DEFLATE_H_
#define FM1_DEFLATE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_DEFLATE_WINDOW 4096u

typedef uint32_t (*fm1_inflate_src_t)(void *ctx, uint32_t off, uint8_t *buf, uint32_t n);

typedef struct fm1_inflate {
  fm1_inflate_src_t rd;
  void *ctx;
  uint32_t in_off, in_end;     /* compressed bytes still to read: [in_off, in_end) */
  uint32_t in_pos, in_len;
  uint32_t bitbuf, bitcnt;
  uint32_t out_total, out_cap;
  uint32_t stored_left;
  uint32_t match_len, match_dist;
  uint8_t state, final, err, pad_;
  uint16_t lcount[16], lsym[288];
  uint16_t dcount[16], dsym[32];
  uint8_t inbuf[64];
  uint8_t window[FM1_DEFLATE_WINDOW];
} fm1_inflate_t;

/* Starts inflating the bytes [off, off + len) of a source, whose output is
 * exactly `out_len` bytes. */
void fm1_inflate_init(fm1_inflate_t *z, fm1_inflate_src_t rd, void *ctx, uint32_t off, uint32_t len,
                      uint32_t out_len);
/* Up to n bytes into out; returns how many (fewer only at the end). z->err
 * is set on a malformed stream, and fm1_inflate_done says whether every
 * byte came out with the stream's final block ended and no trailing bytes. */
uint32_t fm1_inflate_read(fm1_inflate_t *z, uint8_t *out, uint32_t n);
int fm1_inflate_done(const fm1_inflate_t *z);

/* Scratch the compressor needs (aligned to 4). */
#define FM1_DEFLATE_SCRATCH (4u * (4096u + 4096u))
/* Compresses in[0..n) into out (cap bytes); returns the length, or 0 when it
 * does not fit. */
size_t fm1_deflate(const uint8_t *in, size_t n, uint8_t *out, size_t cap, void *scratch);

#ifdef __cplusplus
}
#endif

#endif /* FM1_DEFLATE_H_ */
