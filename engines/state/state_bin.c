/* state_bin.c -- the binary container, for the device (fm1_state.h;
 * notes/2026-10-06-state-files.md §8).
 *
 *   header   32 B: magic 89 4C 75 6E 61 72 0D 0A, major, minor, kind, flags,
 *            u16 header bytes, u16 chunks, u16 entry bytes, u16 0, u32 total,
 *            writer and its version (4 B), CRC-32 of bytes 0-27
 *   directory  chunks x 20 B { tag[4], u16 version, u16 flags, u32 offset,
 *            u32 stored length, u32 CRC-32 of the stored bytes }, then the
 *            directory's CRC-32
 *   chunks   in directory order, each 4-aligned, the last ending at total
 *
 * A tag with an upper-case first letter is critical (a reader that does not
 * know it refuses the file); lower-case is ancillary (skipped and counted).
 * Flag bit 0, DEFLATED: the stored bytes are a u32 unpacked length and raw
 * deflate with a window of at most 4 KiB (fm1_deflate.h).
 *
 * Chunks (version 1), in the records' canonical order:
 *   info  key-value: 1-3 made.by/version/commit, 4 name, 5 title, 6 about,
 *         7 author, 8 licence (strings)
 *   PROJ  key-value: 1 current, 2 octave, 3 transpose (i32), 4 key root (u32),
 *         5 scale (string)
 *   UNIT  one unit: u8 role, sound, slot, flags (bit 0 on, bit 1 has on),
 *         u8 n + n bytes of engine id (0: an empty unit); u16 count x
 *         { u16 uid, u8 focus (0xFF none), u8 type (0 f32, 1 index), u32 value };
 *         key-value: 1 level (f32)
 *   DX7V  u8 count x { u8 slot, u8 flags (bit 0 loaded), 155 VCED bytes, 3 B 0 }
 *   MODR  u8 flags (bit 0 seed), 3 B 0, u32 seed; then items: 1 module
 *         { u8 pos, u8 n, id }, 2 parameter { u8 pos, u16 uid, u8 type, u32 value },
 *         3 pattern data { u8 pos, u8 version, u16 n, n bytes }, 4 cable
 *         { u8 slot, the 12-byte fm1_mod_slot_t, u8 n, n bytes of name }
 *   SEQS  the set's movy1 lines as items (state_movy1.c); CLIP a clip's
 *   view  key-value: 1 mode (u32), 2-10 the view's keys (u32)
 *   SETG  key-value: 1-4 the settings (bool or i32)
 * Key-value: u16 count x { u16 key, u8 type (1 u32, 2 i32, 3 f32, 4 string,
 * 5 bytes, 6 bool), u8 0, u16 n, n bytes }; an unknown key is skipped.
 *
 * The reader pulls: it reads the header, checks the directory and every
 * chunk's CRC entry by entry, then parses each chunk through a 64-byte
 * window (an inflater's 5.5 KiB besides while a DEFLATED one is read), so
 * its state is a few hundred bytes whatever the file's size. The writer
 * holds its file (FM1_STATE_BIN_MAX) and writes it at FM1_REC_END.
 * C99, no heap, no stdio. MIT licence. */
#include "fm1_state.h"
#include "fm1_deflate.h"
#include "fm1_num.h"
#include "state_movy1.h"

#include <string.h>

#define CH_INFO 1
#define CH_PROJ 2
#define CH_UNIT 3
#define CH_DX7V 4
#define CH_MODR 5
#define CH_SEQS 6
#define CH_CLIP 7
#define CH_VIEW 8
#define CH_SETG 9
#define CH_COUNT 10

static const char kTag[CH_COUNT][5] = { "", "info", "PROJ", "UNIT", "DX7V", "MODR", "SEQS", "CLIP",
                                        "view", "SETG" };
static const uint32_t kCap[CH_COUNT] = { 0, 2048, 2048, 6144, 5200, 12288, 49152, 16384, 2048, 2048 };
/* Kinds that may hold each chunk (bit FM1_STATE_*). */
static const uint16_t kKinds[CH_COUNT] = {
  0, 0x7E | 0x80, 1u << 1, (1u << 1) | (1u << 2) | (1u << 3), (1u << 1) | (1u << 2),
  (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4), (1u << 1) | (1u << 7), 1u << 5,
  (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4) | (1u << 5), 1u << 6
};

static const uint8_t kMagic[8] = { 0x89, 'L', 'u', 'n', 'a', 'r', 0x0D, 0x0A };

#define KV_U32 1
#define KV_I32 2
#define KV_F32 3
#define KV_STR 4
#define KV_BYTES 5
#define KV_BOOL 6

static void put16(uint8_t *p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *p, uint32_t v) { put16(p, v & 0xFFFFu); put16(p + 2, v >> 16); }
static unsigned get16(const uint8_t *p) { return (unsigned)p[0] | ((unsigned)p[1] << 8); }
static uint32_t get32(const uint8_t *p) { return (uint32_t)get16(p) | ((uint32_t)get16(p + 2) << 16); }

static void set_what(fm1_state_report_t *rep, const char *what) {
  size_t n = strlen(what);
  if (n >= sizeof(rep->what)) n = sizeof(rep->what) - 1u;
  memcpy(rep->what, what, n);
  rep->what[n] = '\0';
}

/* ======================================================================= */
/* Writer                                                                  */
/* ======================================================================= */
typedef struct {
  uint8_t tag;
  uint8_t pad_;
  uint16_t flags;
  uint32_t off, len, crc;
} bdir_t;

typedef struct bin_writer {
  fm1_put_t put;
  void *ctx;
  fm1_state_report_t *rep;
  unsigned flags, writer;
  uint8_t version[3];
  uint8_t has_head, kind, minor;
  int err;
  bdir_t dir[FM1_STATE_CHUNKS];
  unsigned n_chunks;
  uint8_t cur;                /* the open chunk: CH_*, 0 none */
  uint8_t u_role, u_sound, u_slot;
  uint8_t level_has;
  uint8_t mod_seen;
  uint8_t pad2_[2];
  uint32_t level;
  size_t count_at;            /* where the open chunk's count goes */
  unsigned count;
  size_t cn;
  uint8_t chunk[65536];
  uint8_t info_key;
  uint16_t info_n;
  char info[FM1_INFO_KEYS * 128];
  uint32_t line_n;
  char line[FM1_MOVY1_LINE_MAX];
  uint8_t data_pos, data_ver;
  uint16_t data_n;
  uint8_t data[FM1_STATE_DATA_ONE];
  size_t body_n;
  uint8_t body[FM1_STATE_BIN_MAX];
  uint8_t zout[65536 + 8];
  uint32_t zscratch[FM1_DEFLATE_SCRATCH / 4u];
} bin_writer_t;

size_t fm1_state_bin_writer_size(void) { return sizeof(bin_writer_t); }

fm1_state_writer_t *fm1_state_bin_writer(void *mem, unsigned flags, unsigned writer,
                                         const uint8_t version[3], fm1_put_t put, void *ctx,
                                         fm1_state_report_t *rep) {
  bin_writer_t *w = (bin_writer_t *)mem;
  if (!w) return NULL;
  memset(w, 0, offsetof(bin_writer_t, chunk));   /* the buffers need no clearing, their counts do */
  w->info_n = 0;
  w->line_n = 0;
  w->data_n = 0;
  w->body_n = 0;
  w->put = put;
  w->ctx = ctx;
  w->rep = rep;
  w->flags = flags;
  w->writer = writer;
  if (version) memcpy(w->version, version, 3);
  return (fm1_state_writer_t *)(void *)w;
}

static int berr(bin_writer_t *w, unsigned code, const char *what) {
  if (!w->err) {
    w->err = 1;
    if (w->rep && w->rep->code == FM1_STATE_OK) {
      w->rep->code = (uint8_t)code;
      set_what(w->rep, what);
    }
  }
  return 0;
}

