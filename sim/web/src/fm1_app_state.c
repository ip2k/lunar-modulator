/* fm1_app_state.c -- the virtual FM-1's state through the state core's
 * records: the collector (save) and the two-pass applier (check, load).
 * fm1_app_state.h has the rules. C99. MIT licence. */
#include "fm1_app_state.h"

#include "fm1_edit.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_state_mod.h"
#include "state_clip.h"

#define DX7_USER0 (FM1_APP_DX7_PATCHES - (int)FM1_DX7_USER_SLOTS)
#define SET_CAP FM1_STATE_CAP_MOVY1           /* a set's text: 53,208 B at most at 8 tracks */
#define JSON_CAP FM1_STATE_CAP_PROJECT        /* the largest JSON file */
/* The JSON writer's document (476,664 B on a 64-bit build) and, once the
 * JSON is written, the binary writer's file (284,920 B); never both at once,
 * so they share. Pass 1's rate check creates engines in it too. */
#define W_BYTES (480u * 1024u)
#define CLIP_LINES 512u

static unsigned char g_w[W_BYTES] FM1_APP_ALIGN16;
#define g_jw g_w
#define g_bw g_w
static char g_clip[FM1_STATE_CAP_CLIP + 2];
static char g_json[JSON_CAP + 1];
static uint32_t g_json_n;
static int g_json_over;
static uint8_t g_bin[FM1_STATE_BIN_MAX];
static uint32_t g_bin_n;
static int g_bin_over;
static char g_set[SET_CAP + 2];
static uint32_t g_set_n;
static int g_set_over;
static unsigned char g_seq_scratch[FM1_APP_SEQ_BYTES] FM1_APP_ALIGN16;

static const fm1_state_names_t *names(void) {
  static fm1_state_names_t nm;
  static int ready;
  if (!ready) {
    fm1_state_names_default(&nm);
    ready = 1;
  }
  return &nm;
}

static const char *const kScaleIds[FM1_KEY_SCALES] = {
  "major", "minor", "chromatic", "dorian", "phrygian", "lydian", "mixolydian", "locrian",
};

const char *fm1_app_scale_id(int scale) {
  return scale >= 0 && scale < FM1_KEY_SCALES ? kScaleIds[scale] : NULL;
}

int fm1_app_scale_of(const char *id) {
  for (int i = 0; i < FM1_KEY_SCALES; ++i) {
    if (strcmp(kScaleIds[i], id) == 0) return i;
  }
  return -1;
}

uint32_t fm1_app_state_mem_read(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
  const fm1_app_state_mem_t *m = (const fm1_app_state_mem_t *)ctx;
  if (off >= m->n) return 0;
  if (n > m->n - off) n = m->n - off;
  memcpy(buf, m->b + off, n);
  return n;
}

void fm1_app_load_opts_init(fm1_app_load_opts_t *o) {
  memset(o, 0, sizeof *o);
  o->into = 0;
}

static fm1_rec_t blank(unsigned type) {
  fm1_rec_t r;
  memset(&r, 0, sizeof r);
  r.type = (uint8_t)type;
  return r;
}

static float bits_f(uint32_t b) {
  float f;
  memcpy(&f, &b, sizeof f);
  return f;
}

/* The app unit a mod unit code names (the inverse of fm1_app_mod_unit), or -1. */
static int unit_of_code(unsigned code) {
  const unsigned c = fm1_mod_unit_canonical(code);
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (fm1_app_mod_unit(u) == (int)c) return u;
  }
  return -1;
}

static int unit_sound(int unit) {
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    if (fm1_app_sound_unit(k) == unit) return k;
  }
  return -1;
}

/* ============================== save ===================================== */

typedef struct col {
  fm1_rec_sink_t sink;
  void *ctx;
  int ok;
} col_t;

static void out(col_t *c, const fm1_rec_t *r) {
  if (c->ok && !c->sink(c->ctx, r)) c->ok = 0;
}

static void text_out(col_t *c, unsigned key, const char *s) {
  fm1_rec_t r = blank(FM1_REC_INFO);
  if (!s || !s[0]) return;
  r.piece = FM1_REC_FIRST | FM1_REC_LAST;
  r.u.info.key = (uint8_t)key;
  r.u.info.n = (uint16_t)strlen(s);
  r.u.info.s = s;
  out(c, &r);
}

static void head_out(col_t *c, unsigned kind) {
  fm1_rec_t r = blank(FM1_REC_HEAD);
  r.u.head.kind = (uint8_t)kind;
  r.u.head.major = FM1_STATE_MAJOR;
  r.u.head.minor = FM1_STATE_MINOR;
  out(c, &r);
  text_out(c, FM1_INFO_BY, "simulator");
}

static void param_out(col_t *c, const fm1_rec_t *unit, const fm1_param_t *p, unsigned focus, float v) {
  fm1_rec_t q = *unit;
  q.type = FM1_REC_PARAM;
  memset(&q.u, 0, sizeof q.u);
  q.u.param.uid = p->uid;
  q.u.param.focus = (uint8_t)focus;
  v = fm1_param_clamp(p, v);
  if (p->type == FM1_PARAM_ENUM) {
    q.u.param.vtype = FM1_VAL_INDEX;
    q.u.param.bits = (uint32_t)(v - p->min + 0.5f);
  } else {
    if (v == 0.0f) v = 0.0f;              /* no -0 */
    q.u.param.vtype = FM1_VAL_F32;
    memcpy(&q.u.param.bits, &v, sizeof v);
  }
  out(c, &q);
}

/* A unit and every parameter: the knobs' bases, and a pad kit's every pad
 * read back from the instance (engine API v4). */
static void unit_out(col_t *c, const fm1_app_t *a, int unit, unsigned role, unsigned sound, unsigned slot) {
  const fm1_app_unit_t *u = unit >= 0 ? &a->unit[unit] : NULL;
  fm1_rec_t r = blank(FM1_REC_UNIT);
  r.role = (uint8_t)role;
  r.sound = (uint8_t)sound;
  r.slot = (uint8_t)slot;
  if (u && u->e) strncpy(r.u.unit.id, u->e->id, sizeof r.u.unit.id - 1u);
  out(c, &r);
  if (!u || !u->e) return;
  for (uint16_t i = 0; i < u->e->n_params; ++i) {
    const fm1_param_t *p = &u->e->params[i];
    if (fm1_state_param_focus(u->e, i) == 2 && u->e->get_param) {
      unsigned pads = fm1_engine_focus_count(u->e);
      if (pads > FM1_STATE_PADS) pads = FM1_STATE_PADS;
      for (unsigned f = 0; f < pads; ++f) param_out(c, &r, p, f, u->e->get_param(u->self, i, (uint8_t)f));
    } else {
      param_out(c, &r, p, FM1_FOCUS_NONE, u->value[i]);
    }
  }
}

static void mfx_out(col_t *c, const fm1_app_t *a, int k, unsigned sound) {
  const fm1_engine_t *e = fm1_app_mfx_engine(a, k);
  fm1_rec_t r = blank(FM1_REC_UNIT), o;
  if (!e) return;
  r.role = FM1_ROLE_MFX;
  r.sound = (uint8_t)sound;
  strncpy(r.u.unit.id, e->id, sizeof r.u.unit.id - 1u);
  out(c, &r);
  o = r;
  o.type = FM1_REC_ON;
  memset(&o.u, 0, sizeof o.u);
  o.u.on = (uint8_t)(fm1_app_arp_on(a, k) == 1);
  out(c, &o);
  for (uint16_t i = 0; i < e->n_params; ++i) {
    param_out(c, &r, &e->params[i], FM1_FOCUS_NONE, fm1_app_arp_get_param(a, k, i));
  }
}

static void level_out(col_t *c, const fm1_app_t *a, int k, unsigned sound) {
  fm1_rec_t r = blank(FM1_REC_LEVEL);
  r.sound = (uint8_t)sound;
  memcpy(&r.u.level, &a->level[k], sizeof(float));
  out(c, &r);
}

static void dx7_out(col_t *c, const fm1_app_t *a, unsigned slot) {
  fm1_rec_t r = blank(FM1_REC_DX7);
  r.slot = (uint8_t)slot;
  memcpy(r.u.dx7.vced, a->dx7.voice[slot], FM1_DX7_VCED_BYTES);
  out(c, &r);
}

/* The FM6 user slot a sound unit's Patch plays, or -1. */
static int patch_slot(const fm1_app_t *a, int unit) {
  const fm1_app_unit_t *u = &a->unit[unit];
  int slot;
  if (!u->e || a->dx7.index < 0 || u->index != a->dx7.index) return -1;
  slot = (int)(u->value[a->dx7.patch] + 0.5f) - DX7_USER0;
  return slot >= 0 && slot < (int)FM1_DX7_USER_SLOTS && a->dx7.loaded[slot] ? slot : -1;
}

/* Modulation, filtered and remapped for a partial file. */
enum { MOD_ALL = 0, MOD_SOUND, MOD_CHAIN, MOD_NAMED };

typedef struct modf {
  col_t *c;
  const fm1_app_t *a;
  int mode, k;
  int chain[2];                /* MOD_CHAIN: the app units at chain positions 1 and 2 */
  uint8_t used[FM1_MOD_POSITIONS];
  int kept;
} modf_t;

static int chain_pos(const modf_t *f, unsigned code) {
  const int u = unit_of_code(code);
  for (int j = 0; j < 2; ++j) {
    if (u >= 0 && f->chain[j] == u) return j;
  }
  return -1;
}

static int keep_cable(const modf_t *f, const fm1_mod_slot_t *s) {
  const unsigned u = fm1_mod_unit_canonical(s->dst_unit);
  if (!s->dst && !(s->flags & FM1_MOD_SLOT_GATE_DST)) return 0;
  switch (f->mode) {
    case MOD_SOUND:
      return u == fm1_mod_sound_unit((unsigned)f->k) || u == fm1_mod_insert_unit((unsigned)f->k, 0) ||
             u == fm1_mod_insert_unit((unsigned)f->k, 1) ||
             (s->dst_unit == FM1_MOD_HOST &&
              s->dst == (f->k ? FM1_MOD_HOST_PITCH2_UID + (unsigned)f->k - 1u : FM1_MOD_HOST_PITCH_UID));
    case MOD_CHAIN:
      return !(s->flags & FM1_MOD_SLOT_GATE_DST) && chain_pos(f, s->dst_unit) >= 0;
    default:
      return 1;
  }
}

static int mod_scan(void *ctx, const fm1_rec_t *r) {
  modf_t *f = (modf_t *)ctx;
  const fm1_mod_slot_t *s = &r->u.cable.s;
  if (r->type != FM1_REC_CABLE || !keep_cable(f, s)) return 1;
  ++f->kept;
  if (s->src >= FM1_MOD_SRC_MODULE && s->src != FM1_MOD_NONE) f->used[(s->src - FM1_MOD_SRC_MODULE) / 8u] = 1;
  if (s->via >= FM1_MOD_SRC_MODULE && s->via != FM1_MOD_NONE) f->used[(s->via - FM1_MOD_SRC_MODULE) / 8u] = 1;
  if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
    f->used[s->dst_unit - FM1_MOD_MODULE] = 1;
  }
  return 1;
}

