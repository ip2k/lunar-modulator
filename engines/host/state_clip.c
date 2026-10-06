/* state_clip.c -- a clip file's lines into a set and out of one
 * (state_clip.h; notes/2026-10-06-state-files.md §7.3, §10.2). Host code:
 * malloc and stdio. MIT licence. */
#include "state_clip.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  char **v;
  size_t n, cap;
} lines_t;

static int push(lines_t *l, const char *s, size_t n) {
  char *c;
  if (l->n == l->cap) {
    size_t cap = l->cap ? l->cap * 2 : 64;
    char **v = (char **)realloc(l->v, cap * sizeof(char *));
    if (!v) return 0;
    l->v = v;
    l->cap = cap;
  }
  c = (char *)malloc(n + 1);
  if (!c) return 0;
  memcpy(c, s, n);
  c[n] = '\0';
  l->v[l->n++] = c;
  return 1;
}

static void free_lines(lines_t *l) {
  size_t i;
  for (i = 0; i < l->n; ++i) free(l->v[i]);
  free(l->v);
  memset(l, 0, sizeof(*l));
}

static int split(const char *text, size_t n, lines_t *out) {
  size_t i, start = 0;
  for (i = 0; i < n; ++i) {
    if (text[i] == '\n') {
      if (!push(out, text + start, i - start)) return 0;
      start = i + 1;
    }
  }
  return start == n || push(out, text + start, n - start);
}

/* The key, track and slot of a line ("cl 3 1 ..." -> "cl", 3, 1); -1s
 * when it has none. */
static void parts(const char *line, char key[4], int *t, int *s) {
  int a = -1, b = -1;
  key[0] = '\0';
  *t = *s = -1;
  if (sscanf(line, "%3s %d %d", key, &a, &b) >= 2) {
    *t = a;
    *s = b;
  }
}

static int is_clip_key(const char *k) {
  return !strcmp(k, "cl") || !strcmp(k, "cp") || !strcmp(k, "lk") || !strcmp(k, "tg");
}

static void fail(char *err, size_t cap, const char *what) {
  if (err && cap) snprintf(err, cap, "%s", what);
}

/* The label of an au line ("au 0 2 64 synth:Cutoff" -> lane 2, base 64,
 * "synth:Cutoff"). */
static int au_parts(const char *line, int *lane, int *base, const char **label) {
  int t, n = 0;
  if (sscanf(line, "au %d %d %d %n", &t, lane, base, &n) < 3 || !n) return 0;
  *label = line + n;
  return 1;
}

char *fm1_state_clip_into(const char *set, size_t n, const char *const *clip, size_t nclip, unsigned track,
                          unsigned slot, char *err, size_t errcap) {
  lines_t in = { NULL, 0, 0 }, out = { NULL, 0, 0 }, lanes = { NULL, 0, 0 };
  int lane_map[8];
  unsigned used = 0;
  size_t i, total = 0, at = 0;
  char *text = NULL;
  int ok = 1;
  for (i = 0; i < 8; ++i) lane_map[i] = -1;
  if (track > 15 || slot > 7) { fail(err, errcap, "a track 1-16 and a slot 1-8"); return NULL; }
  if (!split(set, n, &in)) { fail(err, errcap, "out of memory"); return NULL; }
  /* The track's lanes as they are. */
  for (i = 0; i < in.n; ++i) {
    char k[4];
    int t, s, lane, base;
    const char *label;
    parts(in.v[i], k, &t, &s);
    if (!strcmp(k, "au") && t == (int)track && au_parts(in.v[i], &lane, &base, &label) && lane >= 0 && lane < 8) {
      used |= 1u << lane;
    }
  }
  /* The clip's lanes: the same label on the track, else a free lane. */
  for (i = 0; i < nclip && ok; ++i) {
    int lane, base;
    const char *label;
    size_t j;
    if (strncmp(clip[i], "au ", 3) != 0) continue;
    if (!au_parts(clip[i], &lane, &base, &label) || lane < 0 || lane > 7) { ok = 0; break; }
    for (j = 0; j < in.n; ++j) {
      char k[4];
      int t, s, l2, b2;
      const char *lab2;
      parts(in.v[j], k, &t, &s);
      if (!strcmp(k, "au") && t == (int)track && au_parts(in.v[j], &l2, &b2, &lab2) && !strcmp(lab2, label)) {
        lane_map[lane] = l2;
        break;
      }
    }
    if (lane_map[lane] < 0) {
      int f;
      for (f = 0; f < 8 && ((used >> f) & 1u); ++f) {}
      if (f == 8) {
        fail(err, errcap, "no free lane on that track for the clip's locks (NO_ROOM)");
        ok = 0;
        break;
      }
      used |= 1u << f;
      lane_map[lane] = f;
      {
        char line[96];
        snprintf(line, sizeof(line), "au %u %d %d %s", track, f, base, label);
        if (!push(&lanes, line, strlen(line))) ok = 0;
      }
    }
  }
  /* The set less the slot's old lines, then the clip's, renumbered. */
  for (i = 0; i < in.n && ok; ++i) {
    char k[4];
    int t, s;
    parts(in.v[i], k, &t, &s);
    if (is_clip_key(k) && t == (int)track && s == (int)slot) continue;
    if (!push(&out, in.v[i], strlen(in.v[i]))) ok = 0;
  }
  for (i = 0; i < lanes.n && ok; ++i) {                /* the new lanes, after the set's */
    if (!push(&out, lanes.v[i], strlen(lanes.v[i]))) ok = 0;
  }
  for (i = 0; i < nclip && ok; ++i) {
    char k[4];
    int t, s;
    const char *rest;
    char *line;
    size_t m;
    parts(clip[i], k, &t, &s);
    if (!is_clip_key(k)) continue;
    rest = clip[i] + 7;                                  /* past "xx 0 0 " */
    m = strlen(rest) * 2 + 32;
    line = (char *)malloc(m);
    if (!line) { ok = 0; break; }
    if (!strcmp(k, "lk")) {                              /* lanes renumbered */
      size_t o = (size_t)snprintf(line, m, "lk %u %u ", track, slot);
      const char *p = rest;
      while (*p) {
        int lane = -1, step, val, used_n = 0;
        if (sscanf(p, "%d:%d:%d%n", &lane, &step, &val, &used_n) != 3) { ok = 0; break; }
        o += (size_t)snprintf(line + o, m - o, "%s%d:%d:%d", p == rest ? "" : ";",
                              lane >= 0 && lane < 8 && lane_map[lane] >= 0 ? lane_map[lane] : lane, step, val);
        p += used_n;
        if (*p == ';') ++p;
      }
    } else {
      snprintf(line, m, "%s %u %u %s", k, track, slot, rest);
    }
    if (ok && !push(&out, line, strlen(line))) ok = 0;
    free(line);
  }
  if (ok) {
    for (i = 0; i < out.n; ++i) total += strlen(out.v[i]) + 1;
    text = (char *)malloc(total + 1);
    if (!text) ok = 0;
  }
  if (ok) {
    for (i = 0; i < out.n; ++i) {
      const size_t m = strlen(out.v[i]);
      memcpy(text + at, out.v[i], m);
      at += m;
      text[at++] = '\n';
    }
    text[at] = '\0';
  } else if (err && errcap && !err[0]) {
    fail(err, errcap, "a clip line that cannot be read");
  }
  free_lines(&in);
  free_lines(&out);
  free_lines(&lanes);
  return ok ? text : NULL;
}