static int cput(bin_writer_t *w, const void *b, size_t n) {
  if (w->cn + n > sizeof(w->chunk)) return berr(w, FM1_STATE_TOO_BIG, "a chunk past its cap");
  memcpy(w->chunk + w->cn, b, n);
  w->cn += n;
  return 1;
}
static int cput8(bin_writer_t *w, unsigned v) { const uint8_t b = (uint8_t)v; return cput(w, &b, 1); }
static int cput16(bin_writer_t *w, unsigned v) { uint8_t b[2]; put16(b, v); return cput(w, b, 2); }
static int cput32(bin_writer_t *w, uint32_t v) { uint8_t b[4]; put32(b, v); return cput(w, b, 4); }

/* A key-value entry in the open chunk (its count at count_at). */
static int kv(bin_writer_t *w, unsigned key, unsigned type, const void *b, size_t n) {
  ++w->count;
  return cput16(w, key) && cput8(w, type) && cput8(w, 0) && cput16(w, (unsigned)n) && cput(w, b, n);
}
static int kv32(bin_writer_t *w, unsigned key, unsigned type, uint32_t v) {
  uint8_t b[4];
  put32(b, v);
  return kv(w, key, type, b, 4);
}

static int close_chunk(bin_writer_t *w) {
  bdir_t *d;
  size_t stored, pad;
  const uint8_t *src = w->chunk;
  uint16_t flags = 0;
  if (!w->cur) return 1;
  switch (w->cur) {
    case CH_INFO: case CH_PROJ: case CH_VIEW: case CH_SETG:
      put16(w->chunk + w->count_at, w->count);
      break;
    case CH_UNIT:
      put16(w->chunk + w->count_at, w->count);
      if (!cput16(w, w->level_has ? 1u : 0u)) return 0;
      if (w->level_has) {
        uint8_t b[4];
        put32(b, w->level);
        if (!cput16(w, 1) || !cput8(w, KV_F32) || !cput8(w, 0) || !cput16(w, 4) || !cput(w, b, 4)) return 0;
      }
      break;
    case CH_DX7V:
      w->chunk[0] = (uint8_t)w->count;
      break;
    default:
      break;
  }
  if (w->cn > kCap[w->cur]) return berr(w, FM1_STATE_TOO_BIG, "a chunk past its cap");
  if (w->n_chunks >= FM1_STATE_CHUNKS) return berr(w, FM1_STATE_TOO_BIG, "too many chunks");
  stored = w->cn;
  if ((w->flags & FM1_STATE_BIN_DEFLATE) && w->cn >= 16u) {
    const size_t z = fm1_deflate(w->chunk, w->cn, w->zout + 4, sizeof(w->zout) - 4u, w->zscratch);
    if (z && (z + 4u) * 4u <= w->cn * 3u) {
      put32(w->zout, (uint32_t)w->cn);
      src = w->zout;
      stored = z + 4u;
      flags = 1;
    }
  }
  pad = (4u - (w->body_n & 3u)) & 3u;
  if (w->body_n + pad + stored > sizeof(w->body)) return berr(w, FM1_STATE_TOO_BIG, "past 96 KiB");
  memset(w->body + w->body_n, 0, pad);
  w->body_n += pad;
  d = &w->dir[w->n_chunks++];
  d->tag = w->cur;
  d->flags = flags;
  d->off = (uint32_t)w->body_n;
  d->len = (uint32_t)stored;
  d->crc = fm1_state_crc32(0, src, stored);
  memcpy(w->body + w->body_n, src, stored);
  w->body_n += stored;
  w->cur = 0;
  w->cn = 0;
  w->count = 0;
  return 1;
}

static int open_chunk(bin_writer_t *w, unsigned ch) {
  if (w->cur == ch && (ch == CH_INFO || ch == CH_SETG || ch == CH_SEQS || ch == CH_CLIP || ch == CH_MODR ||
                       ch == CH_DX7V)) {
    return 1;
  }
  if (!close_chunk(w)) return 0;
  if (!((kKinds[ch] >> w->kind) & 1u)) return berr(w, FM1_STATE_BAD, "a record this kind of file does not hold");
  w->cur = (uint8_t)ch;
  w->cn = 0;
  w->count = 0;
  switch (ch) {
    case CH_INFO: case CH_PROJ: case CH_VIEW: case CH_SETG:
      w->count_at = 0;
      return cput16(w, 0);
    case CH_DX7V:
      return cput8(w, 0);
    default:
      return 1;
  }
}

static int flush_line(bin_writer_t *w) {
  size_t n;
  n = fm1_movy1_encode(w->line, w->line_n, w->chunk + w->cn, sizeof(w->chunk) - w->cn);
  if (!n) return berr(w, FM1_STATE_TOO_BIG, "a set past its cap");
  w->cn += n;
  return 1;
}

static int assemble(bin_writer_t *w) {
  uint8_t head[32], ent[20];
  const size_t dir_end = 32u + 20u * w->n_chunks + 4u;
  const size_t base = (dir_end + 3u) & ~(size_t)3u;
  uint32_t total, dcrc = 0;
  unsigned i;
  if (w->n_chunks == 0) return berr(w, FM1_STATE_BAD, "no chunks");
  total = (uint32_t)(base + w->body_n);
  if (total > FM1_STATE_BIN_MAX) return berr(w, FM1_STATE_TOO_BIG, "past 96 KiB");
  memcpy(head, kMagic, 8);
  head[8] = FM1_STATE_MAJOR;
  head[9] = w->minor;
  head[10] = w->kind;
  head[11] = 0;
  put16(head + 12, 32);
  put16(head + 14, w->n_chunks);
  put16(head + 16, 20);
  put16(head + 18, 0);
  put32(head + 20, total);
  head[24] = (uint8_t)w->writer;
  head[25] = w->version[0];
  head[26] = w->version[1];
  head[27] = w->version[2];
  put32(head + 28, fm1_state_crc32(0, head, 28));
  w->put(w->ctx, (const char *)head, 32);
  for (i = 0; i < w->n_chunks; ++i) {
    const bdir_t *d = &w->dir[i];
    memcpy(ent, kTag[d->tag], 4);
    put16(ent + 4, 1);
    put16(ent + 6, d->flags);
    put32(ent + 8, (uint32_t)(base + d->off));
    put32(ent + 12, d->len);
    put32(ent + 16, d->crc);
    dcrc = fm1_state_crc32(dcrc, ent, 20);
    w->put(w->ctx, (const char *)ent, 20);
  }
  put32(ent, dcrc);
  w->put(w->ctx, (const char *)ent, 4);
  if (base > dir_end) {
    static const char zero[4] = { 0, 0, 0, 0 };
    w->put(w->ctx, zero, base - dir_end);
  }
  w->put(w->ctx, (const char *)w->body, w->body_n);
  return 1;
}