static int mod_emit(void *ctx, const fm1_rec_t *r) {
  modf_t *f = (modf_t *)ctx;
  fm1_rec_t q = *r;
  const int partial = f->mode == MOD_SOUND || f->mode == MOD_CHAIN;
  if (partial && (q.type == FM1_REC_MODULE || q.type == FM1_REC_DATA ||
                  (q.type == FM1_REC_PARAM && q.role == FM1_ROLE_MODULE)) && !f->used[q.slot]) {
    return 1;
  }
  if (q.type == FM1_REC_CABLE) {
    fm1_mod_slot_t *s = &q.u.cable.s;
    if (!keep_cable(f, s)) return 1;
    if (f->mode == MOD_SOUND) {
      const unsigned k = (unsigned)f->k, u = fm1_mod_unit_canonical(s->dst_unit);
      if (u == fm1_mod_sound_unit(k)) s->dst_unit = FM1_MOD_SOUND;
      else if (u == fm1_mod_insert_unit(k, 0)) s->dst_unit = FM1_MOD_INSERT;
      else if (u == fm1_mod_insert_unit(k, 1)) s->dst_unit = FM1_MOD_INSERT + 1u;
      else if (s->dst_unit == FM1_MOD_HOST) s->dst = FM1_MOD_HOST_PITCH_UID;   /* the sound's own pitch */
      if (s->src >= FM1_MOD_SRC_S_NOTE && s->src < FM1_MOD_SRC_SYSTEM && (s->src - FM1_MOD_SRC_S_NOTE) % 4u == k) {
        s->src = (uint8_t)(s->src - k);
      }
      if (s->via >= FM1_MOD_SRC_S_NOTE && s->via < FM1_MOD_SRC_SYSTEM && (s->via - FM1_MOD_SRC_S_NOTE) % 4u == k) {
        s->via = (uint8_t)(s->via - k);
      }
    } else if (f->mode == MOD_CHAIN) {
      s->dst_unit = (uint8_t)(FM1_MOD_FX1 + (unsigned)chain_pos(f, s->dst_unit));
    } else if (f->mode == MOD_NAMED && s->dst && !(s->flags & FM1_MOD_SLOT_GATE_DST)) {
      /* A rack file holds no engines: its cables name the project's
       * parameters (the note's §7.3). */
      const int u = unit_of_code(s->dst_unit);
      const fm1_engine_t *e = u >= 0 ? f->a->unit[u].e : NULL;
      const int p = e ? fm1_param_index(e, s->dst) : -1;
      if (p >= 0) {
        strncpy(q.u.cable.name, e->params[p].name, sizeof q.u.cable.name - 1u);
        s->dst = 0;
      }
    }
  }
  out(f->c, &q);
  return f->c->ok;
}

static void mod_out(col_t *c, const fm1_app_t *a, int mode, int k, const int chain[2]) {
  modf_t f;
  if (!a->mod) return;
  memset(&f, 0, sizeof f);
  f.c = c;
  f.a = a;
  f.mode = mode;
  f.k = k;
  f.chain[0] = chain ? chain[0] : -1;
  f.chain[1] = chain ? chain[1] : -1;
  if (mode == MOD_SOUND || mode == MOD_CHAIN) {
    fm1_state_mod_collect(a->mod, 0, 0, mod_scan, &f);
    if (!f.kept) return;                 /* no modulation of its own */
  }
  fm1_state_mod_collect(a->mod, a->mod_seed, mode == MOD_ALL || mode == MOD_NAMED, mod_emit, &f);
}

/* The set's movy1 text into g_set; its length, or 0. */
static uint32_t set_text(const fm1_app_t *a) {
  size_t n;
  g_set_n = 0;
  if (!a->seq) return 0;
  n = fm1_seq_export_movy1(a->seq, g_set, sizeof g_set);
  if (n >= sizeof g_set) return 0;
  g_set_n = (uint32_t)n;
  return g_set_n;
}

static void lines_out(col_t *c, const char *s, uint32_t n, unsigned which) {
  uint32_t start = 0;
  for (uint32_t i = 0; i <= n; ++i) {
    if (i < n && s[i] != '\n') continue;
    if (i > start || (i < n)) {
      fm1_rec_t r = blank(FM1_REC_LINE);
      r.piece = FM1_REC_FIRST | FM1_REC_LAST;
      r.u.line.which = (uint8_t)which;
      r.u.line.n = i - start;
      r.u.line.s = s + start;
      if (i < n || i > start) out(c, &r);
    }
    start = i + 1;
  }
}

/* Set by a save with binary 3 (the state hash's form): the project without
 * where the panel is (its view and the current sound), so a follow that
 * moves the panel changes no hash (stage ED4). */
static int g_no_view;

static void session_out(col_t *c, const fm1_app_t *a) {
  fm1_rec_t r = blank(FM1_REC_SESSION);
  int scale = 0;
  const int root = fm1_app_project_key(a, &scale);
  r.u.session.current = (int8_t)(g_no_view ? 0 : a->sound);   /* the hash: where the panel is, left out */
  r.u.session.octave = (int8_t)a->octave;
  r.u.session.transpose = (int8_t)a->transpose;
  /* The key's one home is the set's `key` line; this copy is written from
   * it, for readers of the JSON, and never applied (fm1_app_state.h). */
  r.u.session.has_key = 1;
  r.u.session.root = (uint8_t)(root % 12);
  snprintf(r.u.session.scale, sizeof r.u.session.scale, "%s",
           fm1_app_scale_id(scale) ? fm1_app_scale_id(scale) : "major");
  out(c, &r);
}

static void view_out(col_t *c, const fm1_app_t *a) {
  fm1_rec_t r = blank(FM1_REC_VIEW);
  uint8_t *v = r.u.view.v;
  uint16_t has = 0;
#define VSET(key, value) (v[key] = (uint8_t)(value), has |= (uint16_t)(1u << (key)))
  switch (a->mode) {
    case FM1_MODE_FX: {
      static const int kUnitOf[5] = { -1, -1, -1, 1, 2 };
      r.u.view.mode = FM1_VIEW_FX;
      VSET(FM1_VK_SOUND, a->sound + 1);
      VSET(FM1_VK_PAGE, a->fx_page + 1);
      if (a->fx_slot == 0 || a->fx_slot == 1) {
        VSET(FM1_VK_UNIT, fm1_mod_insert_unit((unsigned)a->sound, (unsigned)a->fx_slot));
      } else if (a->fx_slot >= 3 && a->fx_slot <= 4) {
        VSET(FM1_VK_UNIT, kUnitOf[a->fx_slot]);
      }
      break;
    }
    case FM1_MODE_GLOBAL:
      r.u.view.mode = FM1_VIEW_GLO;
      VSET(FM1_VK_PAGE, a->glo_page + 1);
      break;
    case FM1_MODE_SEQ:
      VSET(FM1_VK_TRACK, a->ui.track + 1);
      if (a->ui.view == FM1_SEQ_VIEW_SESSION) {          /* S9: Session, its track */
        r.u.view.mode = FM1_VIEW_SESSION;
        break;
      }
      if (a->ui.view == FM1_SEQ_VIEW_SONG) {             /* the Song page, its cursor */
        r.u.view.mode = FM1_VIEW_SONG;
        if (a->ui.song_cur < a->ui.song_entries) VSET(FM1_VK_ENTRY, a->ui.song_cur + 1);
        break;
      }
      r.u.view.mode = FM1_VIEW_SEQ;
      VSET(FM1_VK_BAR, a->ui.bar + 1);
      if (a->ui.view == FM1_SEQ_VIEW_SET) VSET(FM1_VK_PANEL, 1);
      else if (a->ui.view == FM1_SEQ_VIEW_CLIP) VSET(FM1_VK_PANEL, 2);
      break;
    case FM1_MODE_RACK:
      r.u.view.mode = FM1_VIEW_RACK;
      VSET(FM1_VK_POS, a->mui.pos + 1);
      break;
    case FM1_MODE_MATRIX:
      r.u.view.mode = FM1_VIEW_MATRIX;
      VSET(FM1_VK_SLOT, a->mui.slot + 1);
      break;
    case FM1_MODE_CHAIN:
      r.u.view.mode = FM1_VIEW_CHAIN;
      break;
    default:                             /* HOME, and the ARP pages, which open from it */
      r.u.view.mode = FM1_VIEW_HOME;
      VSET(FM1_VK_SOUND, a->sound + 1);
      if (a->mode == FM1_MODE_HOME) VSET(FM1_VK_PAGE, a->page + 1);
      break;
  }
#undef VSET
  r.u.view.has = has;
  out(c, &r);
}

static void setting_out(col_t *c, unsigned key, int is_bool, int value) {
  fm1_rec_t r = blank(FM1_REC_SETTING);
  r.u.setting.key = (uint8_t)key;
  r.u.setting.is_bool = (uint8_t)is_bool;
  r.u.setting.value = value;
  out(c, &r);
}

static int metronome_on(const fm1_app_t *a) {
  fm1_seq_info_t i;
  if (!a->seq) return 0;
  fm1_seq_get_info(a->seq, &i);
  return i.metronome != 0;
}

/* The records of `kind` into sink: 1, or 0 with *why. */
static int collect(fm1_app_t *a, unsigned kind, int arg, fm1_rec_sink_t sink, void *ctx, const char **why) {
  col_t c = { sink, ctx, 1 };
  switch (kind) {
    case FM1_STATE_PROJECT: {
      head_out(&c, kind);
      text_out(&c, FM1_INFO_NAME, a->info.name);
      text_out(&c, FM1_INFO_TITLE, a->info.title);
      text_out(&c, FM1_INFO_ABOUT, a->info.about);
      text_out(&c, FM1_INFO_AUTHOR, a->info.author);
      text_out(&c, FM1_INFO_LICENCE, a->info.licence);
      session_out(&c, a);
      for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
        const int u = fm1_app_sound_unit(k);
        unit_out(&c, a, u, FM1_ROLE_SOUND, (unsigned)k, 0);
        if (a->unit[u].e) level_out(&c, a, k, (unsigned)k);
        for (int j = 0; j < FM1_APP_INSERTS; ++j) {
          unit_out(&c, a, fm1_app_insert_unit(k, j), FM1_ROLE_INSERT, (unsigned)k, (unsigned)j);
        }
        if (a->unit[u].e) mfx_out(&c, a, k, (unsigned)k);
      }
      for (int j = 0; j < FM1_APP_FX_SLOTS; ++j) unit_out(&c, a, 1 + j, FM1_ROLE_MASTER, 0, (unsigned)j);
      for (unsigned s = 0; s < FM1_DX7_USER_SLOTS; ++s) {
        if (a->dx7.index >= 0 && a->dx7.loaded[s]) dx7_out(&c, a, s);
      }
      mod_out(&c, a, MOD_ALL, 0, NULL);
      if (set_text(a)) lines_out(&c, g_set, g_set_n, FM1_LINES_SET);
      if (!g_no_view) view_out(&c, a);
      break;
    }
    case FM1_STATE_SOUND: {
      const int u = fm1_app_sound_unit(arg);
      int slot;
      if (u < 0 || !a->unit[u].e) {
        *why = "that sound is empty";
        return 0;
      }
      head_out(&c, kind);
      unit_out(&c, a, u, FM1_ROLE_SOUND, 0, 0);
      level_out(&c, a, arg, 0);
      for (int j = 0; j < FM1_APP_INSERTS; ++j) {
        unit_out(&c, a, fm1_app_insert_unit(arg, j), FM1_ROLE_INSERT, 0, (unsigned)j);
      }
      mfx_out(&c, a, arg, 0);
      slot = patch_slot(a, u);
      if (slot >= 0) dx7_out(&c, a, (unsigned)slot);
      mod_out(&c, a, MOD_SOUND, arg, NULL);
      break;
    }
    case FM1_STATE_FX: {
      int chain[2] = { -1, -1 }, n = 0;
      for (int j = 0; j < 2; ++j) {
        const int u = arg < 0 ? 1 + j : fm1_app_insert_unit(arg, j);
        if (u >= 0 && a->unit[u].e) chain[n++] = u;
      }
      if (!n) {
        *why = arg < 0 ? "the master has no effects" : "that sound has no inserts";
        return 0;
      }
      head_out(&c, kind);
      for (int j = 0; j < n; ++j) unit_out(&c, a, chain[j], FM1_ROLE_MASTER, 0, (unsigned)j);
      mod_out(&c, a, MOD_CHAIN, 0, chain);
      break;
    }
    case FM1_STATE_MODS:
      if (!a->mod) {
        *why = "no modulation runtime";
        return 0;
      }
      head_out(&c, kind);
      mod_out(&c, a, MOD_NAMED, 0, NULL);
      break;
    case FM1_STATE_CLIP: {
      size_t count = 0;
      char **lines;
      if (arg < 0 || !set_text(a)) {
        *why = "no set";
        return 0;
      }
      lines = fm1_state_clip_from(g_set, g_set_n, (unsigned)arg / 8u, (unsigned)arg % 8u, &count);
      if (!lines) {
        *why = "no clip at that track and slot";
        return 0;
      }
      head_out(&c, kind);
      for (size_t i = 0; i < count; ++i) {
        fm1_rec_t r = blank(FM1_REC_LINE);
        r.piece = FM1_REC_FIRST | FM1_REC_LAST;
        r.u.line.which = FM1_LINES_CLIP;
        r.u.line.n = (uint32_t)strlen(lines[i]);
        r.u.line.s = lines[i];
        out(&c, &r);
      }
      fm1_state_clip_free(lines, count);
      break;
    }
    case FM1_STATE_SETTINGS:
      head_out(&c, kind);
      setting_out(&c, FM1_SET_METRONOME, 1, metronome_on(a));
      setting_out(&c, FM1_SET_COUNT_IN_CLICK, 1, a->settings.count_in_click != 0);
      setting_out(&c, FM1_SET_FULL_VELOCITY, 1, a->ui.full_vel != 0);
      setting_out(&c, FM1_SET_MIDI_IN_CHANNEL, 0, a->settings.midi_in_channel);
      break;
    case FM1_STATE_SET:
      if (!set_text(a)) {
        *why = "no set";
        return 0;
      }
      head_out(&c, kind);
      lines_out(&c, g_set, g_set_n, FM1_LINES_SET);
      break;
    default:
      *why = "not a kind the app saves";
      return 0;
  }
  {
    const fm1_rec_t end = blank(FM1_REC_END);
    out(&c, &end);
  }
  if (!c.ok) *why = "the writer refused a record";
  return c.ok;
}

