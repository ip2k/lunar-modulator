/* fm1_json.c -- the streaming JSON tokenizer (fm1_json.h). C99, no heap, no
 * recursion, no stdio. MIT licence. */
#include "fm1_json.h"

#include <string.h>

#define DEPTH_MAX 8u
#define KEY_MAX 64u
#define NUM_MAX 32u
#define STR_MAX 16384u
#define MEMBERS_MAX 64u
#define ITEMS_MAX 8192u
/* A piece is given out once it holds this much (a code point is <= 4 bytes). */
#define PIECE_FLUSH 60u

/* Lexer states. */
enum {
  S_WS = 0,       /* between tokens */
  S_STR,          /* in a string */
  S_ESC,          /* after a backslash */
  S_HEX,          /* in \uXXXX */
  S_HEXLOW_BS,    /* after a high surrogate: expecting '\' */
  S_HEXLOW_U,     /* ...then 'u' */
  S_NUM,          /* in a number */
  S_LIT,          /* in true, false or null */
  S_END           /* after the top value: white space only */
};

/* What the grammar wants. */
enum {
  E_VALUE = 0,    /* a value (top, after ':' or after ',' in an array) */
  E_VALUE_OR_END, /* after '[' : a value or ']' */
  E_KEY,          /* after ',' in an object: a key */
  E_KEY_OR_END,   /* after '{' : a key or '}' */
  E_COLON,        /* after a key */
  E_COMMA_OR_END  /* after a value inside a container */
};

/* Number grammar states. */
enum {
  N_SIGN = 0,     /* after '-' */
  N_ZERO,         /* a leading 0 */
  N_INT,          /* integer digits */
  N_DOT,          /* after '.' */
  N_FRAC,         /* fraction digits */
  N_E,            /* after e/E */
  N_ESIGN,        /* after e+ or e- */
  N_EXP           /* exponent digits */
};

static const char *const kLit[3] = { "true", "false", "null" };

static int fail(fm1_json_t *p, unsigned err) {
  if (!p->err) p->err = (uint8_t)err;
  return 0;
}

static int emit(fm1_json_t *p, uint8_t type, const char *s, uint32_t n, uint8_t first, uint8_t last) {
  fm1_json_ev_t ev;
  ev.type = type;
  ev.first = first;
  ev.last = last;
  ev.depth = p->depth;
  ev.n = n;
  ev.s = s;
  if (!p->cb(p->ctx, &ev)) return fail(p, FM1_JSON_ESTOP);
  return 1;
}

void fm1_json_init(fm1_json_t *p, fm1_json_cb_t cb, void *ctx) {
  memset(p, 0, sizeof(*p));
  p->cb = cb;
  p->ctx = ctx;
  p->line = 1;
  p->col = 1;
  p->state = S_WS;
  p->expect = E_VALUE;
}

const char *fm1_json_error(unsigned err) {
  switch (err) {
    case FM1_JSON_OK: return "ok";
    case FM1_JSON_ESYNTAX: return "syntax";
    case FM1_JSON_EUTF8: return "utf-8";
    case FM1_JSON_EBIG: return "too big";
    case FM1_JSON_ESTOP: return "stopped";
    default: return "?";
  }
}

/* A value completed (a scalar, or a container closed): what comes next. */
static void value_done(fm1_json_t *p) {
  if (p->depth == 0) {
    p->done = 1;
    p->state = S_END;
  } else {
    p->expect = E_COMMA_OR_END;
  }
}

/* A value starts here: count it in its container. */
static int value_start(fm1_json_t *p) {
  if (p->expect != E_VALUE && p->expect != E_VALUE_OR_END) return fail(p, FM1_JSON_ESYNTAX);
  if (p->depth > 0 && !((p->stack >> (p->depth - 1u)) & 1u)) {
    if (++p->count[p->depth - 1u] > ITEMS_MAX) return fail(p, FM1_JSON_EBIG);
  }
  return 1;
}

static int open_container(fm1_json_t *p, int object) {
  if (!value_start(p)) return 0;
  if (p->depth >= DEPTH_MAX) return fail(p, FM1_JSON_EBIG);
  if (!emit(p, object ? FM1_JSON_OBJ : FM1_JSON_ARR, NULL, 0, 0, 0)) return 0;
  if (object) p->stack = (uint8_t)(p->stack | (1u << p->depth));
  else p->stack = (uint8_t)(p->stack & ~(1u << p->depth));
  p->count[p->depth] = 0;
  ++p->depth;
  p->expect = object ? E_KEY_OR_END : E_VALUE_OR_END;
  return 1;
}