int fm1_state_bin_write(void *wv, const fm1_rec_t *r) {
  bin_writer_t *w = (bin_writer_t *)wv;
  if (w->err) return 0;
  if (!w->has_head && r->type != FM1_REC_HEAD) return berr(w, FM1_STATE_BAD, "the head record comes first");
  switch (r->type) {
    case FM1_REC_HEAD:
      if (w->has_head) return berr(w, FM1_STATE_BAD, "two head records");
      if (r->u.head.kind == 0 || r->u.head.kind >= FM1_STATE_KINDS) return berr(w, FM1_STATE_BAD, "an unknown kind");
      w->has_head = 1;
      w->kind = r->u.head.kind;
      w->minor = r->u.head.minor;
      return 1;
    case FM1_REC_INFO:
      if (!open_chunk(w, CH_INFO)) return 0;
      if (r->piece & FM1_REC_FIRST) { w->info_key = r->u.info.key; w->info_n = 0; }
      if (w->info_n + r->u.info.n > sizeof(w->info)) return berr(w, FM1_STATE_TOO_BIG, "info text too long");
      memcpy(w->info + w->info_n, r->u.info.s, r->u.info.n);
      w->info_n = (uint16_t)(w->info_n + r->u.info.n);
      if (r->piece & FM1_REC_LAST) return kv(w, w->info_key, KV_STR, w->info, w->info_n);
      return 1;
    case FM1_REC_SESSION: {
      const size_t sl = strlen(r->u.session.scale);
      if (!open_chunk(w, CH_PROJ)) return 0;
      if (!kv32(w, 1, KV_I32, (uint32_t)(int32_t)r->u.session.current) ||
          !kv32(w, 2, KV_I32, (uint32_t)(int32_t)r->u.session.octave) ||
          !kv32(w, 3, KV_I32, (uint32_t)(int32_t)r->u.session.transpose)) {
        return 0;
      }
      if (r->u.session.has_key) {
        if (!kv32(w, 4, KV_U32, r->u.session.root) || !kv(w, 5, KV_STR, r->u.session.scale, sl)) return 0;
      }
      return close_chunk(w);
    }
    case FM1_REC_UNIT: {
      const size_t n = strlen(r->u.unit.id);
      if (!close_chunk(w) || !open_chunk(w, CH_UNIT)) return 0;
      w->u_role = r->role;
      w->u_sound = r->sound;
      w->u_slot = r->slot;
      w->level_has = 0;
      if (!cput8(w, r->role) || !cput8(w, r->sound) || !cput8(w, r->slot) || !cput8(w, 0) ||
          !cput8(w, (unsigned)n) || !cput(w, r->u.unit.id, n)) {
        return 0;
      }
      w->count_at = w->cn;
      return cput16(w, 0);
    }
    case FM1_REC_ON:
      if (w->cur != CH_UNIT || r->role != w->u_role || r->sound != w->u_sound || r->slot != w->u_slot) {
        return berr(w, FM1_STATE_BAD, "records out of canonical order");
      }
      w->chunk[3] = (uint8_t)(0x02u | (r->u.on ? 1u : 0u));
      return 1;
    case FM1_REC_PARAM:
      if (r->role == FM1_ROLE_MODULE) {
        if (w->cur != CH_MODR) return berr(w, FM1_STATE_BAD, "records out of canonical order");
        return cput8(w, 2) && cput8(w, r->slot) && cput16(w, r->u.param.uid) && cput8(w, r->u.param.vtype) &&
               cput32(w, r->u.param.bits);
      }
      if (w->cur != CH_UNIT || r->role != w->u_role || r->sound != w->u_sound || r->slot != w->u_slot) {
        return berr(w, FM1_STATE_BAD, "records out of canonical order");
      }
      if (++w->count > 512u) return berr(w, FM1_STATE_TOO_BIG, "more than 512 records in a unit");
      return cput16(w, r->u.param.uid) && cput8(w, r->u.param.focus) && cput8(w, r->u.param.vtype) &&
             cput32(w, r->u.param.bits);
    case FM1_REC_LEVEL:
      if (w->cur != CH_UNIT || w->u_role != FM1_ROLE_SOUND || r->sound != w->u_sound) {
        return berr(w, FM1_STATE_BAD, "records out of canonical order");
      }
      w->level_has = 1;
      w->level = r->u.level;
      return 1;
    case FM1_REC_DX7: {
      static const uint8_t zero[3] = { 0, 0, 0 };
      if (!open_chunk(w, CH_DX7V)) return 0;
      ++w->count;
      return cput8(w, r->slot) && cput8(w, 1) && cput(w, r->u.dx7.vced, 155) && cput(w, zero, 3);
    }
    case FM1_REC_MOD:
      if (!close_chunk(w) || !open_chunk(w, CH_MODR)) return 0;
      return cput8(w, 0) && cput8(w, 0) && cput16(w, 0) && cput32(w, 0);
    case FM1_REC_SEED:
      if (w->cur != CH_MODR) return berr(w, FM1_STATE_BAD, "records out of canonical order");
      w->chunk[0] = 1;
      put32(w->chunk + 4, r->u.seed);
      return 1;
    case FM1_REC_MODULE: {
      const size_t n = strlen(r->u.unit.id);
      if (w->cur != CH_MODR) return berr(w, FM1_STATE_BAD, "records out of canonical order");
      return cput8(w, 1) && cput8(w, r->slot) && cput8(w, (unsigned)n) && cput(w, r->u.unit.id, n);
    }
    case FM1_REC_DATA:
      if (w->cur != CH_MODR) return berr(w, FM1_STATE_BAD, "records out of canonical order");
      if (r->piece & FM1_REC_FIRST) { w->data_pos = r->slot; w->data_ver = r->u.data.version; w->data_n = 0; }
      if (w->data_n + r->u.data.n > sizeof(w->data)) return berr(w, FM1_STATE_TOO_BIG, "too much pattern data");
      memcpy(w->data + w->data_n, r->u.data.b, r->u.data.n);
      w->data_n = (uint16_t)(w->data_n + r->u.data.n);
      if (r->piece & FM1_REC_LAST) {
        return cput8(w, 3) && cput8(w, w->data_pos) && cput8(w, w->data_ver) && cput16(w, w->data_n) &&
               cput(w, w->data, w->data_n);
      }
      return 1;
    case FM1_REC_CABLE: {
      const fm1_mod_slot_t *s = &r->u.cable.s;
      size_t n = strlen(r->u.cable.name);
      if (w->cur != CH_MODR) return berr(w, FM1_STATE_BAD, "records out of canonical order");
      if (n > 24u) n = 24u;
      return cput8(w, 4) && cput8(w, r->slot) && cput8(w, s->src) && cput8(w, s->via) &&
             cput8(w, s->dst_unit) && cput8(w, s->flags) && cput16(w, s->dst) &&
             cput16(w, (uint16_t)s->amount) && cput16(w, (uint16_t)s->offset) && cput16(w, s->uid) &&
             cput8(w, (unsigned)n) && cput(w, r->u.cable.name, n);
    }
    case FM1_REC_LINE: {
      const unsigned ch = r->u.line.which == FM1_LINES_CLIP ? CH_CLIP : CH_SEQS;
      if (!open_chunk(w, ch)) return 0;
      if (r->piece & FM1_REC_FIRST) w->line_n = 0;
      if (w->line_n + r->u.line.n > sizeof(w->line)) return berr(w, FM1_STATE_TOO_BIG, "a line past 16 KiB");
      memcpy(w->line + w->line_n, r->u.line.s, r->u.line.n);
      w->line_n += r->u.line.n;
      if (r->piece & FM1_REC_LAST) return flush_line(w);
      return 1;
    }
    case FM1_REC_VIEW: {
      unsigned k;
      if (!close_chunk(w) || !open_chunk(w, CH_VIEW)) return 0;
      if (!kv32(w, 1, KV_U32, r->u.view.mode)) return 0;
      for (k = 0; k < FM1_VIEW_KEYS; ++k) {
        if (((r->u.view.has >> k) & 1u) && !kv32(w, 2u + k, KV_U32, r->u.view.v[k])) return 0;
      }
      return close_chunk(w);
    }
    case FM1_REC_SETTING:
      if (!open_chunk(w, CH_SETG)) return 0;
      return kv32(w, r->u.setting.key, r->u.setting.is_bool ? KV_BOOL : KV_I32,
                  (uint32_t)r->u.setting.value);
    case FM1_REC_END:
      if (!close_chunk(w)) return 0;
      if (w->n_chunks == 0 && (!open_chunk(w, CH_INFO) || !close_chunk(w))) return 0;   /* a file has a chunk */
      return assemble(w);
    default:
      return berr(w, FM1_STATE_BAD, "an unknown record");
  }
}


/* ======================================================================= */
/* Reader                                                                  */
/* ======================================================================= */
typedef struct {
  fm1_src_read_t rd;
  void *rctx;
  uint32_t off, end;          /* raw: the stored bytes still to read */
  uint32_t left;              /* content bytes still to read */
  int deflated;
  fm1_inflate_t *z;
  uint32_t bpos, blen;
  uint8_t buf[64];
} cs_t;

typedef struct {
  fm1_rec_sink_t sink;
  void *sctx;
  fm1_state_report_t *rep;
  int stop;
  uint8_t kind;
  uint8_t mod_pos_seen;
  uint8_t mod_seen;
  uint8_t pad_;
  uint32_t units_seen[2];     /* 40 unit places */
  uint32_t dx7_seen, cable_seen;
  uint32_t data_total;
  uint32_t line_n;
  uint8_t lines_seen;
  uint8_t pad2_[3];
} br_t;