static void json_put(void *ctx, const char *b, size_t n) {
  (void)ctx;
  if (g_json_n + n > JSON_CAP) {
    g_json_over = 1;
    return;
  }
  memcpy(g_json + g_json_n, b, n);
  g_json_n += (uint32_t)n;
}

static void bin_put(void *ctx, const char *b, size_t n) {
  (void)ctx;
  if (g_bin_n + n > sizeof g_bin) {
    g_bin_over = 1;
    return;
  }
  memcpy(g_bin + g_bin_n, b, n);
  g_bin_n += (uint32_t)n;
}

static uint32_t json_src(void *ctx, uint32_t off, uint8_t *buf, uint32_t n) {
  (void)ctx;
  if (off >= g_json_n) return 0;
  if (n > g_json_n - off) n = g_json_n - off;
  memcpy(buf, g_json + off, n);
  return n;
}

static int refuse_rep(fm1_state_report_t *rep, unsigned code, const char *what) {
  rep->code = (uint8_t)code;
  snprintf(rep->what, sizeof rep->what, "%s", what);
  return 0;
}

int fm1_app_state_save(fm1_app_t *a, unsigned kind, int arg, int binary, fm1_put_t put, void *ctx,
                       fm1_state_report_t *rep) {
  static const uint8_t version[3] = { 0, 1, 0 };
  const char *why = "";
  fm1_state_report_t own;
  const unsigned bflags = binary >= 2 ? 0u : FM1_STATE_BIN_DEFLATE;   /* 2, 3: no deflate */
  if (!rep) rep = &own;
  g_no_view = binary == 3;             /* 3: the hash's form, no view either */
  fm1_state_report_init(rep);
  rep->kind = (uint8_t)kind;
  if (kind == FM1_STATE_SET && !binary) {
    if (!set_text(a)) return refuse_rep(rep, FM1_STATE_BAD, "no set");
    put(ctx, g_set, g_set_n);
    return 1;
  }
  if (fm1_state_json_writer_size() > sizeof g_jw || fm1_state_bin_writer_size() > sizeof g_bw) {
    return refuse_rep(rep, FM1_STATE_TOO_BIG, "the writer does not fit its buffer");
  }
  g_bin_n = 0;
  g_bin_over = 0;
  if (kind == FM1_STATE_SET) {         /* binary only: straight to the container */
    fm1_state_writer_t *b = fm1_state_bin_writer(g_bw, bflags, FM1_STATE_WRITER_SIM, version,
                                                 bin_put, NULL, rep);
    if (!b || !collect(a, kind, arg, fm1_state_bin_write, b, &why)) {
      if (rep->code == FM1_STATE_OK) refuse_rep(rep, FM1_STATE_BAD, why);
      return 0;
    }
  } else {
    fm1_state_writer_t *w;
    g_json_n = 0;
    g_json_over = 0;
    w = fm1_state_json_writer(g_jw, names(), 0, json_put, NULL, rep);
    if (!w || !collect(a, kind, arg, fm1_state_write, w, &why)) {
      if (rep->code == FM1_STATE_OK) refuse_rep(rep, FM1_STATE_BAD, why);
      return 0;
    }
    if (g_json_over) return refuse_rep(rep, FM1_STATE_TOO_BIG, "larger than the file cap");
    if (!binary) {
      put(ctx, g_json, g_json_n);
      return 1;
    }
    {
      /* The binary writer wants the canonical order, which the canonical
       * JSON's reader gives. */
      fm1_state_writer_t *b = fm1_state_bin_writer(g_bw, bflags, FM1_STATE_WRITER_SIM, version,
                                                   bin_put, NULL, rep);
      if (!b || !fm1_state_json_read(names(), json_src, NULL, fm1_state_bin_write, b, rep)) return 0;
    }
  }
  if (g_bin_over) return refuse_rep(rep, FM1_STATE_TOO_BIG, "larger than a binary file");
  put(ctx, (const char *)g_bin, g_bin_n);
  return 1;
}

int fm1_app_state_pack(fm1_src_read_t rd, void *rctx, fm1_put_t put, void *ctx, fm1_state_report_t *rep) {
  static const uint8_t version[3] = { 0, 1, 0 };
  fm1_state_writer_t *b;
  fm1_state_report_init(rep);
  if (fm1_state_bin_writer_size() > sizeof g_bw) return refuse_rep(rep, FM1_STATE_TOO_BIG, "the writer does not fit");
  g_bin_n = 0;
  g_bin_over = 0;
  {
    /* The binary writer wants the canonical order: the file goes through the
     * canonical JSON writer first, as fm1-state pack goes through canon. */
    fm1_state_report_t r1;
    fm1_state_writer_t *w;
    fm1_state_report_init(&r1);
    g_json_n = 0;
    g_json_over = 0;
    w = fm1_state_json_writer(g_jw, names(), 0, json_put, NULL, &r1);
    if (!w || !fm1_state_json_read(names(), rd, rctx, fm1_state_write, w, &r1)) {
      *rep = r1;
      return 0;
    }
    if (g_json_over) return refuse_rep(rep, FM1_STATE_TOO_BIG, "larger than the file cap");
  }
  b = fm1_state_bin_writer(g_bw, FM1_STATE_BIN_DEFLATE, FM1_STATE_WRITER_SIM, version, bin_put, NULL, rep);
  if (!b || !fm1_state_json_read(names(), json_src, NULL, fm1_state_bin_write, b, rep)) return 0;
  if (g_bin_over) return refuse_rep(rep, FM1_STATE_TOO_BIG, "larger than a binary file");
  put(ctx, (const char *)g_bin, g_bin_n);
  return 1;
}

/* ============================== load ===================================== */

typedef struct plan {
  fm1_app_t *a;
  const fm1_app_load_opts_t *o;
  fm1_app_state_report_t *rep;
  int pass;                    /* 1 check, 2 apply, 3 pass 2's FM6 sweep */
  unsigned kind;
  int enc;                     /* fm1_state_sniff's */
  /* What the file gives, by app unit. */
  const fm1_engine_t *e[FM1_APP_UNITS];
  uint8_t given[FM1_APP_UNITS], unknown[FM1_APP_UNITS];
  const fm1_engine_t *mfx[FM1_APP_SOUNDS];
  uint8_t mfx_given[FM1_APP_SOUNDS], mfx_on[FM1_APP_SOUNDS];
  unsigned chain_n;            /* an effects file's chain */
  /* Modulation. */
  uint8_t has_mod, has_seed, mod_drop;
  uint32_t seed;
  uint8_t file_pos[FM1_MOD_POSITIONS];
  uint32_t file_slots;
  uint8_t same_mod[FM1_MOD_POSITIONS];
  uint16_t mod_params[FM1_MOD_POSITIONS], mod_data[FM1_MOD_POSITIONS];
  int8_t pos_map[FM1_MOD_POSITIONS];
  int8_t slot_map[FM1_MOD_SLOTS];
  fm1_state_mod_t sm;
  int sm_ready;
  /* FM6's voices. */
  unsigned n_voices;
  uint8_t voice_slot[FM1_DX7_USER_SLOTS];
  uint8_t voice[FM1_DX7_USER_SLOTS][FM1_DX7_VCED_BYTES];
  int8_t voice_map[FM1_DX7_USER_SLOTS];        /* by file slot: the bank slot, or -1 */
  /* Lines, the session, the view, settings, words. */
  uint8_t has_set, has_clip, has_session, has_view;
  fm1_rec_t session, view;
  uint8_t setting_has[FM1_SET_KEYS];
  int32_t setting[FM1_SET_KEYS];
  char name[33];
  unsigned info_key;
  /* Pass 2: a pad kit's focus, applied last. */
  int8_t focus_idx[FM1_APP_UNITS];
  uint8_t focus_has[FM1_APP_UNITS], touched[FM1_APP_UNITS];
  float focus_val[FM1_APP_UNITS];
} plan_t;

static plan_t g_plan;

/* The app unit a record's (role, sound, slot) names in this load: >= 0 a
 * unit, -2 - k sound k's MIDI effect, -1 nothing (left out). */
static int map_unit(const plan_t *p, unsigned role, unsigned sound, unsigned slot) {
  const int into = p->o->into;
  switch (p->kind) {
    case FM1_STATE_PROJECT:
      if (sound >= FM1_APP_SOUNDS) return -1;
      if (role == FM1_ROLE_SOUND) return fm1_app_sound_unit((int)sound);
      if (role == FM1_ROLE_INSERT) return slot < FM1_APP_INSERTS ? fm1_app_insert_unit((int)sound, (int)slot) : -1;
      if (role == FM1_ROLE_MASTER) return slot < FM1_APP_FX_SLOTS ? 1 + (int)slot : -1;
      if (role == FM1_ROLE_MFX) return slot == 0 ? -2 - (int)sound : -1;
      return -1;
    case FM1_STATE_SOUND:
      if (into < 0 || into >= FM1_APP_SOUNDS) return -1;
      if (role == FM1_ROLE_SOUND) return fm1_app_sound_unit(into);
      if (role == FM1_ROLE_INSERT) return slot < FM1_APP_INSERTS ? fm1_app_insert_unit(into, (int)slot) : -1;
      if (role == FM1_ROLE_MFX) return slot == 0 ? -2 - into : -1;
      return -1;
    case FM1_STATE_FX:
      if (role != FM1_ROLE_MASTER || slot >= 2) return -1;
      return into < 0 ? 1 + (int)slot : into < FM1_APP_SOUNDS ? fm1_app_insert_unit(into, (int)slot) : -1;
    default:
      return -1;
  }
}