static int close_container(fm1_json_t *p, int object) {
  const int top_is_obj = p->depth > 0 && ((p->stack >> (p->depth - 1u)) & 1u);
  if (p->depth == 0 || top_is_obj != object) return fail(p, FM1_JSON_ESYNTAX);
  if (object ? !(p->expect == E_KEY_OR_END || p->expect == E_COMMA_OR_END)
             : !(p->expect == E_VALUE_OR_END || p->expect == E_COMMA_OR_END)) {
    return fail(p, FM1_JSON_ESYNTAX);
  }
  --p->depth;
  if (!emit(p, object ? FM1_JSON_OBJ_END : FM1_JSON_ARR_END, NULL, 0, 0, 0)) return 0;
  value_done(p);
  return 1;
}

/* The string piece so far goes out (a value's), or stays (a key's). */
static int flush_piece(fm1_json_t *p, int last) {
  if (p->is_key) {
    if (!last) return 1;
    if (!emit(p, FM1_JSON_KEY, p->buf, p->bufn, 1, 1)) return 0;
    p->bufn = 0;
    return 1;
  }
  if (!emit(p, FM1_JSON_STR, p->buf, p->bufn, p->slen == p->bufn, (uint8_t)last)) return 0;
  p->bufn = 0;
  return 1;
}

/* Appends code point cp, UTF-8 encoded, to the string. */
static int put_cp(fm1_json_t *p, uint32_t cp) {
  uint8_t b[4];
  unsigned n, i;
  if (cp == 0) return fail(p, FM1_JSON_EUTF8);
  if (cp < 0x80u) {
    b[0] = (uint8_t)cp; n = 1;
  } else if (cp < 0x800u) {
    b[0] = (uint8_t)(0xC0u | (cp >> 6)); b[1] = (uint8_t)(0x80u | (cp & 0x3Fu)); n = 2;
  } else if (cp < 0x10000u) {
    b[0] = (uint8_t)(0xE0u | (cp >> 12)); b[1] = (uint8_t)(0x80u | ((cp >> 6) & 0x3Fu));
    b[2] = (uint8_t)(0x80u | (cp & 0x3Fu)); n = 3;
  } else {
    b[0] = (uint8_t)(0xF0u | (cp >> 18)); b[1] = (uint8_t)(0x80u | ((cp >> 12) & 0x3Fu));
    b[2] = (uint8_t)(0x80u | ((cp >> 6) & 0x3Fu)); b[3] = (uint8_t)(0x80u | (cp & 0x3Fu)); n = 4;
  }
  if (p->is_key) {
    if (p->bufn + n > KEY_MAX) return fail(p, FM1_JSON_EBIG);
  } else {
    if (p->slen + n > STR_MAX) return fail(p, FM1_JSON_EBIG);
  }
  for (i = 0; i < n; ++i) p->buf[p->bufn++] = (char)b[i];
  p->slen += n;
  if (!p->is_key && p->bufn >= PIECE_FLUSH) return flush_piece(p, 0);
  return 1;
}