static int brefuse(br_t *b, unsigned code, const char *what) {
  if (!b->stop) {
    b->stop = 1;
    b->rep->code = (uint8_t)code;
    set_what(b->rep, what);
  }
  return 0;
}

static int bbad(br_t *b, const char *what) { return brefuse(b, FM1_STATE_BAD, what); }
static int short_chunk(br_t *b) { return bbad(b, "a chunk ends early"); }

static int bemit(br_t *b, fm1_rec_t *r) {
  if (b->stop) return 0;
  ++b->rep->records;
  if (!b->sink(b->sctx, r)) {
    b->stop = 1;
    if (b->rep->code == FM1_STATE_OK) b->rep->code = FM1_STATE_STOPPED;
    if (!b->rep->what[0]) set_what(b->rep, "the loader stopped");
    return 0;
  }
  return 1;
}

static uint32_t cs_src(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
  const cs_t *c = (const cs_t *)ctx;
  return c->rd(c->rctx, off, buf, n);
}

static int cs_get(cs_t *c, uint8_t *out, uint32_t n) {
  uint32_t k = 0;
  if (n > c->left) return 0;
  while (k < n) {
    if (c->bpos == c->blen) {
      uint32_t want = (uint32_t)sizeof(c->buf);
      const uint32_t rest = c->left - k;
      if (want > rest) want = rest;
      if (c->deflated) {
        c->blen = fm1_inflate_read(c->z, c->buf, want);
      } else {
        if (want > c->end - c->off) want = c->end - c->off;
        c->blen = want ? c->rd(c->rctx, c->off, c->buf, want) : 0;
        if (c->blen > want) c->blen = 0;
        c->off += c->blen;
      }
      c->bpos = 0;
      if (c->blen == 0) return 0;
    }
    {
      uint32_t m = c->blen - c->bpos;
      if (m > n - k) m = n - k;
      memcpy(out + k, c->buf + c->bpos, m);
      c->bpos += m;
      k += m;
    }
  }
  c->left -= n;
  return 1;
}

static int cs_skip(cs_t *c, uint32_t n) {
  uint8_t t[64];
  while (n) {
    const uint32_t m = n < sizeof(t) ? n : (uint32_t)sizeof(t);
    if (!cs_get(c, t, m)) return 0;
    n -= m;
  }
  return 1;
}

static int pull_byte(void *ctx, uint8_t *b) { return cs_get((cs_t *)ctx, b, 1); }

/* UTF-8, checked across pieces: no overlong form, surrogate, U+0000 or
 * other control character, no bidi override. */
typedef struct {
  uint32_t cp, cps;
  uint8_t need, len;
} utf_t;

/* `text`: info text, which the JSON reader also keeps free of bidi
 * overrides; otherwise a movy1 line, which may hold them. */
static int utf_ok(utf_t *u, const uint8_t *t, uint32_t m, int text) {
  uint32_t i;
  for (i = 0; i < m; ++i) {
    const uint8_t x = t[i];
    if (u->need) {
      if ((x & 0xC0u) != 0x80u) return 0;
      u->cp = (u->cp << 6) | (x & 0x3Fu);
      if (--u->need) continue;
      if ((u->len == 2 && u->cp < 0x80u) || (u->len == 3 && u->cp < 0x800u) ||
          (u->len == 4 && (u->cp < 0x10000u || u->cp > 0x10FFFFu)) || (u->cp >= 0xD800u && u->cp <= 0xDFFFu) ||
          (text && ((u->cp >= 0x202Au && u->cp <= 0x202Eu) || (u->cp >= 0x2066u && u->cp <= 0x2069u)))) {
        return 0;
      }
      ++u->cps;
      continue;
    }
    if (x < 0x80u) {
      if (x < 0x20u || x == 0x7Fu) return 0;
      ++u->cps;
    } else if ((x & 0xE0u) == 0xC0u) { u->cp = x & 0x1Fu; u->need = 1; u->len = 2; }
    else if ((x & 0xF0u) == 0xE0u) { u->cp = x & 0x0Fu; u->need = 2; u->len = 3; }
    else if ((x & 0xF8u) == 0xF0u) { u->cp = x & 0x07u; u->need = 3; u->len = 4; }
    else return 0;
  }
  return 1;
}

static int info_cap(unsigned key) {
  switch (key) {
    case FM1_INFO_NAME: return 16;
    case FM1_INFO_TITLE: return 80;
    case FM1_INFO_ABOUT: return 240;
    case FM1_INFO_AUTHOR: return 64;
    case FM1_INFO_LICENCE: return 32;
    default: return 64;
  }
}

/* An info text of n bytes, out in pieces. The screen's name, `made` and the
 * licence keep the JSON reader's narrower characters. */
static int text_value(br_t *b, cs_t *c, uint32_t n, unsigned key) {
  fm1_rec_t r;
  uint8_t t[64];
  uint32_t done = 0;
  utf_t u;
  memset(&u, 0, sizeof(u));
  do {
    const uint32_t m = n - done < sizeof(t) ? n - done : (uint32_t)sizeof(t);
    uint32_t i;
    if (!cs_get(c, t, m)) return short_chunk(b);
    if (!utf_ok(&u, t, m, 1)) return bbad(b, "text that is not clean UTF-8");
    for (i = 0; i < m; ++i) {
      const uint8_t x = t[i];
      if (key == FM1_INFO_NAME || key == FM1_INFO_BY || key == FM1_INFO_VERSION || key == FM1_INFO_COMMIT) {
        if (x >= 0x7Fu) return bbad(b, "this text is printable ASCII");
      } else if (key == FM1_INFO_LICENCE) {
        if (!((x >= 'A' && x <= 'Z') || (x >= 'a' && x <= 'z') || (x >= '0' && x <= '9') || x == '.' ||
              x == '+' || x == '-')) {
          return bbad(b, "not a licence id");
        }
      }
    }
    if ((int)u.cps > info_cap(key)) return bbad(b, "text past its length");
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_INFO;
    r.piece = (uint8_t)((done == 0 ? FM1_REC_FIRST : 0u) | (done + m == n ? FM1_REC_LAST : 0u));
    r.u.info.key = (uint8_t)key;
    r.u.info.n = (uint16_t)m;
    r.u.info.s = (const char *)t;
    done += m;
    if (!bemit(b, &r)) return 0;
  } while (done < n);
  if (u.need) return bbad(b, "text that is not clean UTF-8");
  return 1;
}

/* Key-value entries: the callee reads or skips each value. */
typedef int (*kv_fn)(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx);

static int kv_each(br_t *b, cs_t *c, kv_fn fn, void *ctx) {
  uint8_t h[6];
  uint16_t seen[64];
  unsigned count, i;
  if (!cs_get(c, h, 2)) return short_chunk(b);
  count = get16(h);
  if (count > 64u) return brefuse(b, FM1_STATE_TOO_BIG, "more than 64 entries");
  for (i = 0; i < count; ++i) {
    if (!cs_get(c, h, 6)) return short_chunk(b);
    unsigned j;
    if (h[3]) return bbad(b, "unknown entry flags");
    seen[i] = (uint16_t)get16(h);
    for (j = 0; j < i; ++j) {
      if (seen[j] == seen[i]) return bbad(b, "an entry given twice");
    }
    if (!fn(b, c, seen[i], h[2], get16(h + 4), ctx)) return 0;
  }
  return 1;
}

static int kv_skip(br_t *b, cs_t *c, unsigned n) {
  ++b->rep->skipped;
  return cs_skip(c, n) ? 1 : short_chunk(b);
}

/* A 4-byte value of type `want`: 1 read, 0 not that (and nothing read). */
static int kv_word(br_t *b, cs_t *c, unsigned type, unsigned n, unsigned want, uint32_t *v) {
  uint8_t t[4];
  if (type != want || n != 4) return 0;
  if (!cs_get(c, t, 4)) return short_chunk(b) - 1;
  *v = get32(t);
  return 1;
}

typedef struct {
  fm1_rec_t r;
  uint8_t has;
} acc_t;

