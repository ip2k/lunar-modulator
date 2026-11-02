/* Selected Trio PROJECT applier. MIT. This intentionally accepts only the
 * 30-record starter shape; the service's general PROJECT/SET/SAVE contract
 * remains unsupported by the native diagnostic. */
#include "selected_project.h"

#include <stdint.h>
#include <string.h>

typedef struct selected_plan {
  fm1_app_info_t info;
  uint32_t value_bits[FM1_APP_MAX_PARAMS];
  uint32_t seen_params;
  uint32_t level_bits;
  uint8_t infos;
  uint8_t phase;
  uint8_t null_unit;
  uint8_t have_level;
  uint8_t info_key;
  uint16_t info_used;
} selected_plan_t;

typedef struct selected_scan {
  selected_plan_t *plan;
  const fm1_engine_t *engine;
  fm1_state_report_t *report;
} selected_scan_t;

typedef struct selected_source {
  const uint8_t *bytes;
  uint32_t size;
} selected_source_t;

static int selected_overlap(const void *a, size_t an, const void *b, size_t bn) {
  uintptr_t ap = (uintptr_t)a, bp = (uintptr_t)b;
  if (!a || !b || an > UINTPTR_MAX - ap || bn > UINTPTR_MAX - bp) return 1;
  return ap < bp + bn && bp < ap + an;
}

/* This is a cold diagnostic, not a loader for an app with host attachments.
 * Refuse redirected live storage before even initializing the caller's report:
 * that report (or reader scratch) might itself occupy the redirected object. */
static int selected_fresh_topology(const fm1_app_t *app) {
  const fm1_midi_fx_t *arp = fm1_midi_fx_find("arp");
  if (!app || app->edit || app->on_cmd || app->on_note_in ||
      app->on_mfx || app->on_mod ||
      app->seq != (const fm1_seq_t *)(const void *)app->seq_mem ||
      app->mod != (const fm1_mod_t *)(const void *)app->mod_mem ||
      app->seq_host.seq != app->seq || app->seq_host.ev != app->seq_ev ||
      app->seq_host.mfx != &app->mfx || app->seq_host.engine ||
      app->mod_glue.mod != app->mod || app->mod_glue.ctx != app ||
      app->mod_glue.hook.ctx != &app->mod_glue || app->mod_glue.sound)
    return 0;
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    for (unsigned slot = 0; slot < FM1_MFX_SLOTS; ++slot) {
      const fm1_mfx_slot_t *m = &app->mfx.chain[k].slot[slot];
      if (slot == 0) {
        if (m->fx != arp ||
            (m->self && m->self != (const void *)app->mfx_mem[k])) return 0;
      } else if (m->fx || m->self) return 0;
    }
  }
  return 1;
}

static uint32_t selected_read(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const selected_source_t *src = (const selected_source_t *)ctx;
  if (off >= src->size) return 0;
  if (n > src->size - off) n = src->size - off;
  memcpy(out, src->bytes + off, n);
  return n;
}

static int selected_bad(selected_scan_t *s, const char *why) {
  s->report->code = FM1_STATE_BAD;
  memset(s->report->what, 0, sizeof s->report->what);
  size_t n = strlen(why);
  if (n >= sizeof s->report->what) n = sizeof s->report->what - 1u;
  memcpy(s->report->what, why, n);
  return 0;
}

static int selected_complete(fm1_state_report_t *report, const selected_plan_t *plan) {
  if (report->code != FM1_STATE_OK || plan->phase != 4) return 0;
  if (report->skipped || report->repaired || report->unknown || report->defaulted) {
    report->code = FM1_STATE_BAD;
    memcpy(report->what, "selected project has unsupported data",
           sizeof "selected project has unsupported data");
    return 0;
  }
  return 1;
}

static int selected_info(selected_scan_t *s, const fm1_rec_t *r) {
  selected_plan_t *p = s->plan;
  char *dest;
  size_t cap;
  unsigned bit;
  if (p->phase != 1 || (r->piece & ~(FM1_REC_FIRST | FM1_REC_LAST)) ||
      (!r->u.info.s && r->u.info.n)) return selected_bad(s, "unsupported info record");
  switch (r->u.info.key) {
    case FM1_INFO_BY:      dest = NULL; cap = 64; bit = 1u; break;
    case FM1_INFO_NAME:    dest = p->info.name; cap = sizeof p->info.name; bit = 2u; break;
    case FM1_INFO_TITLE:   dest = p->info.title; cap = sizeof p->info.title; bit = 4u; break;
    case FM1_INFO_ABOUT:   dest = p->info.about; cap = sizeof p->info.about; bit = 8u; break;
    case FM1_INFO_LICENCE: dest = p->info.licence; cap = sizeof p->info.licence; bit = 16u; break;
    default: return selected_bad(s, "unsupported info key");
  }
  if (r->piece & FM1_REC_FIRST) {
    if (p->info_key || (p->infos & bit))
      return selected_bad(s, "duplicate or interleaved info");
    p->info_key = r->u.info.key;
    p->info_used = 0;
    p->infos = (uint8_t)(p->infos | bit);
  } else if (p->info_key != r->u.info.key) {
    return selected_bad(s, "info piece without start");
  }
  if (r->u.info.n >= cap - p->info_used)
    return selected_bad(s, "oversized info");
  if (dest && r->u.info.n) memcpy(dest + p->info_used, r->u.info.s, r->u.info.n);
  p->info_used = (uint16_t)(p->info_used + r->u.info.n);
  if (r->piece & FM1_REC_LAST) { p->info_key = 0; p->info_used = 0; }
  return 1;
}

