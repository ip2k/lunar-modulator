/* state_print.c -- records as text, one JSON object a line (fm1-state
 * records; tools/lunar_state.py prints the same, and the tests compare the
 * two). Pieces are joined; floats are their bits in hex, so the comparison
 * is exact. C99, no heap, no stdio. MIT licence. */
#include "fm1_state.h"

#include <string.h>

static void out(fm1_state_printer_t *p, const char *s) { p->put(p->ctx, s, strlen(s)); }

static void outn(fm1_state_printer_t *p, const char *s, size_t n) { p->put(p->ctx, s, n); }

static void num(fm1_state_printer_t *p, long long v) {
  char t[24];
  int n = 0;
  unsigned long long a = v < 0 ? 0ull - (unsigned long long)v : (unsigned long long)v;
  if (v < 0) out(p, "-");
  do { t[n++] = (char)('0' + a % 10u); a /= 10u; } while (a);
  while (n) { --n; outn(p, &t[n], 1); }
}

static void hex32(fm1_state_printer_t *p, uint32_t v) {
  static const char hx[] = "0123456789abcdef";
  char t[10];
  int i;
  t[0] = '"';
  for (i = 0; i < 8; ++i) t[1 + i] = hx[(v >> (28 - 4 * i)) & 15u];
  t[9] = '"';
  outn(p, t, 10);
}

static void hexbytes(fm1_state_printer_t *p, const uint8_t *b, size_t n) {
  static const char hx[] = "0123456789abcdef";
  size_t i;
  for (i = 0; i < n; ++i) {
    char t[2];
    t[0] = hx[b[i] >> 4];
    t[1] = hx[b[i] & 15u];
    outn(p, t, 2);
  }
}

/* The inside of a JSON string: '"' and '\' escaped, controls as \u00XX. */
static void esc(fm1_state_printer_t *p, const char *s, size_t n) {
  static const char hx[] = "0123456789abcdef";
  size_t i, run = 0;
  for (i = 0; i < n; ++i) {
    const unsigned char c = (unsigned char)s[i];
    if (c == '"' || c == '\\' || c < 0x20u) {
      char u[6];
      if (run) outn(p, s + i - run, run);
      run = 0;
      if (c == '"') out(p, "\\\"");
      else if (c == '\\') out(p, "\\\\");
      else {
        u[0] = '\\'; u[1] = 'u'; u[2] = '0'; u[3] = '0'; u[4] = hx[c >> 4]; u[5] = hx[c & 15u];
        outn(p, u, 6);
      }
    } else {
      ++run;
    }
  }
  if (run) outn(p, s + n - run, run);
}

static void str(fm1_state_printer_t *p, const char *s) {
  out(p, "\"");
  esc(p, s, strlen(s));
  out(p, "\"");
}

static const char *role_name(unsigned r) {
  static const char *const k[6] = { "none", "sound", "insert", "master", "mfx", "module" };
  return r < 6 ? k[r] : "?";
}

static void unit_ref(fm1_state_printer_t *p, const fm1_rec_t *r) {
  out(p, ",\"role\":"); str(p, role_name(r->role));
  out(p, ",\"sound\":"); num(p, r->sound);
  out(p, ",\"slot\":"); num(p, r->slot);
}

void fm1_state_printer_init(fm1_state_printer_t *p, fm1_put_t put, void *ctx) {
  memset(p, 0, sizeof(*p));
  p->put = put;
  p->ctx = ctx;
}

