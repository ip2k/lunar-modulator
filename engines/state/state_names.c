/* state_names.c -- names to uids and back, over a build's registries
 * (fm1_state.h, fm1_state_names_t; notes/2026-10-06-state-files.md §9).
 * Also the small shared pieces: kind names, caps, report, CRC-32, the
 * record tee. C99, no heap, no stdio. MIT licence. */
#include "fm1_state.h"

#include <string.h>

const uint32_t fm1_state_kind_cap[FM1_STATE_KINDS] = {
  0, FM1_STATE_CAP_PROJECT, FM1_STATE_CAP_SOUND, FM1_STATE_CAP_FX, FM1_STATE_CAP_MODS,
  FM1_STATE_CAP_CLIP, FM1_STATE_CAP_SETTINGS, FM1_STATE_CAP_MOVY1, FM1_STATE_CAP_SYX
};

static const char *const kKinds[FM1_STATE_KINDS] = {
  NULL, "project", "sound", "fx", "mods", "clip", "settings", "set", "dx7bank"
};

const char *fm1_state_kind_name(unsigned kind) {
  return kind < FM1_STATE_KINDS ? kKinds[kind] : NULL;
}

unsigned fm1_state_kind_code(const char *name, size_t n) {
  unsigned k;
  for (k = 1; k < FM1_STATE_KINDS; ++k) {
    if (strlen(kKinds[k]) == n && memcmp(kKinds[k], name, n) == 0) return k;
  }
  return FM1_STATE_KIND_NONE;
}

const char *fm1_state_code_name(unsigned code) {
  static const char *const kCodes[FM1_STATE_CODES] = {
    "OK", "NOT_LUNAR", "TOO_NEW", "UNKNOWN", "RATE", "RAM", "NO_ROOM", "TOO_BIG", "BAD", "STOPPED"
  };
  return code < FM1_STATE_CODES ? kCodes[code] : "?";
}

void fm1_state_report_init(fm1_state_report_t *rep) {
  memset(rep, 0, sizeof(*rep));
}