/* The units a load replaces (a project: every one). */
static int target_unit(const plan_t *p, int u) {
  const int into = p->o->into;
  switch (p->kind) {
    case FM1_STATE_PROJECT:
      return 1;
    case FM1_STATE_SOUND:
      return u == fm1_app_sound_unit(into) || u == fm1_app_insert_unit(into, 0) || u == fm1_app_insert_unit(into, 1);
    case FM1_STATE_FX:
      return into < 0 ? (u == 1 || u == 2) : (u == fm1_app_insert_unit(into, 0) || u == fm1_app_insert_unit(into, 1));
    default:
      return 0;
  }
}

static int mod_kind(unsigned k) { return k == FM1_STATE_PROJECT || k == FM1_STATE_MODS; }

static float rec_value(const fm1_param_t *p, const fm1_rec_t *r) {
  if (r->u.param.vtype == FM1_VAL_INDEX) return p->min + (float)r->u.param.bits;
  return bits_f(r->u.param.bits);
}

/* Unit codes and sources of a merge's cable, into the app's places. */
static void remap_cable(const plan_t *p, fm1_mod_slot_t *s) {
  const int into = p->o->into;
  if (p->kind == FM1_STATE_SOUND) {
    const unsigned k = (unsigned)into;
    if (s->dst_unit == FM1_MOD_SOUND) s->dst_unit = (uint8_t)fm1_mod_sound_unit(k);
    else if (s->dst_unit == FM1_MOD_INSERT || s->dst_unit == FM1_MOD_INSERT + 1u) {
      s->dst_unit = (uint8_t)fm1_mod_insert_unit(k, s->dst_unit - FM1_MOD_INSERT);
    } else if (s->dst_unit == FM1_MOD_HOST && s->dst == FM1_MOD_HOST_PITCH_UID && k) {
      s->dst = (uint16_t)(FM1_MOD_HOST_PITCH2_UID + k - 1u);
    }
    if (s->src >= FM1_MOD_SRC_S_NOTE && s->src < FM1_MOD_SRC_SYSTEM && (s->src - FM1_MOD_SRC_S_NOTE) % 4u == 0u) {
      s->src = (uint8_t)(s->src + k);
    }
    if (s->via >= FM1_MOD_SRC_S_NOTE && s->via < FM1_MOD_SRC_SYSTEM && (s->via - FM1_MOD_SRC_S_NOTE) % 4u == 0u) {
      s->via = (uint8_t)(s->via + k);
    }
  } else if (p->kind == FM1_STATE_FX && into >= 0) {
    if (s->dst_unit == FM1_MOD_FX1 || s->dst_unit == FM1_MOD_FX2) {
      s->dst_unit = (uint8_t)fm1_mod_insert_unit((unsigned)into, s->dst_unit - FM1_MOD_FX1);
    }
  }
  if (p->kind == FM1_STATE_SOUND || p->kind == FM1_STATE_FX) {
    if (s->src >= FM1_MOD_SRC_MODULE && s->src != FM1_MOD_NONE) {
      const unsigned pos = (s->src - FM1_MOD_SRC_MODULE) / 8u, port = (s->src - FM1_MOD_SRC_MODULE) % 8u;
      s->src = (uint8_t)(FM1_MOD_SRC_MODULE + 8u * (unsigned)p->pos_map[pos] + port);
    }
    if (s->via >= FM1_MOD_SRC_MODULE && s->via != FM1_MOD_NONE) {
      const unsigned pos = (s->via - FM1_MOD_SRC_MODULE) / 8u, port = (s->via - FM1_MOD_SRC_MODULE) % 8u;
      s->via = (uint8_t)(FM1_MOD_SRC_MODULE + 8u * (unsigned)p->pos_map[pos] + port);
    }
    if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
      s->dst_unit = (uint8_t)(FM1_MOD_MODULE + (unsigned)p->pos_map[s->dst_unit - FM1_MOD_MODULE]);
    }
  }
}

static void gather(char *buf, uint32_t cap, uint32_t *n, int *over, const char *s, uint32_t len, int last) {
  if (*n + len + 1u > cap) {
    *over = 1;
    return;
  }
  memcpy(buf + *n, s, len);
  *n += len;
  if (last) buf[(*n)++] = '\n';
}

static void info_take(plan_t *p, const fm1_rec_t *r) {
  char *dst = NULL;
  size_t cap = 0, have;
  fm1_app_info_t *in = &p->a->info;
  if (p->kind != FM1_STATE_PROJECT && r->u.info.key != FM1_INFO_NAME) return;
  switch (r->u.info.key) {
    case FM1_INFO_NAME: dst = p->pass == 1 ? p->name : in->name; cap = sizeof in->name; break;
    case FM1_INFO_TITLE: dst = in->title; cap = sizeof in->title; break;
    case FM1_INFO_ABOUT: dst = in->about; cap = sizeof in->about; break;
    case FM1_INFO_AUTHOR: dst = in->author; cap = sizeof in->author; break;
    case FM1_INFO_LICENCE: dst = in->licence; cap = sizeof in->licence; break;
    default: return;
  }
  if (p->pass == 1 && dst != p->name) return;
  if (p->pass == 2 && p->kind != FM1_STATE_PROJECT) return;
  if (r->piece & FM1_REC_FIRST) dst[0] = '\0';
  have = strlen(dst);
  if (have + 1u < cap) {
    size_t n = r->u.info.n;
    if (n > cap - 1u - have) n = cap - 1u - have;
    memcpy(dst + have, r->u.info.s, n);
    dst[have + n] = '\0';
  }
}

static const fm1_engine_t *rec_engine(unsigned role, const char *id) {
  if (!id[0]) return NULL;
  if (role == FM1_ROLE_MFX) {
    const fm1_midi_fx_t *fx = fm1_midi_fx_find(id);
    return fx ? &fx->engine : NULL;
  }
  return fm1_state_engine(names(), role == FM1_ROLE_INSERT || role == FM1_ROLE_MASTER ? role : FM1_ROLE_SOUND, id);
}

static int plan_pass1(plan_t *p, const fm1_rec_t *r) {
  fm1_app_t *a = p->a;
  fm1_state_report_t *rep = &p->rep->r;
  if (p->enc == 1) fm1_state_note_unknown(names(), r, rep);   /* the binary reader resolves no names */
  switch (r->type) {
    case FM1_REC_HEAD:
      p->kind = r->u.head.kind;
      break;
    case FM1_REC_INFO:
      info_take(p, r);
      break;
    case FM1_REC_SESSION:
      p->has_session = 1;
      p->session = *r;
      break;
    case FM1_REC_UNIT: {
      const int m = map_unit(p, r->role, r->sound, r->slot);
      const fm1_engine_t *e = rec_engine(r->role, r->u.unit.id);
      if (p->kind == FM1_STATE_FX && r->role == FM1_ROLE_MASTER && r->u.unit.id[0]) ++p->chain_n;
      if (m >= 0) {
        p->given[m] = 1;
        p->e[m] = e;
        p->unknown[m] = (uint8_t)(r->u.unit.id[0] && !e);
      } else if (m <= -2) {
        p->mfx_given[-2 - m] = 1;
        p->mfx[-2 - m] = e;
      } else if (r->u.unit.id[0] && !(p->kind == FM1_STATE_FX && r->role == FM1_ROLE_MASTER)) {
        ++rep->skipped;               /* a MIDI effect past the panel's one slot */
        if (!rep->first_skip[0]) snprintf(rep->first_skip, sizeof rep->first_skip, "%s in a MIDI-effect slot past the first", r->u.unit.id);
      }
      break;
    }
    case FM1_REC_ON: {
      const int m = map_unit(p, r->role, r->sound, r->slot);
      if (m <= -2) p->mfx_on[-2 - m] = r->u.on;
      break;
    }
    case FM1_REC_DX7:
      if (p->n_voices < FM1_DX7_USER_SLOTS && r->slot < FM1_DX7_USER_SLOTS) {
        p->voice_slot[p->n_voices] = r->slot;
        memcpy(p->voice[p->n_voices], r->u.dx7.vced, FM1_DX7_VCED_BYTES);
        ++p->n_voices;
      }
      break;
    case FM1_REC_MOD:
      p->has_mod = 1;
      break;
    case FM1_REC_SEED:
      p->has_seed = 1;
      p->seed = r->u.seed;
      break;
    case FM1_REC_MODULE:
      if (r->slot < FM1_MOD_POSITIONS) {
        p->file_pos[r->slot] = 1;
        p->same_mod[r->slot] = (uint8_t)(a->mod && fm1_mod_kind_at(a->mod, r->slot) >= 0 &&
          fm1_mod_kind_at(a->mod, r->slot) == fm1_mod_kind_find(r->u.unit.id));
      }
      break;
    case FM1_REC_PARAM:
      if (r->role == FM1_ROLE_MODULE && r->slot < FM1_MOD_POSITIONS && p->same_mod[r->slot]) {
        const int k = fm1_mod_kind_at(a->mod, r->slot);
        const fm1_mod_kind_t *kind = fm1_mod_kinds[k];
        unsigned i;
        for (i = 0; i < kind->n_params; ++i) if (kind->params[i].uid == r->u.param.uid) break;
        if (i == kind->n_params || fm1_mod_param_base(a->mod, r->slot, i) != rec_value(&kind->params[i], r))
          p->same_mod[r->slot] = 0;
        ++p->mod_params[r->slot];
      }
      break;
    case FM1_REC_DATA:
      if (r->slot < FM1_MOD_POSITIONS && p->same_mod[r->slot]) {
        uint8_t data[FM1_MOD_DATA_MAX], version = 0;
        const unsigned n = fm1_mod_get_data(a->mod, r->slot, data, sizeof data, &version);
        unsigned off = (r->piece & FM1_REC_FIRST) ? 0 : p->mod_data[r->slot];
        if (version != r->u.data.version || off + r->u.data.n > n ||
            memcmp(data + off, r->u.data.b, r->u.data.n) || ((r->piece & FM1_REC_LAST) && off + r->u.data.n != n))
          p->same_mod[r->slot] = 0;
        p->mod_data[r->slot] = (uint16_t)(off + r->u.data.n);
      }
      break;
    case FM1_REC_CABLE:
      if (r->slot < FM1_MOD_SLOTS) p->file_slots |= 1u << r->slot;
      break;
    case FM1_REC_LINE:
      if (r->u.line.which == FM1_LINES_SET) p->has_set = 1;
      else p->has_clip = 1;
      gather(g_set, SET_CAP, &g_set_n, &g_set_over, r->u.line.s, r->u.line.n, (r->piece & FM1_REC_LAST) != 0);
      break;
    case FM1_REC_VIEW:
      p->has_view = 1;
      p->view = *r;
      break;
    case FM1_REC_SETTING:
      if (r->u.setting.key < FM1_SET_KEYS) {
        p->setting_has[r->u.setting.key] = 1;
        p->setting[r->u.setting.key] = r->u.setting.value;
      }
      break;
    default:
      break;
  }
  return 1;
}

