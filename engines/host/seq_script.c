/* seq_script.c -- the verb-script reader and event-log writer (seq_script.h).
 * Desktop host code. MIT licence. */
#include "seq_script.h"

#include "fm1_seq_host.h"

#include <stdlib.h>
#include <string.h>

char *fm1_read_file(const char *path, size_t *len) {
  FILE *f = fopen(path, "rb");
  char *buf;
  long n;
  if (!f) return NULL;
  if (fseek(f, 0, SEEK_END) != 0 || (n = ftell(f)) < 0 || fseek(f, 0, SEEK_SET) != 0) {
    fclose(f);
    return NULL;
  }
  buf = (char *)malloc((size_t)n + 1u);
  if (!buf) {
    fclose(f);
    return NULL;
  }
  if (fread(buf, 1, (size_t)n, f) != (size_t)n) {
    free(buf);
    fclose(f);
    return NULL;
  }
  fclose(f);
  buf[n] = '\0';
  if (len) *len = (size_t)n;
  return buf;
}

static int parse_u64(const char *p, const char **end, uint64_t *v) {
  uint64_t x = 0;
  const char *q = p;
  while (*q >= '0' && *q <= '9') {
    const unsigned d = (unsigned)(*q - '0');
    if (x > (UINT64_MAX - d) / 10u) return 0;
    x = x * 10u + d;
    ++q;
  }
  if (q == p) return 0;
  *v = x;
  *end = q;
  return 1;
}

/* The line's realtime input or its ops, through the host bridge
 * (fm1_seq_host.h), as every host applies them. */
uint32_t fm1_script_apply(fm1_seq_t *s, const char *ops, fm1_seq_ev_t *out, uint32_t cap) {
  return fm1_seq_apply_line(s, ops, strlen(ops), out, cap);
}

static void header(fm1_script_t *s, char *line) {
  char *p = line + 2;
  while (*p) {
    char *key, *eq;
    uint64_t v;
    const char *after;
    while (*p == ' ' || *p == '\t') ++p;
    if (!*p) break;
    key = p;
    while (*p && *p != ' ' && *p != '\t') ++p;
    if (*p) *p++ = '\0';
    eq = strchr(key, '=');
    if (!eq) continue;
    *eq = '\0';
    if (!parse_u64(eq + 1, &after, &v) || *after) continue;
    if (strcmp(key, "rate") == 0) { s->rate = (uint32_t)v; s->has_rate = 1; }
    else if (strcmp(key, "block") == 0) { s->block = (uint32_t)v; s->has_block = 1; }
    else if (strcmp(key, "tracks") == 0) { s->tracks = (uint8_t)v; s->has_tracks = 1; }
    else if (strcmp(key, "end") == 0) { s->end = v; s->has_end = 1; }
  }
}

static int by_frame(const void *a, const void *b) {
  const fm1_script_cmd_t *x = (const fm1_script_cmd_t *)a, *y = (const fm1_script_cmd_t *)b;
  if (x->frame != y->frame) return x->frame < y->frame ? -1 : 1;
  return x->line < y->line ? -1 : (x->line > y->line ? 1 : 0);
}

int fm1_script_load(const char *path, fm1_script_t *s, char *err, size_t errlen) {
  size_t len, cap = 64, lineno = 0;
  char *p, *eol;
  memset(s, 0, sizeof(*s));
  s->rate = 44118;
  s->block = 128;
  s->tracks = 8;
  s->text = fm1_read_file(path, &len);
  if (!s->text) {
    snprintf(err, errlen, "cannot read %s", path);
    return 0;
  }
  s->cmds = (fm1_script_cmd_t *)malloc(cap * sizeof(*s->cmds));
  if (!s->cmds) return 0;
  for (p = s->text; p && *p; p = eol) {
    char *q;
    uint64_t frame;
    const char *after;
    int snap;
    ++lineno;
    eol = strchr(p, '\n');
    if (eol) *eol++ = '\0';
    q = p + strlen(p);
    while (q > p && (q[-1] == '\r' || q[-1] == ' ' || q[-1] == '\t')) *--q = '\0';
    while (*p == ' ' || *p == '\t') ++p;
    if (!*p) continue;
    if (p[0] == '#' && !(p[1] == '?' && p[2] == '@')) {
      if (p[1] == '!') header(s, p);
      continue;
    }
    snap = p[0] == '#';
    if (snap) p += 2;
    if (p[0] != '@' || !parse_u64(p + 1, &after, &frame) ||
        (*after && *after != ' ' && *after != '\t')) {
      snprintf(err, errlen, "%s:%zu: expected '@<frame> <ops>'", path, lineno);
      return 0;
    }
    while (*after == ' ' || *after == '\t') ++after;
    if (!snap && strncmp(after, "rt", 2) == 0 && (after[2] == ' ' || after[2] == '\t') &&
        !fm1_seq_realtime_status(after, strlen(after))) {
      snprintf(err, errlen, "%s:%zu: expected 'rt F8|FA|FB|FC'", path, lineno);
      return 0;
    }
    if (s->n == cap) {
      fm1_script_cmd_t *grown;
      cap *= 2;
      grown = (fm1_script_cmd_t *)realloc(s->cmds, cap * sizeof(*s->cmds));
      if (!grown) return 0;
      s->cmds = grown;
    }
    s->cmds[s->n].frame = frame;
    s->cmds[s->n].ops = after;
    s->cmds[s->n].line = lineno;
    s->cmds[s->n].snap = snap;
    ++s->n;
  }
  qsort(s->cmds, s->n, sizeof(*s->cmds), by_frame);
  return 1;
}

