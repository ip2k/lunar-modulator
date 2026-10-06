/* fm1_json.h -- a streaming JSON tokenizer for the firmware and the tools
 * (notes/2026-10-06-state-files.md §7.6, §16).
 *
 * RFC 8259 JSON, fed in pieces of any size (a SysEx page, a flash read, the
 * whole buffer); events go to a callback as they complete. Its state is
 * this struct, under 256 bytes whatever the input's size: no malloc, no
 * recursion. Strings go out in pieces of at most 64 decoded bytes, each
 * ending on a code point boundary, so a 16 KiB movy1 line needs no 16 KiB
 * buffer; a key goes out whole (at most 64 bytes). A number goes out as its
 * text (at most 32 characters); fm1_num.h reads it exactly.
 *
 * Refused (fm1_json_t.err): anything RFC 8259 does not allow, a byte-order
 * mark, UTF-8 that is overlong, a surrogate half (raw or as a lone \u
 * escape), past U+10FFFF or U+0000 (raw or \u0000), and the caps:
 * depth 8, keys 64 bytes, numbers 32 characters, strings 16,384 bytes,
 * 64 members an object, 8,192 items an array. Duplicate keys are the
 * record builder's to refuse (state_json_read.c): a tokenizer that kept
 * every key could not stay this small.
 *
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_JSON_H_
#define FM1_JSON_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  FM1_JSON_OBJ = 1,           /* { */
  FM1_JSON_OBJ_END,           /* } */
  FM1_JSON_ARR,               /* [ */
  FM1_JSON_ARR_END,           /* ] */
  FM1_JSON_KEY,               /* a member's name, whole */
  FM1_JSON_STR,               /* a piece of a string value (first, last flags) */
  FM1_JSON_NUM,               /* a number's text, whole */
  FM1_JSON_TRUE,
  FM1_JSON_FALSE,
  FM1_JSON_NULL
};

/* Errors. */
enum {
  FM1_JSON_OK = 0,
  FM1_JSON_ESYNTAX,           /* not JSON */
  FM1_JSON_EUTF8,             /* bad UTF-8, a surrogate half, U+0000, a BOM */
  FM1_JSON_EBIG,              /* a cap */
  FM1_JSON_ESTOP              /* the callback stopped */
};

typedef struct fm1_json_ev {
  uint8_t type;               /* FM1_JSON_* */
  uint8_t first, last;        /* FM1_JSON_STR: the string's first and last piece */
  uint8_t depth;              /* containers open around this token (the top value: 0) */
  uint32_t n;                 /* bytes at s */
  const char *s;              /* KEY, STR, NUM: the text (not NUL-terminated) */
} fm1_json_ev_t;

/* Returns 1 to go on, 0 to stop. */
typedef int (*fm1_json_cb_t)(void *ctx, const fm1_json_ev_t *ev);

typedef struct fm1_json {
  fm1_json_cb_t cb;
  void *ctx;
  uint32_t line, col;         /* of the next byte, 1-based */
  uint32_t offset;            /* bytes consumed */
  uint32_t slen;              /* decoded bytes of the current string */
  uint32_t cp;                /* UTF-8: the code point being decoded */
  uint16_t count[8];          /* members or items of each open container */
  uint16_t hi;                /* a pending high surrogate from \u */
  uint16_t hex;               /* \u digits so far */
  uint8_t state;              /* the lexer's state */
  uint8_t depth;              /* open containers, 0-8 */
  uint8_t stack;              /* bit d: container d is an object */
  uint8_t expect;             /* what the grammar wants next */
  uint8_t need;               /* UTF-8 continuation bytes still to come */
  uint8_t len;                /* UTF-8: the sequence's length */
  uint8_t hexn;               /* \u digits read */
  uint8_t lit;                /* a literal: 0 true, 1 false, 2 null */
  uint8_t litpos;
  uint8_t err;                /* FM1_JSON_* error, sticky */
  uint8_t is_key;             /* the string being read is a key */
  uint8_t bufn;               /* bytes in buf */
  uint8_t numn;               /* characters in num */
  uint8_t numstate;           /* the number grammar's state */
  uint8_t done;               /* the top value is complete */
  uint8_t started;            /* a byte has been seen (the BOM check) */
  char buf[64];               /* a key, or a string piece */
  char num[32];               /* a number's text */
} fm1_json_t;

void fm1_json_init(fm1_json_t *p, fm1_json_cb_t cb, void *ctx);
/* Feeds n bytes. Returns 1, or 0 once an error or a stop happened (sticky:
 * p->err says which, p->line and p->col where). */
int fm1_json_feed(fm1_json_t *p, const uint8_t *b, size_t n);
/* The input ended: completes a top-level number, and fails unless one whole
 * value was read. */
int fm1_json_end(fm1_json_t *p);
/* "syntax", "utf-8", "too big", "stopped". */
const char *fm1_json_error(unsigned err);

#ifdef __cplusplus
}
#endif

#endif /* FM1_JSON_H_ */