/* Whether engine e runs at the host's rate: created once in a scratch
 * arena, remembered by registry entry. Larger instances than the arena are
 * taken to run (none of them resamples from Plaits' rate today). */
static int rate_ok(const fm1_app_t *a, const fm1_engine_t *e) {
  static float memo_rate;
  static int8_t memo[256];
  const int index = fm1_app_find(e->id);
  int ok;
  if (memo_rate != a->host.sample_rate) {
    memset(memo, 0, sizeof memo);
    memo_rate = a->host.sample_rate;
  }
  if (index >= 0 && index < 256 && memo[index]) return memo[index] > 0;
  if (e->instance_size(&a->host) > sizeof g_bw) {
    ok = 1;
  } else {
    void *self;
    memset(g_bw, 0, e->instance_size(&a->host));
    self = e->create(g_bw, &a->host);
    ok = self != NULL;
    if (self) e->destroy(self);
  }
  if (index >= 0 && index < 256) memo[index] = (int8_t)(ok ? 1 : -1);
  return ok;
}

static void rate_text(float hz, char *buf, size_t n) {
  long tenths = (long)(hz / 100.0f + 0.5f);
  if (tenths < 0 || tenths > 99999) tenths = 0;
  if (tenths % 10) snprintf(buf, n, "%ld.%ld kHz", tenths / 10, tenths % 10);
  else snprintf(buf, n, "%ld kHz", tenths / 10);
}

static const char *kind_word(unsigned kind) {
  switch (kind) {
    case FM1_STATE_PROJECT: return "project";
    case FM1_STATE_SOUND: return "sound";
    case FM1_STATE_FX: return "effects chain";
    case FM1_STATE_MODS: return "mod rack";
    case FM1_STATE_CLIP: return "clip";
    case FM1_STATE_SET: return "set";
    case FM1_STATE_SETTINGS: return "settings file";
    default: return "file";
  }
}

/* "a" or "an" ("A" or "An" when capital) for a word the way it is said. */
static const char *article(const char *word, int capital) {
  const int vowel = word && strchr("aeiouAEIOU", word[0]) != NULL;
  return vowel ? (capital ? "An" : "an") : (capital ? "A" : "a");
}

/* The refusal's words: the page's line and the screen's two. */
static int refuse_load(plan_t *p, unsigned code, const char *screen, const char *fmt, const char *arg) {
  fm1_app_state_report_t *rep = p->rep;
  rep->r.code = (uint8_t)code;
  snprintf(rep->message, sizeof rep->message, fmt, arg ? arg : "");
  snprintf(rep->screen[0], sizeof rep->screen[0], "NOT LOADED");
  snprintf(rep->screen[1], sizeof rep->screen[1], "%s", screen);
  return 0;
}

static int reader_refusal(plan_t *p) {
  fm1_app_state_report_t *rep = p->rep;
  char where[96];
  switch (rep->r.code) {
    case FM1_STATE_NOT_LUNAR:
      return refuse_load(p, rep->r.code, "Not a Lunar file", "This is not a Lunar Modulator file.%s", "");
    case FM1_STATE_TOO_NEW: {
      char lv[8];
      snprintf(lv, sizeof lv, "%u.%u", rep->r.major % 100u, rep->r.minor % 100u);
      snprintf(rep->message, sizeof rep->message,
               "Made with a newer Lunar Modulator (format %s); this simulator reads %u.%u.", lv,
               FM1_STATE_MAJOR, FM1_STATE_MINOR);
      snprintf(rep->screen[0], sizeof rep->screen[0], "NOT LOADED");
      snprintf(rep->screen[1], sizeof rep->screen[1], "Newer format %s", lv);
      return 0;
    }
    default:
      if (rep->r.line) {
        snprintf(where, sizeof where, "Line %u, column %u", (unsigned)rep->r.line, (unsigned)rep->r.col);
      } else {
        snprintf(where, sizeof where, "At byte %u", (unsigned)rep->r.offset);
      }
      snprintf(rep->message, sizeof rep->message, "%.24s%s%.60s: %.60s.", where, rep->r.path[0] ? ", " : "",
               rep->r.path, rep->r.what[0] ? rep->r.what : fm1_state_code_name(rep->r.code));
      snprintf(rep->screen[0], sizeof rep->screen[0], "NOT LOADED");
      snprintf(rep->screen[1], sizeof rep->screen[1], "%s",
               rep->r.code == FM1_STATE_TOO_BIG ? "File too big" : "Bad file");
      return 0;
  }
}

static int seq_fixed(const fm1_app_t *a) {
  return a->seq ? (int)(fm1_seq_size(&a->seq_lim) + sizeof a->seq_ev + sizeof a->seq_pend + FM1_APP_SEQ_UI_BYTES +
                        sizeof a->click)
                : 0;
}

/* Pass 1's verdict once the file is read: what the load needs, against the
 * app as it is. */