static int info_kv(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx) {
  (void)ctx;
  if (key == 0 || key >= FM1_INFO_KEYS || type != KV_STR) return kv_skip(b, c, n);
  if (n > 1024u) return bbad(b, "text past its length");
  return text_value(b, c, n, key);
}

static int proj_kv(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx) {
  acc_t *a = (acc_t *)ctx;
  uint32_t v;
  int st;
  if (key >= 1 && key <= 4) {
    st = kv_word(b, c, type, n, key == 4 ? KV_U32 : KV_I32, &v);
    if (st < 0) return 0;
    if (!st) return kv_skip(b, c, n);
    switch (key) {
      case 1:
        if ((int32_t)v < 0 || (int32_t)v > 3) return bbad(b, "a session out of range");
        a->r.u.session.current = (int8_t)v;
        break;
      case 2:
        if ((int32_t)v < -3 || (int32_t)v > 3) return bbad(b, "a session out of range");
        a->r.u.session.octave = (int8_t)v;
        break;
      case 3:
        if ((int32_t)v < -12 || (int32_t)v > 12) return bbad(b, "a session out of range");
        a->r.u.session.transpose = (int8_t)v;
        break;
      default:
        if (v > 11u) return bbad(b, "a session out of range");
        a->r.u.session.root = (uint8_t)v;
        a->has |= 1u;
        break;
    }
    return 1;
  }
  if (key == 5 && type == KV_STR) {
    char s[25];
    unsigned i;
    if (n < 1 || n > 24) return bbad(b, "a scale id out of range");
    if (!cs_get(c, (uint8_t *)s, n)) return short_chunk(b);
    for (i = 0; i < n; ++i) {
      const char x = s[i];
      if (!((x >= 'a' && x <= 'z') || (i && ((x >= '0' && x <= '9') || x == '-')))) return bbad(b, "not a scale id");
    }
    s[n] = '\0';
    memcpy(a->r.u.session.scale, s, n + 1u);
    a->has |= 2u;
    return 1;
  }
  return kv_skip(b, c, n);
}

static int view_kv(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx) {
  acc_t *a = (acc_t *)ctx;
  uint32_t v;
  int st;
  if (key < 1 || key > 1u + FM1_VIEW_KEYS) return kv_skip(b, c, n);
  st = kv_word(b, c, type, n, KV_U32, &v);
  if (st < 0) return 0;
  if (!st) return kv_skip(b, c, n);
  if (key == 1) {
    if (v >= FM1_VIEW_MODES) return bbad(b, "not a view mode");
    a->r.u.view.mode = (uint8_t)v;
    a->has = 1;
  } else {
    static const uint8_t kMax[FM1_VIEW_KEYS] = { 4, 16, 43, 16, 64, 3, 8, 32, 64 };
    const unsigned k = key - 2u;
    if (v > kMax[k] || (k != FM1_VK_UNIT && k != FM1_VK_PANEL && v < 1u)) return bbad(b, "a view key out of range");
    a->r.u.view.v[k] = (uint8_t)v;
    a->r.u.view.has = (uint16_t)(a->r.u.view.has | (1u << k));
  }
  return 1;
}

static int setg_kv(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx) {
  fm1_rec_t r;
  uint32_t v;
  int st;
  (void)ctx;
  if (key < 1 || key >= FM1_SET_KEYS || (type != KV_BOOL && type != KV_I32)) return kv_skip(b, c, n);
  st = kv_word(b, c, type, n, type, &v);
  if (st < 0) return 0;
  if (!st) return kv_skip(b, c, n);
  if (type == KV_BOOL ? v > 1u : (key != FM1_SET_MIDI_IN_CHANNEL || v > 16u)) return bbad(b, "a setting out of range");
  if ((type == KV_BOOL) != (key != FM1_SET_MIDI_IN_CHANNEL)) return bbad(b, "a setting of the wrong type");
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_SETTING;
  r.u.setting.key = (uint8_t)key;
  r.u.setting.is_bool = (uint8_t)(type == KV_BOOL);
  r.u.setting.value = (int32_t)v;
  return bemit(b, &r);
}

static int level_kv(br_t *b, cs_t *c, unsigned key, unsigned type, unsigned n, void *ctx) {
  acc_t *a = (acc_t *)ctx;
  uint32_t v;
  int st;
  if (key != 1) return kv_skip(b, c, n);
  st = kv_word(b, c, type, n, KV_F32, &v);
  if (st < 0) return 0;
  if (!st) return kv_skip(b, c, n);
  {
    const float f = fm1_num_float(v);
    if (!(f >= 0.0f && f <= 100.0f) || v == 0x80000000u) return bbad(b, "a level out of range");
  }
  a->r.u.level = v;
  a->has = 1;
  return 1;
}

static int id_ok(const char *s, size_t n) {
  size_t i;
  if (n > 15) return 0;
  if (n == 0) return 1;
  if (s[0] < 'a' || s[0] > 'z') return 0;
  for (i = 1; i < n; ++i) {
    const char x = s[i];
    if (!((x >= 'a' && x <= 'z') || (x >= '0' && x <= '9') || x == '-')) return 0;
  }
  return 1;
}

static int value_ok(unsigned vtype, uint32_t bits) {
  if (vtype == FM1_VAL_INDEX) return bits < 256u;
  if (vtype != FM1_VAL_F32) return 0;
  return (bits & 0x7F800000u) != 0x7F800000u && bits != 0x80000000u;
}

static int unit_place(const br_t *b, unsigned role, unsigned sound, unsigned slot) {
  const unsigned k = b->kind;
  if (k == FM1_STATE_PROJECT) {
    if (role == FM1_ROLE_SOUND && sound < 4 && slot == 0) return (int)sound;
    if (role == FM1_ROLE_INSERT && sound < 4 && slot < 2) return (int)(4 + 2 * sound + slot);
    if (role == FM1_ROLE_MFX && sound < 4 && slot < 4) return (int)(12 + 4 * sound + slot);
    if (role == FM1_ROLE_MASTER && sound == 0 && slot < 2) return (int)(28 + slot);
  } else if (k == FM1_STATE_SOUND) {
    if (role == FM1_ROLE_SOUND && sound == 0 && slot == 0) return 0;
    if (role == FM1_ROLE_INSERT && sound == 0 && slot < 2) return (int)(4 + slot);
    if (role == FM1_ROLE_MFX && sound == 0 && slot < 4) return (int)(12 + slot);
  } else if (k == FM1_STATE_FX) {
    if (role == FM1_ROLE_MASTER && sound == 0 && slot < 4) return (int)(28 + slot);
  }
  return -1;
}