void fm1_script_free(fm1_script_t *s) {
  free(s->cmds);
  free(s->text);
  memset(s, 0, sizeof(*s));
}

void fm1_script_log_event(FILE *f, uint64_t block, uint64_t block_start, const fm1_seq_ev_t *e) {
  static const char *const kKind[] = { "?", "on", "off", "cc", "click", "start", "stop", "clock" };
  const char *kind = e->kind < 8 ? kKind[e->kind] : "?";
  fprintf(f, "{\"block\":%llu,\"frame\":%llu,\"tick\":%lu,\"kind\":\"%s\",\"track\":",
          (unsigned long long)block, (unsigned long long)(block_start + e->frame),
          (unsigned long)e->tick, kind);
  if (e->track == FM1_SEQ_NONE) fputs("null", f);
  else fprintf(f, "%u", (unsigned)e->track);
  switch (e->kind) {
  case FM1_SEQ_EV_NOTE_ON:
    fprintf(f, ",\"a\":%u,\"b\":%u}\n", (unsigned)e->a, (unsigned)e->b);
    break;
  case FM1_SEQ_EV_NOTE_OFF:
    fprintf(f, ",\"a\":%u,\"b\":null}\n", (unsigned)e->a);
    break;
  case FM1_SEQ_EV_LOCK:
    fprintf(f, ",\"a\":%u,\"b\":%u}\n", (unsigned)(FM1_SEQ_LOCK_CC + e->a), (unsigned)e->b);
    break;
  case FM1_SEQ_EV_CLICK:
    fprintf(f, ",\"a\":%u,\"b\":null}\n", (unsigned)e->a);
    break;
  default:
    fputs(",\"a\":null,\"b\":null}\n", f);
    break;
  }
}

/* ---- Typed commands as text (fm1_seq_cmd_format) --------------------------
 * The names are seq_cmd.c's, by verb; the round-trip check in
 * tests/test_seq_ui.py (fm1-sim-render --format-check) parses every one
 * back, so this table cannot drift from the parser unnoticed. */