static int plan_finish(plan_t *p) {
  fm1_app_t *a = p->a;
  fm1_app_state_report_t *rep = p->rep;
  const fm1_engine_t *res[FM1_APP_UNITS];
  const fm1_engine_t *mfx_res[FM1_APP_SOUNDS];
  uint8_t mfx_on[FM1_APP_SOUNDS];
  const unsigned flags = p->o->flags;
  size_t ram = 0, mfx = 0;
  int sounds = 0;
  rep->r.kind = (uint8_t)p->kind;
  if (p->o->kind && p->o->kind != p->kind) {
    char want[72];
    const char *w = kind_word(p->o->kind), *got = kind_word(p->kind);
    /* "A sound, not an effects chain, was expected." The article follows the word. */
    snprintf(want, sizeof want, "%s %s, not %s %s, was expected.", article(w, 1), w, article(got, 0), got);
    return refuse_load(p, FM1_STATE_BAD, "Wrong kind", "%s", want);
  }
  if ((p->kind == FM1_STATE_SOUND || p->kind == FM1_STATE_FX) && p->o->into >= FM1_APP_SOUNDS) {
    return refuse_load(p, FM1_STATE_BAD, "No such sound", "There is no Sound %s.", "5");
  }
  if (p->kind == FM1_STATE_SOUND && p->o->into < 0) {
    return refuse_load(p, FM1_STATE_BAD, "No sound chosen", "A sound loads into Sound 1, 2, 3 or 4.%s", "");
  }
  if (p->kind == FM1_STATE_SETTINGS || p->kind == FM1_STATE_KIND_NONE || p->kind >= FM1_STATE_DX7BANK) {
    if (p->kind != FM1_STATE_SETTINGS) return refuse_load(p, FM1_STATE_BAD, "Not loadable", "This file holds nothing the simulator loads.%s", "");
  }
  if (rep->r.unknown && !(flags & FM1_APP_LOAD_WITHOUT)) {
    char why[160];
    const char *known = fm1_state_known_text(rep->r.known);
    snprintf(why, sizeof why, "This %s uses %s, which %s%s. Nothing was changed.", kind_word(p->kind),
             rep->r.name, known[0] ? "is " : "", known[0] ? known : "this build does not have");
    snprintf(rep->screen[1], sizeof rep->screen[1], "Uses %.20s", rep->r.name);
    rep->r.code = FM1_STATE_UNKNOWN;
    snprintf(rep->message, sizeof rep->message, "%s", why);
    snprintf(rep->screen[0], sizeof rep->screen[0], "NOT LOADED");
    return 0;
  }
  if (p->kind == FM1_STATE_FX && p->chain_n > 2) {
    if (!(flags & FM1_APP_LOAD_WITHOUT)) {
      char n[12];
      snprintf(n, sizeof n, "%u", p->chain_n % 1000u);
      return refuse_load(p, FM1_STATE_NO_ROOM, "Only two slots",
                         "Two effects fit there; this chain has %s.", n);
    }
    rep->left_out = (uint16_t)(rep->left_out + p->chain_n - 2u);
  }
  /* The units after the load. */
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (target_unit(p, u)) res[u] = p->given[u] ? p->e[u] : NULL;
    else res[u] = a->unit[u].e;
    if (p->unknown[u]) ++rep->left_out;
  }
  if (p->kind == FM1_STATE_PROJECT && !res[0]) {
    const int macro = fm1_app_find("macro");
    res[0] = macro >= 0 ? fm1_engines[macro] : NULL;
  }
  if (p->kind == FM1_STATE_SOUND && !res[fm1_app_sound_unit(p->o->into)]) {
    if (p->o->into == 0) {
      const int macro = fm1_app_find("macro");
      res[0] = macro >= 0 ? fm1_engines[macro] : NULL;
    }
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    const fm1_mfx_slot_t *sl = fm1_mfx_slot(&a->mfx, (unsigned)k, 0);
    const int replaced = p->kind == FM1_STATE_PROJECT || (p->kind == FM1_STATE_SOUND && p->o->into == k);
    if (replaced) {
      mfx_res[k] = p->mfx_given[k] && p->mfx[k] ? p->mfx[k] : fm1_app_arp_engine();
      mfx_on[k] = (uint8_t)(p->mfx_given[k] && p->mfx[k] && p->mfx_on[k]);
    } else {
      mfx_res[k] = sl && sl->fx ? &sl->fx->engine : NULL;
      mfx_on[k] = (uint8_t)(sl && sl->on);
    }
  }
  /* RATE, the arenas and RAM at 44,118 Hz (ST6). */
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const fm1_engine_t *e = res[u];
    if (!e) continue;
    if (target_unit(p, u) || (p->kind == FM1_STATE_PROJECT)) {
      char hz[24];
      if (e->instance_size(&a->host) > a->unit[u].cap) {
        return refuse_load(p, FM1_STATE_RAM, "Too large", "%s is larger than the simulator's arena for it.", e->name);
      }
      if (!rate_ok(a, e)) {
        char why[96];
        rate_text(a->host.sample_rate, hz, sizeof hz);
        snprintf(why, sizeof why, "%s cannot run at this browser's %s.", e->name, hz);
        snprintf(rep->r.name, sizeof rep->r.name, "%s", e->id);
        refuse_load(p, FM1_STATE_RATE, "", "%s", why);
        snprintf(rep->screen[1], sizeof rep->screen[1], "%.12s at %.10s", e->name, hz);
        return 0;
      }
    }
    ram += fm1_app_ram_of(e);
    if (unit_sound(u) >= 0) ++sounds;
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    if (mfx_res[k] && mfx_on[k]) mfx += fm1_app_ram_of(mfx_res[k]);
  }
  ram += (size_t)seq_fixed(a);
  if (sounds > 1) ram += (size_t)(sounds - 1) * FM1_APP_MIX_BLOCK_BYTES;
  if (a->mod || mod_kind(p->kind)) ram += fm1_mod_size();
  if (mfx) ram += mfx + sizeof a->mfx;
  rep->ram = (uint32_t)ram;
  rep->budget = FM1_APP_RAM_BUDGET;
  rep->percent = (uint16_t)fm1_app_ram_percent(ram);
  if (ram > FM1_APP_RAM_BUDGET) {
    char pc[16];
    snprintf(pc, sizeof pc, "%u%%", (unsigned)rep->percent);
    refuse_load(p, FM1_STATE_RAM, "", "Needs %s of the FM-1's RAM.", pc);
    snprintf(rep->screen[1], sizeof rep->screen[1], "Needs %u%% RAM", (unsigned)rep->percent);
    return 0;
  }
  /* Room for a merge's modulation: free rack positions and matrix slots. */
  for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) p->pos_map[i] = (int8_t)i;
  for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) p->slot_map[i] = (int8_t)i;
  if (p->kind == FM1_STATE_SOUND && (flags & FM1_APP_LOAD_RESTORE_SOUND) && a->mod) {
    modf_t f;
    memset(&f, 0, sizeof f); f.mode = MOD_SOUND; f.k = p->o->into;
    for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      const int k = fm1_mod_kind_at(a->mod, pos);
      if (p->file_pos[pos] && k >= 0 && (p->mod_params[pos] != fm1_mod_kinds[k]->n_params ||
          p->mod_data[pos] != fm1_mod_kinds[k]->data_bytes)) p->same_mod[pos] = 0;
    }
    for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_slot_t slot;
      if (!fm1_mod_get_slot(a->mod, i, &slot) || (!slot.dst && !(slot.flags & FM1_MOD_SLOT_GATE_DST)) || keep_cable(&f, &slot)) continue;
      if ((p->file_slots >> i) & 1u)
        return refuse_load(p, FM1_STATE_NO_ROOM, "Cable slot changed", "A/B's original cable slot now belongs to %s.", "another destination");
      const uint8_t refs[2] = { slot.src, slot.via };
      for (unsigned j = 0; j < 2; ++j) if (refs[j] >= FM1_MOD_SRC_MODULE && refs[j] != FM1_MOD_NONE) {
        const unsigned pos = (refs[j] - FM1_MOD_SRC_MODULE) / 8u;
        if (pos < FM1_MOD_POSITIONS && p->file_pos[pos] && !p->same_mod[pos])
          return refuse_load(p, FM1_STATE_NO_ROOM, "Shared module changed", "A/B cannot replace a changed module shared with %s.", "another destination");
      }
    }
  } else if (p->has_mod && (p->kind == FM1_STATE_SOUND || p->kind == FM1_STATE_FX)) {
    uint8_t taken[FM1_MOD_POSITIONS];
    uint32_t used = 0;
    int short_pos = 0, short_slot = 0;
    if (!a->mod) {
      p->mod_drop = 1;
    } else {
      for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) taken[i] = (uint8_t)(fm1_mod_kind_at(a->mod, i) >= 0);
      for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
        fm1_mod_slot_t s;
        if (fm1_mod_get_slot(a->mod, i, &s) && (s.dst || (s.flags & FM1_MOD_SLOT_GATE_DST))) used |= 1u << i;
      }
      for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) {      /* where it was, if free */
        if (p->file_pos[i] && !taken[i]) taken[i] = 2;
      }
      for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) {
        if (!p->file_pos[i]) continue;
        if (taken[i] == 2) {
          taken[i] = 1;
          continue;
        }
        {
          unsigned q = 0;
          while (q < FM1_MOD_POSITIONS && taken[q]) ++q;
          if (q == FM1_MOD_POSITIONS) {
            short_pos = 1;
            break;
          }
          taken[q] = 1;
          p->pos_map[i] = (int8_t)q;
        }
      }
      for (unsigned i = 0; i < FM1_MOD_SLOTS && !short_pos; ++i) {
        unsigned q = 0;
        if (!((p->file_slots >> i) & 1u)) continue;
        while (q < FM1_MOD_SLOTS && ((used >> q) & 1u)) ++q;
        if (q == FM1_MOD_SLOTS) {
          short_slot = 1;
          break;
        }
        used |= 1u << q;
        p->slot_map[i] = (int8_t)q;
      }
      if (short_pos || short_slot) {
        if (!(flags & FM1_APP_LOAD_WITHOUT)) {
          snprintf(rep->r.name, sizeof rep->r.name, "its modulation");
          return refuse_load(p, FM1_STATE_NO_ROOM, short_pos ? "Rack is full" : "Matrix is full",
                             short_pos ? "The rack is full (8 of 8)%s; load it without its modulation?"
                                       : "The matrix is full (32 of 32)%s; load it without its modulation?", "");
        }
        p->mod_drop = 1;
      }
    }
    if (p->mod_drop) {
      for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) rep->left_out = (uint16_t)(rep->left_out + p->file_pos[i]);
      for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) rep->left_out = (uint16_t)(rep->left_out + ((p->file_slots >> i) & 1u));
    }
  }
  /* FM6's voices: a project's replace the bank; a sound's reuse an
   * identical voice, else the first slot not loaded (ST8). */
  for (unsigned i = 0; i < FM1_DX7_USER_SLOTS; ++i) p->voice_map[i] = -1;
  if (a->dx7.index >= 0) {
    uint8_t claimed[FM1_DX7_USER_SLOTS];
    memset(claimed, 0, sizeof claimed);
    for (unsigned v = 0; v < p->n_voices; ++v) {
      const unsigned fs = p->voice_slot[v];
      int to = -1;
      if (p->kind == FM1_STATE_PROJECT) {
        to = (int)fs;
      } else {
        for (unsigned s = 0; s < FM1_DX7_USER_SLOTS && to < 0; ++s) {
          if (a->dx7.loaded[s] && memcmp(a->dx7.voice[s], p->voice[v], FM1_DX7_VCED_BYTES) == 0) to = (int)s;
        }
        for (unsigned s = 0; s < FM1_DX7_USER_SLOTS && to < 0; ++s) {
          if (!a->dx7.loaded[s] && !claimed[s]) to = (int)s;
        }
        if (to < 0) {
          if (!(flags & FM1_APP_LOAD_WITHOUT)) {
            snprintf(rep->r.name, sizeof rep->r.name, "its FM6 voice");
            return refuse_load(p, FM1_STATE_NO_ROOM, "FM6 bank is full",
                               "FM6's user bank is full (32 of 32)%s; load it without its voice?", "");
          }
          ++rep->left_out;
        }
      }
      if (to >= 0) claimed[to] = 1;
      p->voice_map[fs] = (int8_t)to;
    }
  }
  /* A set: it must import (the tag), into a scratch instance. */
  if (g_set_over) return refuse_load(p, FM1_STATE_TOO_BIG, "Set too big", "The set is larger than %s.", "64 KiB");
  if (p->has_set || p->kind == FM1_STATE_SET) {
    fm1_seq_t *s;
    fm1_seq_info_t info;
    if (!a->seq || fm1_seq_size(&a->seq_lim) > sizeof g_seq_scratch) {
      return refuse_load(p, FM1_STATE_BAD, "No sequencer", "The simulator has no sequencer to load a set into.%s", "");
    }
    s = fm1_seq_create(g_seq_scratch, &a->seq_lim, (uint32_t)(a->host.sample_rate + 0.5f));
    if (!s || !fm1_seq_import_movy1(s, g_set, g_set_n)) {
      return refuse_load(p, FM1_STATE_BAD, "Not a set", "The set's lines are not a movy1 set.%s", "");
    }
    fm1_seq_get_info(s, &info);
    rep->tracks = info.tracks;
    rep->song = info.song_len;
    rep->set = 1;
    for (uint32_t i = 0; i + 3 < g_set_n; ++i) {
      if ((i == 0 || g_set[i - 1] == '\n') && g_set[i] == 'c' && g_set[i + 1] == 'l' && g_set[i + 2] == ' ') ++rep->clips;
    }
  }
  if (p->kind == FM1_STATE_CLIP) {
    const int t = p->o->into, sl = p->o->slot;
    char err[64];
    char *merged;
    const char *lines[CLIP_LINES];
    size_t n = 0;
    uint32_t at = 0, set_n;
    char *clip_copy = g_clip;
    if (!a->seq || t < 0 || t >= (int)a->seq_lim.tracks || sl < 0 || sl >= 8) {
      return refuse_load(p, FM1_STATE_BAD, "No such slot", "A clip loads into a track and a slot.%s", "");
    }
    {
      fm1_seq_clip_info_t ci;
      if (fm1_seq_get_clip(a->seq, (uint8_t)t, (uint8_t)sl, &ci) && ci.length_steps && !(flags & FM1_APP_LOAD_REPLACE)) {
        char ts[32];
        snprintf(ts, sizeof ts, "Track %d slot %d", t + 1, sl + 1);
        return refuse_load(p, FM1_STATE_NO_ROOM, "Slot holds a clip", "%s holds a clip; replace it?", ts);
      }
    }
    if (g_set_n > FM1_STATE_CAP_CLIP) return refuse_load(p, FM1_STATE_TOO_BIG, "Clip too big", "The clip is too big.%s", "");
    memcpy(clip_copy, g_set, g_set_n);
    for (uint32_t i = 0; i < g_set_n && n < CLIP_LINES; ++i) {
      if (clip_copy[i] != '\n') continue;
      clip_copy[i] = '\0';
      lines[n++] = clip_copy + at;
      at = i + 1;
    }
    set_n = set_text(a);
    merged = set_n ? fm1_state_clip_into(g_set, set_n, lines, n, (unsigned)t, (unsigned)sl, err, sizeof err) : NULL;
    if (!merged) return refuse_load(p, FM1_STATE_NO_ROOM, "No room", "The clip does not fit: %s.", err);
    free(merged);
    rep->clips = 1;
  }
  /* The report's counts. */
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (!res[u]) continue;
    if (unit_sound(u) >= 0) ++rep->sounds;
    else ++rep->effects;
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) rep->mfx_on = (uint8_t)(rep->mfx_on + mfx_on[k]);
  for (unsigned i = 0; i < FM1_MOD_POSITIONS; ++i) rep->modules = (uint8_t)(rep->modules + p->file_pos[i]);
  for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) rep->cables = (uint8_t)(rep->cables + ((p->file_slots >> i) & 1u));
  rep->voices = (uint8_t)p->n_voices;
  return 1;
}

/* A project starts from fm1_app_init; the settings, MASTER, the host's
 * hooks, the clock and the store are the device's, not the project's. */
static void project_reset(fm1_app_t *a) {
  const float rate = a->host.sample_rate, master = a->master;
  const fm1_app_settings_t settings = a->settings;
  const int metro = metronome_on(a), full_vel = a->ui.full_vel, store = a->store_ready;
  const uint32_t save_gen = a->save_gen;
  const uint64_t frames = a->frames, last_draw = a->last_draw;
  void (*on_cmd)(void *, uint64_t, const fm1_seq_cmd_t *) = a->on_cmd;
  void (*on_note_in)(void *, uint64_t, int, int, int) = a->on_note_in;
  void (*on_mfx)(void *, uint64_t, int, int, float) = a->on_mfx;
  void *cmd_ctx = a->on_cmd_ctx;
  struct fm1_edit *edit = a->edit;       /* the edit layer's ring goes on (fm1_edit.h) */
  fm1_app_all_notes_off(a);
  fm1_app_init(a, rate);
  a->edit = edit;
  a->master = master;
  a->gain = master * master;
  a->settings = settings;
  a->store_ready = store;
  a->save_gen = save_gen;
  a->frames = frames;
  a->last_draw = last_draw;
  a->on_cmd = on_cmd;
  a->on_note_in = on_note_in;
  a->on_mfx = on_mfx;
  a->on_cmd_ctx = cmd_ctx;
  a->ui.full_vel = (uint8_t)full_vel;
  if (metro && a->seq) {
    const int64_t arg[1] = { 1 };
    fm1_seq_cmd_t c;
    fm1_seq_cmd_make(&c, FM1_SEQ_V_METRO, 1, arg);
    fm1_app_seq_cmd(a, &c);
  }
}