static int read_unit(br_t *b, cs_t *c) {
  uint8_t h[8];
  /* Bounded by the format's record cap; do not allocate a UID-by-pad map. */
  uint16_t seen_uid[512];
  uint8_t seen_focus[512];
  fm1_rec_t r;
  acc_t lv;
  unsigned count, i;
  int ix;
  if (!cs_get(c, h, 5)) return short_chunk(b);
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_UNIT;
  r.role = h[0];
  r.sound = h[1];
  r.slot = h[2];
  ix = unit_place(b, h[0], h[1], h[2]);
  if (ix < 0) return bbad(b, "a unit this kind of file does not hold");
  if ((b->units_seen[ix / 32] >> (ix % 32)) & 1u) return bbad(b, "a unit given twice");
  b->units_seen[ix / 32] |= 1u << (ix % 32);
  if (h[3] & ~3u) return bbad(b, "unknown unit flags");
  if (h[4] > 15u) return bbad(b, "an engine id past 15 characters");
  if (!cs_get(c, (uint8_t *)r.u.unit.id, h[4])) return short_chunk(b);
  r.u.unit.id[h[4]] = '\0';
  if (!id_ok(r.u.unit.id, h[4])) return bbad(b, "not an engine id");
  if (b->kind == FM1_STATE_PROJECT && ix == 0 && h[4] == 0) return bbad(b, "Sound 1 is never empty");
  if (b->kind == FM1_STATE_SOUND && ix == 0 && h[4] == 0) return bbad(b, "a sound file's sound is never empty");
  ++b->rep->units;
  if (!bemit(b, &r)) return 0;
  if (h[3] & 2u) {
    if (h[0] != FM1_ROLE_MFX) return bbad(b, "on is a MIDI effect's");
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_ON;
    r.role = h[0];
    r.sound = h[1];
    r.slot = h[2];
    r.u.on = (uint8_t)(h[3] & 1u);
    if (!bemit(b, &r)) return 0;
  } else if (h[3] & 1u) {
    return bbad(b, "unknown unit flags");
  }
  if (!cs_get(c, h + 5, 2)) return short_chunk(b);
  count = get16(h + 5);
  if (count > 512u) return brefuse(b, FM1_STATE_TOO_BIG, "more than 512 records in a unit");
  if (count && !h[4]) return bbad(b, "an empty unit with values");
  for (i = 0; i < count; ++i) {
    uint8_t p[8];
    if (!cs_get(c, p, 8)) return short_chunk(b);
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_PARAM;
    r.role = h[0];
    r.sound = h[1];
    r.slot = h[2];
    r.u.param.uid = (uint16_t)get16(p);
    r.u.param.focus = p[2];
    r.u.param.vtype = p[3];
    r.u.param.bits = get32(p + 4);
    if (r.u.param.uid < 1u || r.u.param.uid > FM1_PARAM_UID_MAX) return bbad(b, "a uid out of range");
    if (r.u.param.focus != FM1_FOCUS_NONE && (r.u.param.focus >= FM1_STATE_PADS || h[0] != FM1_ROLE_SOUND)) {
      return bbad(b, "a pad out of range");
    }
    if (!value_ok(r.u.param.vtype, r.u.param.bits)) return bbad(b, "a value that cannot be read");
    {
      unsigned j;
      for (j = 0; j < i; ++j) {
        if (seen_uid[j] == r.u.param.uid && seen_focus[j] == r.u.param.focus) {
          return bbad(b, "a parameter given twice");
        }
      }
      seen_uid[i] = r.u.param.uid;
      seen_focus[i] = r.u.param.focus;
    }
    if (!bemit(b, &r)) return 0;
  }
  memset(&lv, 0, sizeof(lv));
  if (!kv_each(b, c, level_kv, &lv)) return 0;
  if (lv.has) {
    if (h[0] != FM1_ROLE_SOUND || !h[4]) return bbad(b, "a level is a sound's");
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_LEVEL;
    r.role = FM1_ROLE_SOUND;
    r.sound = h[1];
    r.u.level = lv.r.u.level;
    if (!bemit(b, &r)) return 0;
  }
  return 1;
}

static int read_dx7v(br_t *b, cs_t *c) {
  static const uint8_t kOpMax[21] = { 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 3, 3, 7, 3, 7, 99,
                                      1, 31, 99, 14 };
  static const uint8_t kGlobMax[19] = { 99, 99, 99, 99, 99, 99, 99, 99, 31, 7, 1, 99, 99, 99, 99, 1, 5,
                                        7, 48 };
  uint8_t n, v[160];
  unsigned i, k;
  fm1_rec_t r;
  if (!cs_get(c, &n, 1)) return short_chunk(b);
  if (n < 1 || n > 32) return bbad(b, "an FM6 voice count out of range");
  for (i = 0; i < n; ++i) {
    if (!cs_get(c, v, 160)) return short_chunk(b);
    if (v[0] >= 32u || v[1] != 1u) return bbad(b, "an FM6 voice out of range");
    if ((b->dx7_seen >> v[0]) & 1u) return bbad(b, "two voices in one FM6 slot");
    b->dx7_seen |= 1u << v[0];
    for (k = 0; k < 126u; ++k) {
      if (v[2 + k] > kOpMax[k % 21u]) return bbad(b, "an FM6 value out of range");
    }
    for (k = 0; k < 19u; ++k) {
      if (v[2 + 126u + k] > kGlobMax[k]) return bbad(b, "an FM6 value out of range");
    }
    for (k = 0; k < 10u; ++k) {
      if (v[2 + 145u + k] < 0x20u || v[2 + 145u + k] > 0x7Eu) return bbad(b, "an FM6 name out of range");
    }
    memset(&r, 0, sizeof(r));
    r.type = FM1_REC_DX7;
    r.slot = v[0];
    memcpy(r.u.dx7.vced, v + 2, 155);
    ++b->rep->voices;
    if (!bemit(b, &r)) return 0;
  }
  return 1;
}

static int code_ok(unsigned kind, unsigned code) {
  if (code >= FM1_MOD_MODULE && code < FM1_MOD_MODULE + 8u) return 1;
  if (code == FM1_MOD_HOST) return 1;
  if (kind == FM1_STATE_SOUND) return code == FM1_MOD_SOUND || code == FM1_MOD_INSERT || code == FM1_MOD_INSERT + 1u;
  if (kind == FM1_STATE_FX) {
    return code == FM1_MOD_FX1 || code == FM1_MOD_FX2 || code == FM1_STATE_CHAIN3 || code == FM1_STATE_CHAIN4;
  }
  if (code == FM1_MOD_SOUND || code == FM1_MOD_FX1 || code == FM1_MOD_FX2) return 1;
  if (code >= 17u && code <= 19u) return 1;
  return code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 16u && ((code - FM1_MOD_INSERT) & 3u) < 2u;
}

static int src_ok(unsigned src) {
  return src < FM1_MOD_SRC_MODULE + 64u;
}