int fm1_state_print(void *pv, const fm1_rec_t *r) {
  static const char *const kInfo[FM1_INFO_KEYS] = { "?", "by", "version", "commit", "name", "title",
                                                    "about", "author", "licence" };
  static const char *const kSet[FM1_SET_KEYS] = { "?", "metronome", "count_in_click", "full_velocity",
                                                  "midi_in_channel" };
  static const char *const kVKeys[FM1_VIEW_KEYS] = { "sound", "page", "unit", "track", "bar", "panel",
                                                     "pos", "slot", "entry" };
  fm1_state_printer_t *p = (fm1_state_printer_t *)pv;
  unsigned i;
  /* Pieces: the line opens at the first and closes at the last. */
  if (r->type == FM1_REC_INFO || r->type == FM1_REC_LINE || r->type == FM1_REC_DATA) {
    if (r->piece & FM1_REC_FIRST) {
      if (r->type == FM1_REC_INFO) {
        out(p, "{\"rec\":\"info\",\"key\":");
        str(p, r->u.info.key < FM1_INFO_KEYS ? kInfo[r->u.info.key] : "?");
        out(p, ",\"text\":\"");
      } else if (r->type == FM1_REC_LINE) {
        out(p, "{\"rec\":\"line\",\"which\":");
        str(p, r->u.line.which == FM1_LINES_CLIP ? "clip" : "set");
        out(p, ",\"text\":\"");
      } else {
        out(p, "{\"rec\":\"data\",\"pos\":");
        num(p, r->slot);
        out(p, ",\"version\":");
        num(p, r->u.data.version);
        out(p, ",\"hex\":\"");
      }
    }
    if (r->type == FM1_REC_INFO) esc(p, r->u.info.s, r->u.info.n);
    else if (r->type == FM1_REC_LINE) esc(p, r->u.line.s, r->u.line.n);
    else hexbytes(p, r->u.data.b, r->u.data.n);
    if (r->piece & FM1_REC_LAST) out(p, "\"}\n");
    return 1;
  }
  switch (r->type) {
    case FM1_REC_HEAD:
      out(p, "{\"rec\":\"head\",\"kind\":");
      str(p, fm1_state_kind_name(r->u.head.kind) ? fm1_state_kind_name(r->u.head.kind) : "?");
      out(p, ",\"major\":"); num(p, r->u.head.major);
      out(p, ",\"minor\":"); num(p, r->u.head.minor);
      break;
    case FM1_REC_SESSION:
      out(p, "{\"rec\":\"session\",\"current\":"); num(p, r->u.session.current);
      out(p, ",\"octave\":"); num(p, r->u.session.octave);
      out(p, ",\"transpose\":"); num(p, r->u.session.transpose);
      if (r->u.session.has_key) {
        out(p, ",\"root\":"); num(p, r->u.session.root);
        out(p, ",\"scale\":"); str(p, r->u.session.scale);
      }
      break;
    case FM1_REC_UNIT:
      out(p, "{\"rec\":\"unit\"");
      unit_ref(p, r);
      out(p, ",\"engine\":"); str(p, r->u.unit.id);
      break;
    case FM1_REC_ON:
      out(p, "{\"rec\":\"on\"");
      unit_ref(p, r);
      out(p, r->u.on ? ",\"on\":true" : ",\"on\":false");
      break;
    case FM1_REC_PARAM:
      out(p, "{\"rec\":\"param\"");
      unit_ref(p, r);
      out(p, ",\"uid\":"); num(p, r->u.param.uid);
      out(p, ",\"focus\":");
      if (r->u.param.focus == FM1_FOCUS_NONE) out(p, "null");
      else num(p, r->u.param.focus);
      if (r->u.param.vtype == FM1_VAL_INDEX) { out(p, ",\"index\":"); num(p, r->u.param.bits); }
      else { out(p, ",\"f32\":"); hex32(p, r->u.param.bits); }
      break;
    case FM1_REC_LEVEL:
      out(p, "{\"rec\":\"level\",\"sound\":"); num(p, r->sound);
      out(p, ",\"f32\":"); hex32(p, r->u.level);
      break;
    case FM1_REC_DX7:
      out(p, "{\"rec\":\"dx7\",\"slot\":"); num(p, r->slot);
      out(p, ",\"vced\":\""); hexbytes(p, r->u.dx7.vced, 155); out(p, "\"");
      break;
    case FM1_REC_MOD:
      out(p, "{\"rec\":\"mod\"");
      break;
    case FM1_REC_SEED:
      out(p, "{\"rec\":\"seed\",\"seed\":"); num(p, r->u.seed);
      break;
    case FM1_REC_MODULE:
      out(p, "{\"rec\":\"module\",\"pos\":"); num(p, r->slot);
      out(p, ",\"kind\":"); str(p, r->u.unit.id);
      break;
    case FM1_REC_CABLE: {
      const fm1_mod_slot_t *s = &r->u.cable.s;
      out(p, "{\"rec\":\"cable\",\"slot\":"); num(p, r->slot);
      out(p, ",\"src\":"); num(p, s->src);
      out(p, ",\"via\":"); num(p, s->via);
      out(p, ",\"unit\":"); num(p, s->dst_unit);
      out(p, ",\"flags\":"); num(p, s->flags);
      out(p, ",\"dst\":"); num(p, s->dst);
      out(p, ",\"amount\":"); num(p, s->amount);
      out(p, ",\"offset\":"); num(p, s->offset);
      out(p, ",\"lock\":"); num(p, s->uid);
      out(p, ",\"name\":"); str(p, r->u.cable.name);
      break;
    }
    case FM1_REC_VIEW:
      out(p, "{\"rec\":\"view\",\"mode\":"); num(p, r->u.view.mode);
      for (i = 0; i < FM1_VIEW_KEYS; ++i) {
        if (!((r->u.view.has >> i) & 1u)) continue;
        out(p, ",\""); out(p, kVKeys[i]); out(p, "\":"); num(p, r->u.view.v[i]);
      }
      break;
    case FM1_REC_SETTING:
      out(p, "{\"rec\":\"setting\",\"key\":");
      str(p, r->u.setting.key < FM1_SET_KEYS ? kSet[r->u.setting.key] : "?");
      if (r->u.setting.is_bool) out(p, r->u.setting.value ? ",\"bool\":true" : ",\"bool\":false");
      else { out(p, ",\"int\":"); num(p, r->u.setting.value); }
      break;
    case FM1_REC_END:
      out(p, "{\"rec\":\"end\"");
      break;
    default:
      out(p, "{\"rec\":\"?\"");
      break;
  }
  out(p, "}\n");
  return 1;
}
