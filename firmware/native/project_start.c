#include "project_start.h"
#include <string.h>

#if FM1_APP_EXTERNAL_ARENAS
typedef char parameter_capacity_match[
    FM1_APP_MAX_PARAMS == LUNAR_PROJECT_ENGINE_PARAMS ? 1 : -1];

int lunar_project_adopt_audio_units(fm1_app_t *app,
                                    lunar_project_engines_t *candidate) {
    fm1_app_unit_t units[FM1_APP_UNITS];
    int result;
    if (!app || !candidate || !candidate->pool ||
        app->storage_ctx != candidate->pool) return FM1_APP_SELECT_BAD;
    /* Metadata/input must survive until every transfer has completed. */
    uintptr_t lo = (uintptr_t)candidate, hi = lo + sizeof *candidate;
    uintptr_t al = (uintptr_t)app, ah = al + sizeof *app;
    if (hi < lo || ah < al || (lo < ah && al < hi) ||
        (lo < candidate->pool->hi && candidate->pool->lo < hi))
        return FM1_APP_SELECT_BAD;
    memset(units, 0, sizeof units);
    for (int i = 0; i < FM1_APP_UNITS; ++i) units[i].index = -1;
    for (unsigned i = 0; i < 14u; ++i) {
        const lunar_project_instance_t *from = &candidate->unit[i];
        int slot = i < 4u ? fm1_app_sound_unit((int)i) :
                   i < 12u ? fm1_app_insert_unit((int)((i - 4u) / 2u), (int)((i - 4u) % 2u)) :
                   1 + (int)(i - 12u);
        fm1_app_unit_t *to = &units[slot];
        if (!from->engine) {
            if (from->memory || from->self || from->bytes) return FM1_APP_SELECT_BAD;
            continue;
        }
        size_t index;
        for (index = 0; index < fm1_engine_count; ++index)
            if (fm1_engines[index] == from->engine) break;
        if (index == fm1_engine_count) return FM1_APP_SELECT_BAD;
        to->e = from->engine; to->index = (int)index;
        to->mem = from->memory; to->self = from->self;
        to->bytes = to->cap = from->bytes;
        memcpy(to->value, from->value, sizeof to->value);
    }
    result = fm1_app_adopt_start_units(app, units);
    if (result != FM1_APP_SELECT_OK) return result;
    /* No operation after app transfer may refuse. */
    memset(candidate->unit, 0, 14u * sizeof candidate->unit[0]);
    return FM1_APP_SELECT_OK;
}
#endif
