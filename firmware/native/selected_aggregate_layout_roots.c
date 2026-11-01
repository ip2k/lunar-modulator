/* SPDX-License-Identifier: MIT
 * Compile/link layout experiment only. Nothing here is called at startup. */
#if !defined(LUNAR_SELECTED_INTERACTIVE_PROOF) || LUNAR_SELECTED_INTERACTIVE_PROOF != 1
#error "aggregate layout requires selected interactive proof"
#endif
#if !defined(LUNAR_DIAGNOSTIC_OFFLINE_PROOF) || LUNAR_DIAGNOSTIC_OFFLINE_PROOF != 1
#error "aggregate layout requires offline proof"
#endif
#if !defined(LUNAR_SELECTED_PROJECT_STAGE_PROOF) || LUNAR_SELECTED_PROJECT_STAGE_PROOF != 1
#error "aggregate layout requires PROJECT stage proof"
#endif
#if !defined(LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION) || LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION != 1
#error "aggregate layout requires pi32v2 publication"
#endif
#if !defined(LUNAR_DIAGNOSTIC_CPU0_ONLY) || LUNAR_DIAGNOSTIC_CPU0_ONLY != 1
#error "aggregate layout requires CPU0-only publication"
#endif
#if !defined(FM1_APP_EXTERNAL_ARENAS) || FM1_APP_EXTERNAL_ARENAS != 1
#error "aggregate layout requires external sound arena"
#endif
#if !defined(FM1_APP_STATE_EXTERNAL_WORKSPACE) || FM1_APP_STATE_EXTERNAL_WORKSPACE != 1
#error "aggregate layout requires external PROJECT workspace"
#endif
#ifdef FM1_APP_RENDER_PIPELINE
#error "aggregate layout cannot admit pending render pipeline work"
#endif

#include "selected_owner_storage.h"
#include "selected_interactive_app.h"
#include "diagnostic_api.h"

/* These are target globals, not reference-model storage. The only app, sound
 * arena, TFT frame, and PROJECT workspace remain in selected_diagnostic_app.c.
 * Queue capacities are fixed offline proof inputs, not release defaults. */
lunar_selected_platform_t lunar_selected_aggregate_platform __attribute__((aligned(16)));
lunar_input_t lunar_selected_aggregate_input[16] __attribute__((aligned(16)));
lunar_pcm_t lunar_selected_aggregate_pcm[2] __attribute__((aligned(16)));
_Static_assert(sizeof(lunar_input_t) == 8, "input event layout changed");
_Static_assert(sizeof(lunar_pcm_t) == 512, "64-frame stereo PCM layout changed");

/* The private builder passes -u/--undefined for this external symbol.
 * -fdata-sections isolates this table; its relocations keep the actual stage,
 * owner, platform and storage despite --gc-sections. */
const struct {
  __typeof__(&lunar_selected_interactive_stage) stage;
  __typeof__(&lunar_selected_owner_init) owner_init;
  __typeof__(&lunar_selected_owner_step) owner_step;
  __typeof__(&lunar_selected_platform_start) platform_start;
  __typeof__(&lunar_selected_platform_main) platform_main;
  __typeof__(&lunar_selected_platform_timer) platform_timer;
  __typeof__(&lunar_selected_platform_audio) platform_audio;
  __typeof__(&lunar_selected_platform_matrix) platform_matrix;
  __typeof__(&lunar_selected_platform_encoder) platform_encoder;
  __typeof__(&lunar_diagnostic_init) app_init;
  lunar_selected_platform_t *platform;
  lunar_input_t *input;
  lunar_pcm_t *pcm;
} lunar_selected_aggregate_layout_roots
    __attribute__((used)) = {
  lunar_selected_interactive_stage,
  lunar_selected_owner_init, lunar_selected_owner_step,
  lunar_selected_platform_start, lunar_selected_platform_main,
  lunar_selected_platform_timer, lunar_selected_platform_audio,
  lunar_selected_platform_matrix, lunar_selected_platform_encoder,
  lunar_diagnostic_init,
  &lunar_selected_aggregate_platform,
  lunar_selected_aggregate_input,
  lunar_selected_aggregate_pcm,
};