uint32_t fm1_state_crc32(uint32_t crc, const uint8_t *b, size_t n) {
  size_t i;
  int k;
  crc = ~crc;
  for (i = 0; i < n; ++i) {
    crc ^= b[i];
    for (k = 0; k < 8; ++k) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

int fm1_state_tee(void *t, const fm1_rec_t *r) {
  const fm1_state_tee_t *tee = (const fm1_state_tee_t *)t;
  if (tee->a && !tee->a(tee->actx, r)) return 0;
  if (tee->b && !tee->b(tee->bctx, r)) return 0;
  return 1;
}

int fm1_state_sniff(const uint8_t *b, size_t n) {
  static const uint8_t kMagic[8] = { 0x89, 'L', 'u', 'n', 'a', 'r', 0x0D, 0x0A };
  size_t i = 0;
  if (n >= 8 && memcmp(b, kMagic, 8) == 0) return 1;
  if (n >= 2 && b[0] == 0xF0 && b[1] == 0x43) return 4;
  if (n == 4096) return 4;
  while (i < n && (b[i] == ' ' || b[i] == '\t' || b[i] == '\r' || b[i] == '\n')) ++i;
  if (i < n && b[i] == '{') return 2;
  if (n - i >= 5 && memcmp(b + i, "movy1", 5) == 0) return 3;
  return 0;
}

/* ---- Lookups ------------------------------------------------------------------ */
static int same_ci(const char *a, const char *b, size_t n) {
  size_t i;
  for (i = 0; i < n; ++i) {
    unsigned char x = (unsigned char)a[i], y = (unsigned char)b[i];
    if (!y) return 0;
    if (x >= 'A' && x <= 'Z') x = (unsigned char)(x + 32);
    if (y >= 'A' && y <= 'Z') y = (unsigned char)(y + 32);
    if (x != y) return 0;
  }
  return b[n] == '\0';
}

static int same(const char *a, const char *b, size_t n) {
  return strlen(b) == n && memcmp(a, b, n) == 0;
}

const fm1_engine_t *fm1_state_engine(const fm1_state_names_t *nm, unsigned role, const char *id) {
  size_t i;
  if (!nm || !id || !*id) return NULL;
  if (role == FM1_ROLE_MFX) {
    for (i = 0; i < nm->n_mfx; ++i) {
      if (strcmp(nm->mfx[i]->engine.id, id) == 0) return &nm->mfx[i]->engine;
    }
    return NULL;
  }
  for (i = 0; i < nm->n_engines; ++i) {
    const fm1_engine_t *e = nm->engines[i];
    if (strcmp(e->id, id) != 0) continue;
    if (role == FM1_ROLE_SOUND ? e->kind == FM1_KIND_SOUND : e->kind == FM1_KIND_AUDIO_FX) return e;
    return NULL;
  }
  return NULL;
}

const fm1_mod_kind_t *fm1_state_kind(const fm1_state_names_t *nm, const char *id) {
  size_t i;
  if (!nm || !id || !*id) return NULL;
  for (i = 0; i < nm->n_kinds; ++i) {
    if (strcmp(nm->kinds[i]->id, id) == 0) return nm->kinds[i];
  }
  return NULL;
}

/* The owner's old names (fm1_known.h): a parameter's (entry -1) or one of
 * its entries'. Returns the alias row's uid and entry through *a, or NULL. */
static const fm1_alias_t *alias_find(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                                     const char *key, size_t len, int entry_of, uint16_t uid) {
  size_t a;
  if (!nm || !nm->aliases || !owner || !owner_kind) return NULL;
  for (a = 0; a < nm->n_aliases; ++a) {
    const fm1_alias_t *al = &nm->aliases[a];
    if (!al->name || al->owner != owner_kind || strcmp(al->id, owner) != 0) continue;
    if (entry_of ? (al->entry < 0 || al->uid != uid) : al->entry >= 0) continue;
    if (same_ci(key, al->name, len)) return al;
  }
  return NULL;
}

int fm1_state_param_find(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                         const fm1_param_t *p, unsigned n, const char *key, size_t len) {
  unsigned i;
  const fm1_alias_t *al;
  if (len >= 2 && key[0] == '#') {
    unsigned uid = 0;
    size_t k;
    if (key[1] == '0') return -1;
    for (k = 1; k < len; ++k) {
      if (key[k] < '0' || key[k] > '9' || k > 4) return -1;
      uid = uid * 10u + (unsigned)(key[k] - '0');
    }
    for (i = 0; i < n; ++i) {
      if (p[i].uid == uid) return (int)i;
    }
    return -1;
  }
  for (i = 0; i < n; ++i) {
    if (same(key, p[i].name, len)) return (int)i;
  }
  for (i = 0; i < n; ++i) {
    if (same_ci(key, p[i].name, len)) return (int)i;
  }
  for (i = 0; i < n; ++i) {
    if (p[i].abbr && same_ci(key, p[i].abbr, len)) return (int)i;
  }
  al = alias_find(nm, owner_kind, owner, key, len, 0, 0);
  if (al) {
    for (i = 0; i < n; ++i) {
      if (p[i].uid == al->uid) return (int)i;
    }
  }
  return -1;
}

int fm1_state_entry_find(const fm1_state_names_t *nm, unsigned owner_kind, const char *owner,
                         const fm1_param_t *p, const char *s, size_t len) {
  int k, count;
  const fm1_alias_t *al;
  if (p->type != FM1_PARAM_ENUM || !p->enum_names) return -1;
  count = (int)(p->max - p->min) + 1;
  for (k = 0; k < count; ++k) {
    if (same(s, p->enum_names[k], len)) return k;
  }
  for (k = 0; k < count; ++k) {
    if (same_ci(s, p->enum_names[k], len)) return k;
  }
  al = alias_find(nm, owner_kind, owner, s, len, 1, p->uid);
  return al && al->entry < count ? al->entry : -1;
}

/* Engine API v4: a kit's Pad carries FM1_PARAM_FOCUS and each per-pad value
 * FM1_PARAM_PER_FOCUS (Drums and Sophie today); the flags count only in an
 * engine that has a FOCUS parameter. */
int fm1_state_param_focus(const fm1_engine_t *e, unsigned index) {
  const fm1_param_t *p;
  if (!e || index >= e->n_params) return 0;
  p = &e->params[index];
  if (p->flags & FM1_PARAM_FOCUS) return 1;
  if ((p->flags & FM1_PARAM_PER_FOCUS) && fm1_engine_focus(e) >= 0) return 2;
  return 0;
}

void fm1_state_note_unknown(const fm1_state_names_t *nm, const fm1_rec_t *r, fm1_state_report_t *rep) {
  const char *id;
  size_t n;
  const fm1_known_id_t *k;
  if (r->type == FM1_REC_UNIT) {
    if (!r->u.unit.id[0] || fm1_state_engine(nm, r->role, r->u.unit.id)) return;
  } else if (r->type == FM1_REC_MODULE) {
    if (fm1_state_kind(nm, r->u.unit.id)) return;
  } else {
    return;
  }
  if (rep->unknown++) return;
  id = r->u.unit.id;
  for (n = 0; n < sizeof(r->u.unit.id) && n + 1u < sizeof(rep->name) && id[n]; ++n) {
    const unsigned char c = (unsigned char)id[n];
    rep->name[n] = (char)(c >= 0x20 && c < 0x7F ? c : '?');
  }
  rep->name[n] = '\0';
  k = nm && nm->known ? nm->known(rep->name) : NULL;
  rep->known[0] = '\0';
  if (k && k->reason) {
    n = strlen(k->reason);
    if (n >= sizeof(rep->known)) n = sizeof(rep->known) - 1u;
    memcpy(rep->known, k->reason, n);
    rep->known[n] = '\0';
  }
}

const char *fm1_state_known_text(const char *reason) {
  if (!reason || !*reason) return "";
  if (strcmp(reason, "gpl") == 0) return "in the GPL build only";
  if (strcmp(reason, "planned") == 0) return "not built yet";
  if (strcmp(reason, "retired") == 0) return "retired";
  return "";
}

int fm1_state_source_find(const fm1_state_names_t *nm, const char *s, size_t len) {
  unsigned id;
  if (!nm || !nm->source) return -1;
  for (id = 0; id < 64u; ++id) {
    const fm1_mod_source_info_t *si = nm->source(id);
    if (si && same(s, si->name, len)) return (int)id;
  }
  return -1;
}

int fm1_state_port_find(const fm1_port_t *ports, unsigned n, const char *s, size_t len) {
  unsigned i;
  if (len == 1 && s[0] >= '1' && s[0] <= '8') {
    const unsigned k = (unsigned)(s[0] - '1');
    return k < n ? (int)k : -1;
  }
  for (i = 0; i < n; ++i) {
    if (same(s, ports[i].name, len)) return (int)i;
  }
  for (i = 0; i < n; ++i) {
    if (same_ci(s, ports[i].name, len)) return (int)i;
  }
  return -1;
}