static int selected_param(selected_scan_t *s, const fm1_rec_t *r) {
  selected_plan_t *p = s->plan;
  const int i = fm1_param_index(s->engine, r->u.param.uid);
  if (p->phase != 2 || r->role != FM1_ROLE_SOUND || r->sound != 0 ||
      r->slot != 0 || r->u.param.focus != FM1_FOCUS_NONE ||
      i < 0 || i >= FM1_APP_MAX_PARAMS || (p->seen_params & (1u << i)))
    return selected_bad(s, "unsupported or duplicate Trio parameter");
  const fm1_param_t *def = &s->engine->params[i];
  if (def->flags & (FM1_PARAM_FOCUS | FM1_PARAM_PER_FOCUS))
    return selected_bad(s, "focused parameter unsupported");
  if (def->type == FM1_PARAM_ENUM) {
    if (r->u.param.vtype != FM1_VAL_INDEX ||
        r->u.param.bits > (uint32_t)(def->max - def->min))
      return selected_bad(s, "invalid Trio enum");
  } else if (def->type == FM1_PARAM_FLOAT) {
    float value;
    if (r->u.param.vtype != FM1_VAL_F32)
      return selected_bad(s, "invalid Trio float type");
    memcpy(&value, &r->u.param.bits, sizeof value);
    if (!(value >= def->min && value <= def->max))
      return selected_bad(s, "Trio float outside range");
  } else return selected_bad(s, "unknown Trio parameter type");
  p->seen_params |= 1u << i;
  p->value_bits[i] = r->u.param.bits;
  return 1;
}

static int selected_null_unit(selected_scan_t *s, const fm1_rec_t *r) {
  /* The fixed project has two empty Sound 1 inserts, Sounds 2-4 and two
   * empty master slots. The exact order is the current codec's order. */
  static const uint8_t role[7] = {
    FM1_ROLE_INSERT, FM1_ROLE_INSERT, FM1_ROLE_SOUND, FM1_ROLE_SOUND,
    FM1_ROLE_SOUND, FM1_ROLE_MASTER, FM1_ROLE_MASTER
  };
  static const uint8_t sound[7] = {0, 0, 1, 2, 3, 0, 0};
  static const uint8_t slot[7] = {0, 1, 0, 0, 0, 0, 1};
  selected_plan_t *p = s->plan;
  if (p->phase != 3 || p->null_unit >= 7 ||
      r->role != role[p->null_unit] || r->sound != sound[p->null_unit] ||
      r->slot != slot[p->null_unit] || r->u.unit.id[0])
    return selected_bad(s, "unsupported project unit");
  ++p->null_unit;
  return 1;
}

static int selected_sink(void *ctx, const fm1_rec_t *r) {
  selected_scan_t *s = (selected_scan_t *)ctx;
  selected_plan_t *p = s->plan;
  switch (r->type) {
    case FM1_REC_HEAD:
      if (p->phase || r->u.head.kind != FM1_STATE_PROJECT ||
          r->u.head.major != FM1_STATE_MAJOR || r->u.head.minor > FM1_STATE_MINOR)
        return selected_bad(s, "unsupported project header");
      p->phase = 1;
      return 1;
    case FM1_REC_INFO:
      return selected_info(s, r);
    case FM1_REC_UNIT:
      if (p->phase == 1 && p->infos == 31u && !p->info_key &&
          r->role == FM1_ROLE_SOUND &&
          r->sound == 0 && r->slot == 0 &&
          memchr(r->u.unit.id, 0, sizeof r->u.unit.id) &&
          strcmp(r->u.unit.id, "trio") == 0) {
        p->phase = 2;
        return 1;
      }
      return selected_null_unit(s, r);
    case FM1_REC_PARAM:
      return selected_param(s, r);
    case FM1_REC_LEVEL: {
      float level;
      if (p->phase != 2 || p->have_level || r->sound != 0 ||
          p->seen_params != ((1u << s->engine->n_params) - 1u))
        return selected_bad(s, "missing or duplicate Trio level");
      memcpy(&level, &r->u.level, sizeof level);
      if (!(level >= 0.0f && level <= FM1_APP_LEVEL_MAX))
        return selected_bad(s, "Trio level outside range");
      p->level_bits = r->u.level;
      p->have_level = 1;
      p->phase = 3;
      return 1;
    }
    case FM1_REC_END:
      if (p->phase != 3 || p->null_unit != 7)
        return selected_bad(s, "incomplete selected project");
      p->phase = 4;
      return 1;
    default:
      return selected_bad(s, "record unsupported by native diagnostic");
  }
}