static void apply_param(plan_t *p, const fm1_rec_t *r) {
  fm1_app_t *a = p->a;
  const int m = map_unit(p, r->role, r->sound, r->slot);
  if (m >= 0) {
    fm1_app_unit_t *u = &a->unit[m];
    const int idx = u->e ? fm1_param_index(u->e, r->u.param.uid) : -1;
    float v;
    if (idx < 0) return;
    v = rec_value(&u->e->params[idx], r);
    if (p->kind == FM1_STATE_SOUND && u->index == a->dx7.index && idx == a->dx7.patch) {
      const int slot = (int)(v + 0.5f) - DX7_USER0;
      if (slot >= 0 && slot < (int)FM1_DX7_USER_SLOTS) {
        int to = -1;
        for (unsigned i = 0; i < p->n_voices; ++i) {
          if (p->voice_slot[i] == slot) to = p->voice_map[slot];
        }
        v = to >= 0 ? (float)(DX7_USER0 + to) : u->e->params[idx].def;
      }
    }
    if (r->u.param.focus != FM1_FOCUS_NONE && p->focus_idx[m] >= 0) {
      const fm1_param_t *fp = &u->e->params[p->focus_idx[m]];
      fm1_app_set_param(a, m, p->focus_idx[m], fp->min + (float)r->u.param.focus);
      fm1_app_set_param(a, m, idx, v);
    } else if (idx == p->focus_idx[m]) {
      p->focus_has[m] = 1;
      p->focus_val[m] = v;
    } else {
      fm1_app_set_param(a, m, idx, v);
    }
  } else if (m <= -2) {
    const int k = -2 - m;
    /* An unavailable imported effect's UIDs must never address the old
     * slot or the bypassed default installed for it. */
    const fm1_engine_t *e = p->mfx[k] ? fm1_app_mfx_engine(a, k) : NULL;
    const int idx = e ? fm1_param_index(e, r->u.param.uid) : -1;
    if (idx >= 0) fm1_app_arp_set_param(a, k, idx, rec_value(&e->params[idx], r));
  }
}

static void apply_unit(plan_t *p, const fm1_rec_t *r) {
  fm1_app_t *a = p->a;
  const int m = map_unit(p, r->role, r->sound, r->slot);
  const fm1_engine_t *e = rec_engine(r->role, r->u.unit.id);
  if (m >= 0) {
    p->touched[m] = 1;
    p->focus_idx[m] = -1;
    p->focus_has[m] = 0;
    if (e) {
      fm1_app_select(a, m, fm1_app_find(e->id));
      for (uint16_t i = 0; a->unit[m].e && i < a->unit[m].e->n_params; ++i) {
        if (fm1_state_param_focus(a->unit[m].e, i) == 1) p->focus_idx[m] = (int8_t)i;
      }
    } else if (m != 0) {
      fm1_app_select(a, m, -1);
    }
  } else if (m <= -2) {
    const int k = -2 - m;
    if (e) {
      fm1_app_arp_set_on(a, k, 0);
      fm1_app_mfx_select(a, k, e->id);
      e = fm1_app_mfx_engine(a, k);
      for (uint16_t i = 0; e && i < e->n_params; ++i) fm1_app_arp_set_param(a, k, i, e->params[i].def);
    }
  }
}

static int plan_pass2(plan_t *p, const fm1_rec_t *r) {
  fm1_app_t *a = p->a;
  if (p->pass == 3) {                  /* FM6's voices before any unit plays them */
    if (r->type == FM1_REC_DX7 && r->slot < FM1_DX7_USER_SLOTS && p->voice_map[r->slot] >= 0) {
      fm1_app_dx7_put(a, (unsigned)p->voice_map[r->slot], r->u.dx7.vced);
    }
    return 1;
  }
  switch (r->type) {
    case FM1_REC_INFO:
      info_take(p, r);
      break;
    case FM1_REC_UNIT:
      apply_unit(p, r);
      break;
    case FM1_REC_ON: {
      const int m = map_unit(p, r->role, r->sound, r->slot);
      if (m <= -2 && p->mfx[-2 - m]) fm1_app_arp_set_on(a, -2 - m, r->u.on);
      break;
    }
    case FM1_REC_PARAM:
      if (r->role == FM1_ROLE_MODULE) {
        if (!p->sm_ready || r->slot >= FM1_MOD_POSITIONS) break;
        {
          fm1_rec_t q = *r;
          if ((p->o->flags & FM1_APP_LOAD_RESTORE_SOUND) && p->kind == FM1_STATE_SOUND && p->same_mod[r->slot]) break;
          q.slot = (uint8_t)p->pos_map[r->slot];
          fm1_state_mod_sink(&p->sm, &q);
        }
      } else {
        apply_param(p, r);
      }
      break;
    case FM1_REC_LEVEL: {
      const int k = p->kind == FM1_STATE_PROJECT ? r->sound : p->kind == FM1_STATE_SOUND ? p->o->into : -1;
      if (k >= 0 && k < FM1_APP_SOUNDS) fm1_app_unit_set_level(a, k, bits_f(r->u.level));
      break;
    }
    case FM1_REC_MOD: {
      const fm1_engine_t *units[FM1_MOD_SINKS];
      if (p->mod_drop) break;
      if (mod_kind(p->kind)) fm1_app_mod_reset(a, p->has_seed ? p->seed : a->mod_seed);
      if (!a->mod) break;
      fm1_app_mod_units(a, units);
      fm1_state_mod_init(&p->sm, a->mod, names(), units, &p->rep->r);
      p->sm_ready = 1;
      break;
    }
    case FM1_REC_MODULE:
    case FM1_REC_DATA:
      if (p->sm_ready && r->slot < FM1_MOD_POSITIONS) {
        fm1_rec_t q = *r;
        if ((p->o->flags & FM1_APP_LOAD_RESTORE_SOUND) && p->kind == FM1_STATE_SOUND && p->same_mod[r->slot]) break;
        q.slot = (uint8_t)p->pos_map[r->slot];
        fm1_state_mod_sink(&p->sm, &q);
      }
      break;
    case FM1_REC_CABLE:
      if (p->sm_ready && r->slot < FM1_MOD_SLOTS) {
        fm1_rec_t q = *r;
        q.slot = (uint8_t)p->slot_map[r->slot];
        remap_cable(p, &q.u.cable.s);
        fm1_state_mod_sink(&p->sm, &q);
        a->mui.aim[q.slot] = 0;
        a->mui.aim_on &= ~(1u << q.slot);
      }
      break;
    case FM1_REC_LINE:
      gather(g_set, SET_CAP, &g_set_n, &g_set_over, r->u.line.s, r->u.line.n, (r->piece & FM1_REC_LAST) != 0);
      break;
    default:
      break;
  }
  return 1;
}

static int plan_sink(void *ctx, const fm1_rec_t *r) {
  plan_t *p = (plan_t *)ctx;
  return p->pass == 1 ? plan_pass1(p, r) : plan_pass2(p, r);
}

static void apply_view(fm1_app_t *a, const fm1_rec_t *v) {
  const uint16_t has = v->u.view.has;
  const uint8_t *x = v->u.view.v;
#define HAS(key) ((has >> (key)) & 1u)
  if (HAS(FM1_VK_SOUND)) fm1_app_unit_set_current(a, x[FM1_VK_SOUND] - 1);
  switch (v->u.view.mode) {
    case FM1_VIEW_FX:
      a->mode = FM1_MODE_FX;
      a->fx_slot = 2;                    /* Mix, unless a unit says */
      if (HAS(FM1_VK_UNIT)) {
        const unsigned u = x[FM1_VK_UNIT];
        if (u == FM1_MOD_FX1 || u == FM1_MOD_FX2) {
          a->fx_slot = 3 + (int)(u - FM1_MOD_FX1);
        } else if (u >= FM1_MOD_INSERT && u < FM1_MOD_INSERT + 16u && (u - FM1_MOD_INSERT) % 4u < 2u) {
          fm1_app_unit_set_current(a, (int)((u - FM1_MOD_INSERT) / 4u));
          a->fx_slot = (int)((u - FM1_MOD_INSERT) % 4u);
        }
      }
      a->fx_page = HAS(FM1_VK_PAGE) ? x[FM1_VK_PAGE] - 1 : 0;
      break;
    case FM1_VIEW_GLO:
      a->mode = FM1_MODE_GLOBAL;
      a->glo_page = HAS(FM1_VK_PAGE) && x[FM1_VK_PAGE] == 2 ? 1 : 0;
      break;
    case FM1_VIEW_SEQ:
    case FM1_VIEW_SESSION:
    case FM1_VIEW_SONG:
      a->mode = FM1_MODE_SEQ;
      fm1_seq_ui_enter(&a->ui);
      if (HAS(FM1_VK_TRACK) && a->seq && x[FM1_VK_TRACK] <= a->seq_lim.tracks) a->ui.track = (uint8_t)(x[FM1_VK_TRACK] - 1);
      if (HAS(FM1_VK_BAR) && x[FM1_VK_BAR] <= 16) a->ui.bar = (uint8_t)(x[FM1_VK_BAR] - 1);
      if (v->u.view.mode == FM1_VIEW_SESSION) {
        fm1_seq_ui_open(&a->ui, FM1_SEQ_VIEW_SESSION);
      } else if (v->u.view.mode == FM1_VIEW_SONG) {    /* the cursor on its entry, or `+ add` */
        fm1_seq_ui_open_song(&a->ui, HAS(FM1_VK_ENTRY) && x[FM1_VK_ENTRY] >= 1 ? x[FM1_VK_ENTRY] - 1u
                                                                             : FM1_SEQ_UI_SONG_MAX);
      } else if (HAS(FM1_VK_PANEL) && x[FM1_VK_PANEL] == 1) {
        fm1_seq_ui_open(&a->ui, FM1_SEQ_VIEW_SET);
      } else if (HAS(FM1_VK_PANEL) && x[FM1_VK_PANEL] == 2) {
        fm1_seq_ui_open(&a->ui, FM1_SEQ_VIEW_CLIP);
      }
      break;
    case FM1_VIEW_RACK:
      a->mode = FM1_MODE_RACK;
      if (HAS(FM1_VK_POS)) a->mui.pos = (uint8_t)(x[FM1_VK_POS] - 1);
      break;
    case FM1_VIEW_MATRIX:
      a->mode = FM1_MODE_MATRIX;
      if (HAS(FM1_VK_SLOT)) a->mui.slot = (uint8_t)(x[FM1_VK_SLOT] - 1);
      break;
    case FM1_VIEW_CHAIN:
      a->mode = FM1_MODE_CHAIN;
      break;
    default:
      a->mode = FM1_MODE_HOME;
      if (HAS(FM1_VK_PAGE)) a->page = x[FM1_VK_PAGE] - 1;
      break;
  }
  if (a->mode == FM1_MODE_HOME) {
    const fm1_engine_t *e = fm1_app_unit_engine(a, a->sound);
    const int pages = e ? fm1_seq_ui_pages(e) : 1;
    if (a->page >= pages) a->page = pages > 0 ? pages - 1 : 0;
    if (a->page < 0) a->page = 0;
  }
  if (a->mode == FM1_MODE_FX && a->fx_page < 0) a->fx_page = 0;
#undef HAS
  a->dirty = 1;
  a->leds_changed = 1;
}