static int hexval(uint8_t c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

/* A \u escape's 16 bits are in: a BMP code point, or one half of a pair. */
static int hex_done(fm1_json_t *p) {
  const uint16_t u = p->hex;
  if (p->hi) {
    const uint16_t hi = p->hi;
    p->hi = 0;
    if (u < 0xDC00u || u > 0xDFFFu) return fail(p, FM1_JSON_EUTF8);
    p->state = S_STR;
    return put_cp(p, 0x10000u + (((uint32_t)hi - 0xD800u) << 10) + ((uint32_t)u - 0xDC00u));
  }
  if (u >= 0xD800u && u <= 0xDBFFu) {
    p->hi = u;
    p->state = S_HEXLOW_BS;
    return 1;
  }
  if (u >= 0xDC00u && u <= 0xDFFFu) return fail(p, FM1_JSON_EUTF8);
  p->state = S_STR;
  return put_cp(p, u);
}

static int num_char(fm1_json_t *p, uint8_t c) {
  const int digit = c >= '0' && c <= '9';
  switch (p->numstate) {
    case N_SIGN:
      if (c == '0') p->numstate = N_ZERO;
      else if (digit) p->numstate = N_INT;
      else return -1;
      break;
    case N_ZERO:
      if (c == '.') p->numstate = N_DOT;
      else if (c == 'e' || c == 'E') p->numstate = N_E;
      else return 0;
      break;
    case N_INT:
      if (digit) break;
      if (c == '.') p->numstate = N_DOT;
      else if (c == 'e' || c == 'E') p->numstate = N_E;
      else return 0;
      break;
    case N_DOT:
      if (!digit) return -1;
      p->numstate = N_FRAC;
      break;
    case N_FRAC:
      if (digit) break;
      if (c == 'e' || c == 'E') p->numstate = N_E;
      else return 0;
      break;
    case N_E:
      if (c == '+' || c == '-') p->numstate = N_ESIGN;
      else if (digit) p->numstate = N_EXP;
      else return -1;
      break;
    case N_ESIGN:
      if (!digit) return -1;
      p->numstate = N_EXP;
      break;
    case N_EXP:
      if (!digit) return 0;
      break;
    default:
      return -1;
  }
  return 1;
}

/* The number ends (before c, or at the input's end). */
static int num_end(fm1_json_t *p) {
  if (p->numstate == N_SIGN || p->numstate == N_DOT || p->numstate == N_E || p->numstate == N_ESIGN) {
    return fail(p, FM1_JSON_ESYNTAX);
  }
  p->state = p->depth ? S_WS : S_END;
  if (!emit(p, FM1_JSON_NUM, p->num, p->numn, 1, 1)) return 0;
  value_done(p);
  return 1;
}

static int is_ws(uint8_t c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r'; }

/* One byte between tokens. */
static int ws_byte(fm1_json_t *p, uint8_t c) {
  if (is_ws(c)) return 1;
  if (p->state == S_END) return fail(p, FM1_JSON_ESYNTAX);
  switch (c) {
    case '{': return open_container(p, 1);
    case '[': return open_container(p, 0);
    case '}': return close_container(p, 1);
    case ']': return close_container(p, 0);
    case ':':
      if (p->expect != E_COLON) return fail(p, FM1_JSON_ESYNTAX);
      p->expect = E_VALUE;
      return 1;
    case ',':
      if (p->expect != E_COMMA_OR_END || p->depth == 0) return fail(p, FM1_JSON_ESYNTAX);
      p->expect = ((p->stack >> (p->depth - 1u)) & 1u) ? E_KEY : E_VALUE;
      return 1;
    case '"':
      if (p->expect == E_KEY || p->expect == E_KEY_OR_END) {
        if (++p->count[p->depth - 1u] > MEMBERS_MAX) return fail(p, FM1_JSON_EBIG);
        p->is_key = 1;
      } else {
        if (!value_start(p)) return 0;
        p->is_key = 0;
      }
      p->state = S_STR;
      p->bufn = 0;
      p->slen = 0;
      p->need = 0;
      return 1;
    case 't': case 'f': case 'n':
      if (!value_start(p)) return 0;
      p->lit = c == 't' ? 0 : (c == 'f' ? 1 : 2);
      p->litpos = 1;
      p->state = S_LIT;
      return 1;
    default:
      if (c == '-' || (c >= '0' && c <= '9')) {
        if (!value_start(p)) return 0;
        p->numn = 0;
        p->num[p->numn++] = (char)c;
        p->numstate = c == '-' ? N_SIGN : (c == '0' ? N_ZERO : N_INT);
        p->state = S_NUM;
        return 1;
      }
      return fail(p, FM1_JSON_ESYNTAX);
  }
}

/* One byte inside a string (not an escape). */
static int str_byte(fm1_json_t *p, uint8_t c) {
  if (p->need) {
    if ((c & 0xC0u) != 0x80u) return fail(p, FM1_JSON_EUTF8);
    p->cp = (p->cp << 6) | (c & 0x3Fu);
    if (--p->need) return 1;
    /* Overlong, surrogate or out of range? */
    if ((p->len == 2 && p->cp < 0x80u) || (p->len == 3 && p->cp < 0x800u) ||
        (p->len == 4 && (p->cp < 0x10000u || p->cp > 0x10FFFFu)) ||
        (p->cp >= 0xD800u && p->cp <= 0xDFFFu)) {
      return fail(p, FM1_JSON_EUTF8);
    }
    return put_cp(p, p->cp);
  }
  if (c == '"') {
    p->state = p->depth ? S_WS : S_END;
    if (p->is_key) {
      if (!flush_piece(p, 1)) return 0;
      p->expect = E_COLON;
      return 1;
    }
    if (!flush_piece(p, 1)) return 0;
    value_done(p);
    return 1;
  }
  if (c == '\\') {
    p->state = S_ESC;
    return 1;
  }
  if (c < 0x20u) return fail(p, c == 0 ? FM1_JSON_EUTF8 : FM1_JSON_ESYNTAX);
  if (c < 0x80u) return put_cp(p, c);
  if ((c & 0xE0u) == 0xC0u) { p->cp = c & 0x1Fu; p->need = 1; p->len = 2; return 1; }
  if ((c & 0xF0u) == 0xE0u) { p->cp = c & 0x0Fu; p->need = 2; p->len = 3; return 1; }
  if ((c & 0xF8u) == 0xF0u) { p->cp = c & 0x07u; p->need = 3; p->len = 4; return 1; }
  return fail(p, FM1_JSON_EUTF8);
}

static int esc_byte(fm1_json_t *p, uint8_t c) {
  uint32_t cp;
  switch (c) {
    case '"': cp = '"'; break;
    case '\\': cp = '\\'; break;
    case '/': cp = '/'; break;
    case 'b': cp = 8; break;
    case 'f': cp = 12; break;
    case 'n': cp = 10; break;
    case 'r': cp = 13; break;
    case 't': cp = 9; break;
    case 'u':
      p->state = S_HEX;
      p->hex = 0;
      p->hexn = 0;
      return 1;
    default:
      return fail(p, FM1_JSON_ESYNTAX);
  }
  p->state = S_STR;
  return put_cp(p, cp);
}

static int byte(fm1_json_t *p, uint8_t c) {
  int r, h;
  switch (p->state) {
    case S_WS:
    case S_END:
      return ws_byte(p, c);
    case S_STR:
      return str_byte(p, c);
    case S_ESC:
      return esc_byte(p, c);
    case S_HEX:
      h = hexval(c);
      if (h < 0) return fail(p, FM1_JSON_ESYNTAX);
      p->hex = (uint16_t)((p->hex << 4) | (unsigned)h);
      if (++p->hexn < 4) return 1;
      return hex_done(p);
    case S_HEXLOW_BS:
      if (c != '\\') return fail(p, FM1_JSON_EUTF8);
      p->state = S_HEXLOW_U;
      return 1;
    case S_HEXLOW_U:
      if (c != 'u') return fail(p, FM1_JSON_EUTF8);
      p->state = S_HEX;
      p->hex = 0;
      p->hexn = 0;
      return 1;
    case S_NUM:
      r = num_char(p, c);
      if (r < 0) return fail(p, FM1_JSON_ESYNTAX);
      if (r > 0) {
        if (p->numn >= NUM_MAX) return fail(p, FM1_JSON_EBIG);
        p->num[p->numn++] = (char)c;
        return 1;
      }
      if (!num_end(p)) return 0;
      return ws_byte(p, c);
    case S_LIT:
      if (c != (uint8_t)kLit[p->lit][p->litpos]) return fail(p, FM1_JSON_ESYNTAX);
      if (kLit[p->lit][++p->litpos] == '\0') {
        p->state = p->depth ? S_WS : S_END;
        if (!emit(p, p->lit == 0 ? FM1_JSON_TRUE : (p->lit == 1 ? FM1_JSON_FALSE : FM1_JSON_NULL),
                  NULL, 0, 0, 0)) {
          return 0;
        }
        value_done(p);
      }
      return 1;
    default:
      return fail(p, FM1_JSON_ESYNTAX);
  }
}

int fm1_json_feed(fm1_json_t *p, const uint8_t *b, size_t n) {
  size_t i;
  if (p->err) return 0;
  for (i = 0; i < n; ++i) {
    const uint8_t c = b[i];
    if (!p->started) {
      p->started = 1;
      if (c == 0xEFu) return fail(p, FM1_JSON_EUTF8);   /* a byte-order mark */
    }
    if (!byte(p, c)) return 0;
    ++p->offset;
    if (c == '\n') {
      ++p->line;
      p->col = 1;
    } else if ((c & 0xC0u) != 0x80u) {
      ++p->col;                       /* columns count code points */
    }
  }
  return 1;
}

int fm1_json_end(fm1_json_t *p) {
  if (p->err) return 0;
  if (p->state == S_NUM && p->depth == 0) {
    if (!num_end(p)) return 0;
  }
  if (!p->done || p->state != S_END) return fail(p, FM1_JSON_ESYNTAX);
  return 1;
}