int lunar_selected_project_load(fm1_app_t *app, const uint8_t *packed,
    uint32_t packed_bytes, void *reader, size_t reader_bytes,
    fm1_state_report_t *report) {
  selected_plan_t first, second;
  selected_source_t source;
  selected_scan_t scan;
  fm1_state_report_t second_report;
  const fm1_engine_t *engine = fm1_engine_find("trio");
  int index;
  if (!report) return 0;
  if (app && !selected_fresh_topology(app)) return 0;
  /* Never write a refusal report into caller-owned live input or scratch. */
  if ((app && selected_overlap(report, sizeof *report, app, sizeof *app)) ||
      (packed && packed_bytes && selected_overlap(report, sizeof *report, packed, packed_bytes)) ||
      (reader && reader_bytes && selected_overlap(report, sizeof *report, reader, reader_bytes)))
    return 0;
  if (app) for (int i = 0; i < FM1_APP_UNITS; ++i) {
    if (app->unit[i].cap &&
        selected_overlap(report, sizeof *report, app->unit[i].mem, app->unit[i].cap)) return 0;
  }
  fm1_state_report_init(report);
  if (!app || !packed || !reader || !packed_bytes ||
      packed_bytes > FM1_STATE_BIN_MAX ||
      reader_bytes < fm1_state_bin_reader_size() ||
      ((uintptr_t)reader & 15u) || !app->external_arenas || app->frames ||
      selected_overlap(reader, reader_bytes, packed, packed_bytes) ||
      selected_overlap(reader, reader_bytes, app, sizeof *app) ||
      selected_overlap(packed, packed_bytes, app, sizeof *app) ||
      !engine || engine->kind != FM1_KIND_SOUND ||
      engine->n_params != 14 || engine->n_params > FM1_APP_MAX_PARAMS) {
    report->code = FM1_STATE_BAD;
    return 0;
  }
  for (int i = 0; i < FM1_APP_UNITS; ++i) {
    if (app->unit[i].e) { report->code = FM1_STATE_BAD; return 0; }
    if (app->unit[i].cap &&
        (selected_overlap(reader, reader_bytes, app->unit[i].mem, app->unit[i].cap) ||
         selected_overlap(packed, packed_bytes, app->unit[i].mem, app->unit[i].cap))) {
      report->code = FM1_STATE_BAD;
      return 0;
    }
  }
  index = fm1_app_find("trio");
  if (index < 0) { report->code = FM1_STATE_UNKNOWN; return 0; }
  source.bytes = packed;
  source.size = packed_bytes;
  memset(&first, 0, sizeof first);
  scan.plan = &first;
  scan.engine = engine;
  scan.report = report;
  if (!fm1_state_bin_read_workspace(reader, reader_bytes, selected_read,
          &source, packed_bytes, selected_sink, &scan, report, 0) ||
      !selected_complete(report, &first)) return 0;

  memset(&second, 0, sizeof second);
  fm1_state_report_init(&second_report);
  scan.plan = &second;
  scan.report = &second_report;
  if (!fm1_state_bin_read_workspace(reader, reader_bytes, selected_read,
          &source, packed_bytes, selected_sink, &scan, &second_report, 0) ||
      !selected_complete(&second_report, &second) ||
      memcmp(&first, &second, sizeof first) != 0) {
    *report = second_report;
    if (report->code == FM1_STATE_OK) report->code = FM1_STATE_BAD;
    return 0;
  }

  /* All file refusals are complete. Selection is the only constructor and
   * may still report rate, arena or RAM refusal; that is not a file refusal. */
  int selected = fm1_app_select(app, 0, index);
  if (selected) {
    report->code = selected == FM1_APP_SELECT_RATE ? FM1_STATE_RATE :
                   selected == FM1_APP_SELECT_RAM ? FM1_STATE_RAM : FM1_STATE_NO_ROOM;
    return 0;
  }
  for (unsigned i = 0; i < engine->n_params; ++i) {
    float value;
    if (engine->params[i].type == FM1_PARAM_ENUM) {
      value = engine->params[i].min + (float)first.value_bits[i];
    } else memcpy(&value, &first.value_bits[i], sizeof value);
    fm1_app_set_param(app, 0, (int)i, value);
  }
  float level;
  memcpy(&level, &first.level_bits, sizeof level);
  fm1_app_unit_set_level(app, 0, level);
  app->info = first.info;
  return 1;
}
