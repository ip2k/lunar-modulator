/* seq_script.c -- the verb-script reader and event-log writer (seq_script.h).
 * Desktop host code. MIT licence. */
#include "seq_script.h"

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

/* "rt XX", XX one of F8 FA FB FC (either case): the status byte, else 0. */
static unsigned realtime_status(const char *ops) {
  unsigned v = 0;
  int i;
  if (strncmp(ops, "rt", 2) != 0 || (ops[2] != ' ' && ops[2] != '\t')) return 0;
  ops += 3;
  while (*ops == ' ' || *ops == '\t') ++ops;
  for (i = 0; i < 2; ++i) {
    const char c = ops[i];
    const unsigned d = c >= '0' && c <= '9' ? (unsigned)(c - '0')
                       : c >= 'a' && c <= 'f' ? (unsigned)(c - 'a' + 10)
                       : c >= 'A' && c <= 'F' ? (unsigned)(c - 'A' + 10) : 16u;
    if (d > 15) return 0;
    v = v * 16u + d;
  }
  ops += 2;
  while (*ops == ' ' || *ops == '\t') ++ops;
  if (*ops) return 0;
  return v == 0xF8 || v == 0xFA || v == 0xFB || v == 0xFC ? v : 0;
}

uint32_t fm1_script_apply(fm1_seq_t *s, const char *ops, fm1_seq_ev_t *out, uint32_t cap) {
  const unsigned rt = realtime_status(ops);
  if (rt) return fm1_seq_realtime_in(s, 0, (uint8_t)rt, out, cap);
  return fm1_seq_apply_text(s, ops, strlen(ops), out, cap);
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
        !realtime_status(after)) {
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