char **fm1_state_clip_from(const char *set, size_t n, unsigned track, unsigned slot, size_t *count) {
  lines_t in = { NULL, 0, 0 }, out = { NULL, 0, 0 };
  unsigned lanes = 0;
  size_t i;
  int has = 0;
  *count = 0;
  if (!split(set, n, &in)) return NULL;
  for (i = 0; i < in.n; ++i) {          /* the lanes its locks use */
    char k[4];
    int t, s;
    parts(in.v[i], k, &t, &s);
    if (!strcmp(k, "lk") && t == (int)track && s == (int)slot) {
      const char *p = strchr(strchr(strchr(in.v[i], ' ') + 1, ' ') + 1, ' ');
      while (p && *p) {
        int lane, step, val, used_n = 0;
        if (*p == ' ' || *p == ';') { ++p; continue; }
        if (sscanf(p, "%d:%d:%d%n", &lane, &step, &val, &used_n) != 3) break;
        if (lane >= 0 && lane < 8) lanes |= 1u << lane;
        p += used_n;
      }
    }
    if (!strcmp(k, "cl") && t == (int)track && s == (int)slot) has = 1;
  }
  if (!has) {
    free_lines(&in);
    return NULL;
  }
  for (i = 0; i < in.n; ++i) {
    char k[4];
    int t, s, lane, base;
    const char *label;
    parts(in.v[i], k, &t, &s);
    if (!strcmp(k, "au") && t == (int)track && au_parts(in.v[i], &lane, &base, &label) && lane >= 0 &&
        lane < 8 && ((lanes >> lane) & 1u)) {
      char line[96];
      snprintf(line, sizeof(line), "au 0 %d %d %s", lane, base, label);
      push(&out, line, strlen(line));
    }
  }
  for (i = 0; i < in.n; ++i) {
    char k[4];
    int t, s;
    parts(in.v[i], k, &t, &s);
    if (is_clip_key(k) && t == (int)track && s == (int)slot) {
      const char *rest = strchr(strchr(strchr(in.v[i], ' ') + 1, ' ') + 1, ' ');
      char *line = (char *)malloc(strlen(in.v[i]) + 8);
      if (!line) break;
      sprintf(line, "%s 0 0%s", k, rest ? rest : "");
      push(&out, line, strlen(line));
      free(line);
    }
  }
  free_lines(&in);
  *count = out.n;
  return out.v;
}

void fm1_state_clip_free(char **lines, size_t count) {
  size_t i;
  for (i = 0; i < count; ++i) free(lines[i]);
  free(lines);
}