static const char *const kVerbName[FM1_SEQ_V_COUNT] = {
  [FM1_SEQ_V_UNKNOWN] = "?",
  [FM1_SEQ_V_PLAY] = "play", [FM1_SEQ_V_STOP] = "stop", [FM1_SEQ_V_LINK] = "link",
  [FM1_SEQ_V_MINJECT] = "minject", [FM1_SEQ_V_BPM] = "bpm", [FM1_SEQ_V_SWING] = "swing",
  [FM1_SEQ_V_WATCH] = "watch", [FM1_SEQ_V_WLANE] = "wlane", [FM1_SEQ_V_TDRUM] = "tdrum",
  [FM1_SEQ_V_MUTE] = "mute", [FM1_SEQ_V_PMUTE] = "pmute", [FM1_SEQ_V_PSOLO] = "psolo",
  [FM1_SEQ_V_TOG] = "tog", [FM1_SEQ_V_EVEL] = "evel", [FM1_SEQ_V_ELEN] = "elen",
  [FM1_SEQ_V_ENUDGE] = "enudge", [FM1_SEQ_V_ETRN] = "etrn", [FM1_SEQ_V_HOLD] = "hold",
  [FM1_SEQ_V_SLEN] = "slen", [FM1_SEQ_V_CLEN] = "clen", [FM1_SEQ_V_CSCL] = "cscl",
  [FM1_SEQ_V_CTR] = "ctr", [FM1_SEQ_V_EPROB] = "eprob", [FM1_SEQ_V_ECOND] = "econd",
  [FM1_SEQ_V_EINV] = "einv", [FM1_SEQ_V_REC] = "rec", [FM1_SEQ_V_CAP] = "cap",
  [FM1_SEQ_V_CAPCLR] = "capclr", [FM1_SEQ_V_CAPSEL] = "capsel",
  [FM1_SEQ_V_CAPDONE] = "capdone", [FM1_SEQ_V_METRO] = "metro", [FM1_SEQ_V_CQ] = "cq",
  [FM1_SEQ_V_DQ] = "dq", [FM1_SEQ_V_NON] = "non", [FM1_SEQ_V_NOF] = "nof",
  [FM1_SEQ_V_DEL] = "del", [FM1_SEQ_V_CLIPDUP] = "clipdup", [FM1_SEQ_V_CLIPDEL] = "clipdel",
  [FM1_SEQ_V_CLIPSEL] = "clipsel", [FM1_SEQ_V_LAUNCH] = "launch", [FM1_SEQ_V_SONG] = "song",
  [FM1_SEQ_V_SONGADD] = "songadd", [FM1_SEQ_V_STOPTRK] = "stoptrk",
  [FM1_SEQ_V_CLIPCOPY] = "clipcopy", [FM1_SEQ_V_CLIPPASTE] = "clippaste",
  [FM1_SEQ_V_CLIPDELAT] = "clipdelat", [FM1_SEQ_V_CPY] = "cpy", [FM1_SEQ_V_PST] = "pst",
  [FM1_SEQ_V_CPYCLR] = "cpyclr", [FM1_SEQ_V_ADDP] = "addp", [FM1_SEQ_V_LOOP] = "loop",
  [FM1_SEQ_V_DBL] = "dbl", [FM1_SEQ_V_LTOG] = "ltog", [FM1_SEQ_V_ALABEL] = "alabel",
  [FM1_SEQ_V_ABASE] = "abase", [FM1_SEQ_V_ABASEQ] = "abaseq", [FM1_SEQ_V_ASET] = "aset",
  [FM1_SEQ_V_ACLR] = "aclr", [FM1_SEQ_V_ACLRS] = "aclrs", [FM1_SEQ_V_ACLRSTEP] = "aclrstep",
  [FM1_SEQ_V_ASETR] = "asetr", [FM1_SEQ_V_USNAP] = "usnap", [FM1_SEQ_V_USWAP] = "uswap",
  [FM1_SEQ_V_UCOMMIT] = "ucommit", [FM1_SEQ_V_UDROP] = "udrop", [FM1_SEQ_V_UCLR] = "uclr",
  [FM1_SEQ_V_ROUTE] = "route",
};

const char *fm1_seq_verb_name(unsigned v) { return v < FM1_SEQ_V_COUNT ? kVerbName[v] : NULL; }

/* Does `text` spell the integer v as a token fm1_seq_parse reads (an
 * optional sign and digits only)? */
static int spells(const char *text, int64_t v) {
  fm1_seq_cmd_t c;
  char op[2 + FM1_SEQ_LABEL_MAX];
  size_t n = strlen(text);
  if (!n || n >= FM1_SEQ_LABEL_MAX) return 0;
  memcpy(op, "? ", 2);
  memcpy(op + 2, text, n);
  /* As the first argument of an unknown verb: parsed, never applied. */
  return fm1_seq_parse(op, n + 2, &c) && (c.valid & 1u) && c.arg[0] == v;
}

size_t fm1_seq_cmd_format(const fm1_seq_cmd_t *c, char *buf, size_t cap) {
  char tmp[640];
  size_t len = 0;
  const char *name = fm1_seq_verb_name(c->verb);
  int n = snprintf(tmp, sizeof tmp, "%s", name ? name : "?");
  len = n > 0 ? (size_t)n : 0;
  for (unsigned i = 0; i < c->argc && i < FM1_SEQ_CMD_ARGS && len < sizeof tmp; ++i) {
    const int valid = (c->valid >> i) & 1u;
    if (i == 2 && c->text[0] && (!valid || spells(c->text, c->arg[2]))) {
      n = snprintf(tmp + len, sizeof tmp - len, " %s", c->text);
    } else if (valid) {
      n = snprintf(tmp + len, sizeof tmp - len, " %lld", (long long)c->arg[i]);
    } else {
      n = snprintf(tmp + len, sizeof tmp - len, " _");
    }
    if (n > 0) len += (size_t)n;
  }
  if (len >= sizeof tmp) len = sizeof tmp - 1u;
  if (cap) {
    const size_t m = len < cap - 1u ? len : cap - 1u;
    memcpy(buf, tmp, m);
    buf[m] = '\0';
  }
  return len;
}