static int read_modr(br_t *b, cs_t *c) {
  uint8_t h[16];
  fm1_rec_t r;
  if (b->mod_seen) return bbad(b, "two mod chunks");
  b->mod_seen = 1;
  if (!cs_get(c, h, 8)) return short_chunk(b);
  if ((h[0] & ~1u) || h[1] || h[2] || h[3]) return bbad(b, "unknown mod flags");
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_MOD;
  if (!bemit(b, &r)) return 0;
  if (h[0] & 1u) {
    r.type = FM1_REC_SEED;
    r.u.seed = get32(h + 4);
    if (!bemit(b, &r)) return 0;
  } else if (b->kind == FM1_STATE_PROJECT || b->kind == FM1_STATE_MODS) {
    return bbad(b, "a project's or a mod rack's mod needs its seed");
  }
  while (c->left) {
    uint8_t tag;
    if (!cs_get(c, &tag, 1)) return short_chunk(b);
    memset(&r, 0, sizeof(r));
    switch (tag) {
      case 1:
        if (!cs_get(c, h, 2)) return short_chunk(b);
        if (h[0] >= 8u || h[1] < 1u || h[1] > 15u) return bbad(b, "a module out of range");
        if ((b->mod_pos_seen >> h[0]) & 1u) return bbad(b, "two modules at one rack position");
        b->mod_pos_seen = (uint8_t)(b->mod_pos_seen | (1u << h[0]));
        r.type = FM1_REC_MODULE;
        r.role = FM1_ROLE_MODULE;
        r.slot = h[0];
        if (!cs_get(c, (uint8_t *)r.u.unit.id, h[1])) return short_chunk(b);
        if (!id_ok(r.u.unit.id, h[1])) return bbad(b, "not a kind id");
        ++b->rep->modules;
        break;
      case 2:
        if (!cs_get(c, h, 8)) return short_chunk(b);
        if (h[0] >= 8u || !((b->mod_pos_seen >> h[0]) & 1u)) return bbad(b, "a parameter of no module");
        r.type = FM1_REC_PARAM;
        r.role = FM1_ROLE_MODULE;
        r.slot = h[0];
        r.u.param.uid = (uint16_t)get16(h + 1);
        r.u.param.focus = FM1_FOCUS_NONE;
        r.u.param.vtype = h[3];
        r.u.param.bits = get32(h + 4);
        if (r.u.param.uid < 1u || r.u.param.uid > FM1_PARAM_UID_MAX) return bbad(b, "a uid out of range");
        if (!value_ok(r.u.param.vtype, r.u.param.bits)) return bbad(b, "a value that cannot be read");
        break;
      case 3: {
        unsigned n, done = 0;
        if (!cs_get(c, h, 4)) return short_chunk(b);
        if (h[0] >= 8u || !((b->mod_pos_seen >> h[0]) & 1u)) return bbad(b, "pattern data of no module");
        n = get16(h + 2);
        if (n > FM1_STATE_DATA_ONE || b->data_total + n > FM1_STATE_DATA) {
          return brefuse(b, FM1_STATE_TOO_BIG, "too much pattern data");
        }
        b->data_total += n;
        do {
          uint8_t t[64];
          const unsigned m = n - done < 64u ? n - done : 64u;
          if (!cs_get(c, t, m)) return short_chunk(b);
          memset(&r, 0, sizeof(r));
          r.type = FM1_REC_DATA;
          r.slot = h[0];
          r.piece = (uint8_t)((done == 0 ? FM1_REC_FIRST : 0u) | (done + m == n ? FM1_REC_LAST : 0u));
          r.u.data.version = h[1];
          r.u.data.n = (uint16_t)m;
          r.u.data.b = t;
          done += m;
          if (!bemit(b, &r)) return 0;
        } while (done < n);
        continue;
      }
      case 4: {
        fm1_mod_slot_t *s = &r.u.cable.s;
        if (!cs_get(c, h, 14)) return short_chunk(b);
        if (h[0] >= 32u) return bbad(b, "a matrix slot out of range");
        if ((b->cable_seen >> h[0]) & 1u) return bbad(b, "two cables in one matrix slot");
        b->cable_seen |= 1u << h[0];
        r.type = FM1_REC_CABLE;
        r.slot = h[0];
        s->src = h[1];
        s->via = h[2];
        s->dst_unit = h[3];
        s->flags = h[4];
        s->dst = (uint16_t)get16(h + 5);
        s->amount = (int16_t)get16(h + 7);
        s->offset = (int16_t)get16(h + 9);
        s->uid = (uint16_t)get16(h + 11);
        if (!src_ok(s->src) || (s->via != FM1_MOD_NONE && !src_ok(s->via)) || !code_ok(b->kind, s->dst_unit) ||
            s->amount < -16384 || s->amount > 16384 || s->offset < -16384 || s->offset > 16384 ||
            s->uid > FM1_PARAM_UID_MAX ||
            ((s->flags & FM1_MOD_SLOT_GATE_DST) ? s->dst >= FM1_MOD_MAX_GATES : s->dst > FM1_PARAM_UID_MAX) ||
            ((s->flags & FM1_MOD_SLOT_GATE_DST) && !(s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + 8u))) {
          return bbad(b, "a cable out of range");
        }
        if (h[13] > 24u) return bbad(b, "a parameter's name past 24 characters");
        if (!cs_get(c, (uint8_t *)r.u.cable.name, h[13])) return short_chunk(b);
        r.u.cable.name[h[13]] = '\0';
        {
          unsigned k;
          for (k = 0; k < h[13]; ++k) {
            if (r.u.cable.name[k] < 0x20 || r.u.cable.name[k] > 0x7E) return bbad(b, "a parameter's name out of range");
          }
          if (h[13] && s->dst) return bbad(b, "a cable with both a uid and a name");
          if (!h[13] && !s->dst && !(s->flags & FM1_MOD_SLOT_GATE_DST)) return bbad(b, "a cable to no parameter");
        }
        ++b->rep->cables;
        break;
      }
      default:
        return bbad(b, "an unknown mod item");
    }
    if (!bemit(b, &r)) return 0;
  }
  return 1;
}

typedef struct {
  br_t *b;
  uint8_t which;
  uint8_t first_line;
  uint8_t head_n;
  char head[8];
  uint32_t n;
  utf_t u;
} line_ctx_t;

/* The JSON reader's checks of a list's lines, so a binary holds nothing
 * the JSON could not: a set opens with movy1; a clip's lines are its
 * track 0 slot 0 lines. */
static int clip_prefix(const char *h) {
  if (h[0] == 'a' && h[1] == 'u') return memcmp(h, "au 0 ", 5) == 0 && h[5] >= '0' && h[5] <= '7' && h[6] == ' ';
  return memcmp(h, "cl 0 0 ", 7) == 0 || memcmp(h, "cp 0 0 ", 7) == 0 || memcmp(h, "lk 0 0 ", 7) == 0 ||
         memcmp(h, "tg 0 0 ", 7) == 0;
}

static int line_text(void *ctx, const char *s, size_t n, int first, int last) {
  line_ctx_t *l = (line_ctx_t *)ctx;
  fm1_rec_t r;
  size_t i;
  if (first) {
    l->head_n = 0;
    l->n = 0;
    memset(&l->u, 0, sizeof(l->u));
  }
  if (!utf_ok(&l->u, (const uint8_t *)s, (uint32_t)n, 0)) {
    return bbad(l->b, "a movy1 line that is not UTF-8, or a control character in one");
  }
  for (i = 0; i < n; ++i) {
    if (l->head_n < 8u) l->head[l->head_n++] = s[i];
  }
  l->n += (uint32_t)n;
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_LINE;
  r.piece = (uint8_t)((first ? FM1_REC_FIRST : 0u) | (last ? FM1_REC_LAST : 0u));
  r.u.line.which = l->which;
  r.u.line.n = (uint32_t)n;
  r.u.line.s = s;
  if (!bemit(l->b, &r)) return 0;
  if (last) {
    if (l->u.need) return bbad(l->b, "a movy1 line that is not UTF-8");
    if (l->which == FM1_LINES_SET && l->first_line && !(l->n == 5 && memcmp(l->head, "movy1", 5) == 0)) {
      return bbad(l->b, "a set's first line is movy1");
    }
    if (l->which == FM1_LINES_CLIP && (l->n < 7u || !clip_prefix(l->head))) {
      return bbad(l->b, "a clip line is au, cl, cp, lk or tg at track 0 and slot 0");
    }
  }
  return 1;
}

static int read_lines(br_t *b, cs_t *c, unsigned which) {
  line_ctx_t l;
  unsigned lines = 0;
  memset(&l, 0, sizeof(l));
  l.b = b;
  l.which = (uint8_t)which;
  l.first_line = 1;
  while (c->left) {
    int st;
    if (++lines > (which == FM1_LINES_CLIP ? 12u : 8192u)) return brefuse(b, FM1_STATE_TOO_BIG, "too many lines");
    st = fm1_movy1_decode(pull_byte, c, line_text, &l);
    if (st < 0 || b->stop) return 0;
    if (st == 0) return bbad(b, "a movy1 item that cannot be read");
    l.first_line = 0;
    ++b->rep->lines;
  }
  if (!lines) return bbad(b, "an empty list of lines");
  if (b->lines_seen) return bbad(b, "two lists of lines");
  b->lines_seen = 1;
  if (which == FM1_LINES_CLIP && lines < 2u) return bbad(b, "a clip has its cl and cp lines");
  return 1;
}

static int tag_of(const uint8_t t[4]) {
  int i;
  for (i = 1; i < CH_COUNT; ++i) {
    if (memcmp(t, kTag[i], 4) == 0) return i;
  }
  return 0;
}