static void apply_finish(plan_t *p) {
  fm1_app_t *a = p->a;
  /* A pad kit's focus last, and its per-pad knobs read back for the pad
   * it shows. */
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const fm1_app_unit_t *x = &a->unit[u];
    if (!p->touched[u] || !x->e || p->focus_idx[u] < 0) continue;
    if (p->focus_has[u]) fm1_app_set_param(a, u, p->focus_idx[u], p->focus_val[u]);
    for (uint16_t i = 0; x->e->get_param && i < x->e->n_params; ++i) {
      if (fm1_state_param_focus(x->e, i) == 2) fm1_app_set_param(a, u, i, x->e->get_param(x->self, i, FM1_FOCUS_CURRENT));
    }
  }
  if ((p->kind == FM1_STATE_PROJECT || (p->kind == FM1_STATE_SOUND && p->o->into == 0)) && !a->unit[0].e) {
    const int macro = fm1_app_find("macro");
    fm1_app_select(a, 0, macro);
  }
  if ((p->has_set && p->kind == FM1_STATE_PROJECT) || p->kind == FM1_STATE_SET) {
    fm1_app_seq_import(a, g_set, g_set_n);
    if (p->kind == FM1_STATE_SET) fm1_app_seq_default_route(a);
  }
  if (p->kind == FM1_STATE_CLIP && p->has_clip) {
    const char *lines[CLIP_LINES];
    char *clip_copy = g_clip;
    size_t n = 0;
    uint32_t at = 0, clip_n = g_set_n;
    char err[64];
    char *merged;
    memcpy(clip_copy, g_set, clip_n);
    for (uint32_t i = 0; i < clip_n && n < CLIP_LINES; ++i) {
      if (clip_copy[i] != '\n') continue;
      clip_copy[i] = '\0';
      lines[n++] = clip_copy + at;
      at = i + 1;
    }
    if (set_text(a)) {
      merged = fm1_state_clip_into(g_set, g_set_n, lines, n, (unsigned)p->o->into, (unsigned)p->o->slot, err, sizeof err);
      if (merged) {
        fm1_app_seq_import(a, merged, strlen(merged));
        free(merged);
      }
    }
  }
  if (p->kind == FM1_STATE_PROJECT && p->has_session) {
    const fm1_rec_t *s = &p->session;
    int oct = s->u.session.octave, tr = s->u.session.transpose;
    fm1_app_unit_set_current(a, s->u.session.current >= 0 && s->u.session.current < FM1_APP_SOUNDS ? s->u.session.current : 0);
    a->octave = oct < -3 ? -3 : oct > 3 ? 3 : oct;
    a->transpose = tr < -12 ? -12 : tr > 12 ? 12 : tr;
  }
  if (p->kind == FM1_STATE_SETTINGS) {
    if (p->setting_has[FM1_SET_METRONOME] && a->seq && (p->setting[FM1_SET_METRONOME] != 0) != metronome_on(a)) {
      const int64_t arg[1] = { p->setting[FM1_SET_METRONOME] != 0 };
      fm1_seq_cmd_t c;
      fm1_seq_cmd_make(&c, FM1_SEQ_V_METRO, 1, arg);
      fm1_app_seq_cmd(a, &c);
    }
    if (p->setting_has[FM1_SET_FULL_VELOCITY]) a->ui.full_vel = (uint8_t)(p->setting[FM1_SET_FULL_VELOCITY] != 0);
    if (p->setting_has[FM1_SET_COUNT_IN_CLICK]) a->settings.count_in_click = (uint8_t)(p->setting[FM1_SET_COUNT_IN_CLICK] != 0);
    if (p->setting_has[FM1_SET_MIDI_IN_CHANNEL]) {
      const int32_t ch = p->setting[FM1_SET_MIDI_IN_CHANNEL];
      a->settings.midi_in_channel = (uint8_t)(ch < 0 ? 0 : ch > 16 ? 16 : ch);
    }
  }
  if (p->has_view && p->kind == FM1_STATE_PROJECT) apply_view(a, &p->view);
  a->dirty = 1;
  a->leds_changed = 1;
}

static uint32_t sniff(fm1_src_read_t rd, void *rctx, int *enc) {
  uint8_t head[32];
  const uint32_t n = rd(rctx, 0, head, sizeof head);
  *enc = fm1_state_sniff(head, n);
  return n;
}

/* Pass 1 into g_plan. 1 when the load may go ahead. */
static int check(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total, const fm1_app_load_opts_t *o,
                 fm1_app_state_report_t *rep) {
  plan_t *p = &g_plan;
  int ok;
  memset(p, 0, sizeof *p);
  memset(rep, 0, sizeof *rep);
  fm1_state_report_init(&rep->r);
  rep->budget = FM1_APP_RAM_BUDGET;
  p->a = a;
  p->o = o;
  p->rep = rep;
  p->pass = 1;
  g_set_n = 0;
  g_set_over = 0;
  sniff(rd, rctx, &p->enc);
  if (p->enc == 3) {                   /* a .movy1 set: its text is the set */
    p->kind = FM1_STATE_SET;
    if (total > SET_CAP) return refuse_load(p, FM1_STATE_TOO_BIG, "Set too big", "The set is larger than %s.", "64 KiB");
    g_set_n = rd(rctx, 0, (uint8_t *)g_set, total);
    rep->r.kind = FM1_STATE_SET;
    return plan_finish(p);
  }
  if (p->enc == 1) ok = fm1_state_bin_read(rd, rctx, total, plan_sink, p, &rep->r, 0);
  else if (p->enc == 2) ok = fm1_state_json_read(names(), rd, rctx, plan_sink, p, &rep->r);
  else {
    rep->r.code = FM1_STATE_NOT_LUNAR;
    ok = 0;
  }
  if (!ok) return reader_refusal(p);
  return plan_finish(p);
}

int fm1_app_state_check(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                        const fm1_app_load_opts_t *o, fm1_app_state_report_t *rep) {
  fm1_app_load_opts_t none;
  if (!o) {
    fm1_app_load_opts_init(&none);
    o = &none;
  }
  return check(a, rd, rctx, total, o, rep);
}

int fm1_app_state_load(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                       const fm1_app_load_opts_t *o, fm1_app_state_report_t *rep) {
  fm1_app_load_opts_t none;
  plan_t *p = &g_plan;
  void (*on_mod)(void *, uint64_t, const char *);
  void *on_mod_ctx;
  void (*on_mfx)(void *, uint64_t, int, int, float);
  void (*on_cmd)(void *, uint64_t, const fm1_seq_cmd_t *);
  fm1_seq_transport_t carry;
  int edit_was;
  if (!o) {
    fm1_app_load_opts_init(&none);
    o = &none;
  }
  if (!check(a, rd, rctx, total, o, rep)) {
    if (!(o->flags & FM1_APP_LOAD_QUIET)) fm1_app_say(a, FM1_APP_TONE_REFUSE, rep->screen[0], rep->screen[1], NULL);
    return 0;
  }
  /* The transport of a project that goes on playing: read now, before the project is made again. */
  memset(&carry, 0, sizeof carry);
  if ((o->flags & FM1_APP_LOAD_KEEP_TRANSPORT) && p->kind == FM1_STATE_PROJECT && a->seq) {
    fm1_seq_transport_take(a->seq, &carry);
  }
  /* Pass 2. A load is not an edit: the native harness's logs hear none of
   * it, and the edit layer's ring gets one LOADED entry (fm1_edit.h). */
  edit_was = fm1_edit_enter(a, FM1_EDIT_LOAD);
  on_mod = a->on_mod;
  on_mod_ctx = a->on_mod_ctx;
  on_mfx = a->on_mfx;
  on_cmd = a->on_cmd;
  a->on_mod = NULL;
  a->on_mfx = NULL;
  a->on_cmd = NULL;
  if (p->kind == FM1_STATE_PROJECT) {
    project_reset(a);
    a->on_mfx = NULL;
    a->on_cmd = NULL;
    memset(&a->info, 0, sizeof a->info);
  }
  if (p->kind == FM1_STATE_SOUND && (o->flags & FM1_APP_LOAD_RESTORE_SOUND) && a->mod) {
    modf_t f;
    memset(&f, 0, sizeof f); f.mode = MOD_SOUND; f.k = o->into;
    for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_slot_t slot;
      if (fm1_mod_get_slot(a->mod, i, &slot) && keep_cable(&f, &slot)) {
        memset(&slot, 0, sizeof slot);
        slot.src = slot.via = FM1_MOD_NONE;
        fm1_mod_set_slot(a->mod, i, &slot);
      }
    }
  }
  for (int u = 0; u < FM1_APP_UNITS; ++u) p->focus_idx[u] = -1;
  /* The units a merge replaces go first, so the RAM rule never sees the
   * old and the new at once. */
  if (p->kind == FM1_STATE_SOUND || p->kind == FM1_STATE_FX) {
    for (int u = FM1_APP_UNITS - 1; u > 0; --u) {
      if (target_unit(p, u) && unit_sound(u) < 0) fm1_app_select(a, u, -1);
    }
  }
  if (p->kind == FM1_STATE_SOUND) {
    /* Preflight budgets an absent/unavailable MIDI effect as the default
     * bypassed arp. Make the target match that plan before applying records;
     * this also prevents the previous sound's effect leaking into the load. */
    const int k = p->o->into;
    const fm1_engine_t *e = fm1_app_arp_engine();
    fm1_app_arp_set_on(a, k, 0);
    fm1_app_mfx_select(a, k, e->id);
    for (uint16_t i = 0; i < e->n_params; ++i) fm1_app_arp_set_param(a, k, i, e->params[i].def);
  }
  if (p->kind == FM1_STATE_SET) {
    apply_finish(p);
  } else {
    fm1_state_report_t r2;
    fm1_state_report_init(&r2);
    p->pass = 3;
    if (p->enc == 1) fm1_state_bin_read(rd, rctx, total, plan_sink, p, &r2, 0);
    else fm1_state_json_read(names(), rd, rctx, plan_sink, p, &r2);
    p->pass = 2;
    g_set_n = 0;
    g_set_over = 0;
    fm1_state_report_init(&r2);
    if (p->enc == 1) fm1_state_bin_read(rd, rctx, total, plan_sink, p, &r2, 0);
    else fm1_state_json_read(names(), rd, rctx, plan_sink, p, &r2);
    apply_finish(p);
  }
  if (carry.playing && a->seq) {
    /* A Play (the new set's clips launch, or its song starts), then the old clock and playheads over it. */
    fm1_seq_cmd_t c;
    fm1_seq_cmd_make(&c, FM1_SEQ_V_PLAY, 0, NULL);
    if (fm1_app_seq_cmd(a, &c) == FM1_APP_SEQ_APPLIED) fm1_seq_transport_put(a->seq, &carry);
  }
  a->on_mod = on_mod;
  a->on_mod_ctx = on_mod_ctx;
  a->on_mfx = on_mfx;
  a->on_cmd = on_cmd;
  fm1_edit_note_loaded(a);
  fm1_edit_leave(a, edit_was);
  rep->ram = (uint32_t)fm1_app_ram(a);
  rep->percent = (uint16_t)fm1_app_ram_percent(rep->ram);
  snprintf(rep->screen[0], sizeof rep->screen[0], "LOADED");
  snprintf(rep->screen[1], sizeof rep->screen[1], "RAM %u%%", (unsigned)rep->percent);
  snprintf(rep->message, sizeof rep->message, "Loaded %s%s%.32s. RAM %u%%.", kind_word(p->kind),
           p->name[0] ? " " : "", p->name, (unsigned)rep->percent);
  if (!(o->flags & FM1_APP_LOAD_QUIET)) {
    fm1_app_say(a, FM1_APP_TONE_SAY, "LOADED", p->name[0] ? p->name : kind_word(p->kind), rep->screen[1]);
  }
  return 1;
}