int fm1_state_bin_read(fm1_src_read_t rd, void *rctx, uint32_t total, fm1_rec_sink_t sink, void *sctx,
                       fm1_state_report_t *rep, int skip_crc) {
  uint8_t h[32], e[64];
  br_t b;
  uint32_t hdr, count, esz, dir_end, chunk0, prev_end, i, dcrc = 0;
  fm1_rec_t r;
  memset(&b, 0, sizeof(b));
  b.sink = sink;
  b.sctx = sctx;
  b.rep = rep;
  if (total < 32u || rd(rctx, 0, h, 32) != 32u || memcmp(h, kMagic, 8) != 0) {
    return brefuse(&b, FM1_STATE_NOT_LUNAR, "not a Lunar Modulator file");
  }
  if (!skip_crc && get32(h + 28) != fm1_state_crc32(0, h, 28)) return bbad(&b, "the header's CRC does not match");
  rep->major = h[8];
  rep->minor = h[9];
  if (h[8] != FM1_STATE_MAJOR || h[9] > FM1_STATE_MINOR) {
    return brefuse(&b, FM1_STATE_TOO_NEW, "made with a newer Lunar Modulator");
  }
  if (h[10] == 0 || h[10] >= FM1_STATE_KINDS || h[10] == FM1_STATE_DX7BANK) return bbad(&b, "not a kind this build knows");
  b.kind = h[10];
  rep->kind = h[10];
  hdr = get16(h + 12);
  count = get16(h + 14);
  esz = get16(h + 16);
  if (hdr < 32u || hdr > 256u || count < 1u || count > FM1_STATE_CHUNKS || esz < 20u || esz > 64u) {
    return bbad(&b, "a header out of range");
  }
  if (get32(h + 20) != total) return bbad(&b, "the file's length is not its header's");
  if (total > FM1_STATE_BIN_MAX) return brefuse(&b, FM1_STATE_TOO_BIG, "past 96 KiB");
  dir_end = hdr + count * esz;
  if (dir_end + 4u > total) return bbad(&b, "a directory past the file");
  chunk0 = (dir_end + 4u + 3u) & ~3u;
  /* The directory: CRC, then each entry's bounds; every chunk's CRC. */
  for (i = 0; i < count; ++i) {
    if (rd(rctx, hdr + i * esz, e, esz) != esz) return bbad(&b, "a directory past the file");
    dcrc = fm1_state_crc32(dcrc, e, esz);
  }
  if (rd(rctx, dir_end, h, 4) != 4u) return bbad(&b, "a directory past the file");
  if (!skip_crc && get32(h) != dcrc) return bbad(&b, "the directory's CRC does not match");
  prev_end = chunk0;
  for (i = 0; i < count; ++i) {
    uint32_t off, len, crc = 0, k;
    int tag;
    if (rd(rctx, hdr + i * esz, e, 20) != 20u) return bbad(&b, "a directory past the file");
    off = get32(e + 8);
    len = get32(e + 12);
    tag = tag_of(e);
    if (!tag) {
      if (e[0] >= 'A' && e[0] <= 'Z') return brefuse(&b, FM1_STATE_TOO_NEW, "a critical chunk this build does not know");
    } else {
      if (!((kKinds[tag] >> b.kind) & 1u)) return bbad(&b, "a chunk this kind of file does not hold");
      if (len > kCap[tag] + 4u) return brefuse(&b, FM1_STATE_TOO_BIG, "a chunk past its cap");
    }
    if (get16(e + 6) & ~1u) return bbad(&b, "unknown chunk flags");
    if (get16(e + 4) < 1u) return bbad(&b, "a chunk version of 0");
    if ((off & 3u) || off < prev_end || len > total || off > total - len) return bbad(&b, "a chunk out of place");
    /* The padding before a chunk is zero: no CRC covers it. */
    while (prev_end < off) {
      uint8_t z[4];
      const uint32_t m = off - prev_end < 4u ? off - prev_end : 4u, k2 = 0;
      if (rd(rctx, prev_end, z, m) != m) return bbad(&b, "a chunk past the file");
      for (k = k2; k < m; ++k) {
        if (z[k]) return bbad(&b, "padding that is not zero");
      }
      prev_end += m;
    }
    prev_end = off + len;
    if (!skip_crc) {
      for (k = 0; k < len;) {
        uint8_t t[64];
        const uint32_t m = len - k < 64u ? len - k : 64u;
        if (rd(rctx, off + k, t, m) != m) return bbad(&b, "a chunk past the file");
        crc = fm1_state_crc32(crc, t, m);
        k += m;
      }
      if (crc != get32(e + 16)) return bbad(&b, "a chunk's CRC does not match");
    }
  }
  if (prev_end != total) return bbad(&b, "the last chunk does not end the file");
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_HEAD;
  r.u.head.kind = b.kind;
  r.u.head.major = FM1_STATE_MAJOR;
  r.u.head.minor = rep->minor;
  if (!bemit(&b, &r)) return 0;
  for (i = 0; i < count; ++i) {
    cs_t c;
    fm1_inflate_t z;
    uint32_t off, len;
    int tag, ok;
    acc_t a;
    if (rd(rctx, hdr + i * esz, e, 20) != 20u) return bbad(&b, "a directory past the file");
    tag = tag_of(e);
    off = get32(e + 8);
    len = get32(e + 12);
    if (!tag) {
      ++rep->skipped;
      continue;
    }
    memset(&c, 0, sizeof(c));
    c.rd = rd;
    c.rctx = rctx;
    c.off = off;
    c.end = off + len;
    c.left = len;
    if (get16(e + 6) & 1u) {
      uint8_t u[4];
      uint32_t unpacked;
      if (len < 4u || rd(rctx, off, u, 4) != 4u) return bbad(&b, "a deflated chunk without its length");
      unpacked = get32(u);
      if (unpacked > kCap[tag]) return brefuse(&b, FM1_STATE_TOO_BIG, "a chunk past its cap");
      fm1_inflate_init(&z, cs_src, &c, off + 4u, len - 4u, unpacked);
      c.deflated = 1;
      c.z = &z;
      c.left = unpacked;
    } else if (len > kCap[tag]) {
      return brefuse(&b, FM1_STATE_TOO_BIG, "a chunk past its cap");
    }
    memset(&a, 0, sizeof(a));
    switch (tag) {
      case CH_INFO:
        ok = kv_each(&b, &c, info_kv, NULL);
        break;
      case CH_PROJ:
        a.r.type = FM1_REC_SESSION;
        ok = kv_each(&b, &c, proj_kv, &a);
        if (ok) {
          a.r.u.session.has_key = (uint8_t)(a.has == 3u);
          if (!a.r.u.session.has_key) a.r.u.session.root = 0, a.r.u.session.scale[0] = '\0';
          ok = bemit(&b, &a.r);
        }
        break;
      case CH_UNIT: ok = read_unit(&b, &c); break;
      case CH_DX7V: ok = read_dx7v(&b, &c); break;
      case CH_MODR: ok = read_modr(&b, &c); break;
      case CH_SEQS: ok = read_lines(&b, &c, FM1_LINES_SET); break;
      case CH_CLIP: ok = read_lines(&b, &c, FM1_LINES_CLIP); break;
      case CH_VIEW:
        a.r.type = FM1_REC_VIEW;
        ok = kv_each(&b, &c, view_kv, &a);
        if (ok && !a.has) ok = bbad(&b, "a view needs its mode");
        if (ok) ok = bemit(&b, &a.r);
        break;
      case CH_SETG: ok = kv_each(&b, &c, setg_kv, NULL); break;
      default: ok = 0; break;
    }
    if (!ok) {
      if (!b.stop) bbad(&b, "a chunk that cannot be read");
      return 0;
    }
    /* A newer chunk version may add a tail an older reader skips. */
    if (c.left) {
      if (get16(e + 4) == 1u) return bbad(&b, "a chunk longer than its contents");
      if (!cs_skip(&c, c.left)) return bbad(&b, "a chunk ends early");
    }
    if (c.deflated && !fm1_inflate_done(&z)) {
      uint8_t t;
      if (fm1_inflate_read(&z, &t, 1) != 0 || !fm1_inflate_done(&z)) return bbad(&b, "a deflated chunk that does not end");
    }
  }
  /* What each kind needs, as the JSON reader needs it. */
  if ((b.kind == FM1_STATE_PROJECT || b.kind == FM1_STATE_SOUND) && !((b.units_seen[0]) & 1u)) {
    return bbad(&b, b.kind == FM1_STATE_PROJECT ? "a project needs its Sound 1" : "a sound file needs its sound");
  }
  if (b.kind == FM1_STATE_MODS && !b.mod_seen) return bbad(&b, "a mod rack needs its mod chunk");
  if ((b.kind == FM1_STATE_CLIP || b.kind == FM1_STATE_SET) && !b.lines_seen) {
    return bbad(&b, "a clip or a set needs its lines");
  }
  memset(&r, 0, sizeof(r));
  r.type = FM1_REC_END;
  return bemit(&b, &r);
}
