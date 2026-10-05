/* tools/jieli/sizes.c -- the C side of tools/jieli/sizes.cc: ABI facts, the
 * sequencer's internal records, the modulation runtime's state and records,
 * and the simulator app layer's structs, as
 * constants in the object file (`fm1sz_<name>`), read back by
 * tools/jieli/analyze.py for pi32v2, i386 (-m32) and x86-64.
 *
 * Alignment is measured inside a struct (offsetof after a char), because that
 * is what lays out our records; i386, for one, aligns double and uint64_t to 4
 * there and to 8 on their own.
 *
 * Compiled from engines/ with -Iinclude -Iseq -Imod -I../sim/web/src. Compile-only:
 * never linked. MIT licence. */

#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#include "seq_int.h"
#include "mod_int.h"
#include "fm1_app.h"
#include "fm1_engine.h"
#include "fm1_mix_limiter.h"
#include "fm1_resampler.h"

#define FM1SZ(name, expr) \
  __attribute__((used)) const uint32_t fm1sz_##name = (uint32_t)(expr);
#define FM1SZ_ALIGN(name, T)              \
  struct fm1al_##name { char c; T t; };   \
  FM1SZ(abi_align_##name, offsetof(struct fm1al_##name, t))

/* ABI */
FM1SZ(abi_char_signed, (char)-1 < 0)
FM1SZ(abi_sizeof_pointer, sizeof(void *))
FM1SZ(abi_sizeof_long, sizeof(long))
FM1SZ(abi_sizeof_size_t, sizeof(size_t))
FM1SZ(abi_sizeof_wchar_t, sizeof(L'x'))
FM1SZ(abi_sizeof_double, sizeof(double))
FM1SZ(abi_sizeof_long_double, sizeof(long double))
FM1SZ_ALIGN(float, float)
FM1SZ_ALIGN(double, double)
FM1SZ_ALIGN(long_double, long double)
FM1SZ_ALIGN(uint64_t, uint64_t)
FM1SZ_ALIGN(pointer, void *)

/* The engine API and host helpers */
FM1SZ(api_fm1_engine_t, sizeof(fm1_engine_t))
FM1SZ(api_fm1_param_t, sizeof(fm1_param_t))
FM1SZ(api_fm1_host_t, sizeof(fm1_host_t))
FM1SZ(api_fm1_resampler_t, sizeof(fm1_resampler_t))
FM1SZ(api_fm1_mix_limiter_t, sizeof(fm1_mix_limiter_t))

/* The sequencer (seq_int.h promises the same layout on 32 and 64 bits) */
FM1SZ(seq_struct_fm1_seq, sizeof(struct fm1_seq))
FM1SZ(seq_sq_note_t, sizeof(sq_note_t))
FM1SZ(seq_sq_lock_t, sizeof(sq_lock_t))
FM1SZ(seq_sq_trig_t, sizeof(sq_trig_t))
FM1SZ(seq_sq_seg_t, sizeof(sq_seg_t))
FM1SZ(seq_sq_clip_t, sizeof(sq_clip_t))
FM1SZ(seq_sq_track_t, sizeof(sq_track_t))
FM1SZ(seq_sq_gate_t, sizeof(sq_gate_t))
FM1SZ(seq_sq_rec_t, sizeof(sq_rec_t))
FM1SZ(seq_sq_cap_t, sizeof(sq_cap_t))
FM1SZ(seq_sq_props_t, sizeof(sq_props_t))
FM1SZ(seq_fm1_seq_limits_t, sizeof(fm1_seq_limits_t))
FM1SZ(seq_fm1_seq_ev_t, sizeof(fm1_seq_ev_t))
FM1SZ(seq_fm1_seq_cmd_t, sizeof(fm1_seq_cmd_t))

/* The modulation runtime (mod_int.h: no pointers, the same layout at 32
 * and 64 bits; fm1_mod_size() rounds struct fm1_mod up to 16) */
FM1SZ(mod_struct_fm1_mod, sizeof(struct fm1_mod))
FM1SZ(mod_fm1_mod_size, (sizeof(struct fm1_mod) + 15u) & ~(size_t)15u)
FM1SZ(mod_offsetof_now, offsetof(struct fm1_mod, now))
FM1SZ(mod_offsetof_plan, offsetof(struct fm1_mod, plan))
FM1SZ(mod_offsetof_slot, offsetof(struct fm1_mod, slot))
FM1SZ(mod_fm1_mod_slot_t, sizeof(fm1_mod_slot_t))
FM1SZ(mod_fm1_mod_gate_t, sizeof(fm1_mod_gate_t))
FM1SZ(mod_fm1_mod_kind_t, sizeof(fm1_mod_kind_t))
FM1SZ(mod_fm1_mod_io_t, sizeof(fm1_mod_io_t))
FM1SZ(mod_fm1_mp_lfo_t, sizeof(fm1_mp_lfo_t))
FM1SZ(mod_fm1_mp_env_t, sizeof(fm1_mp_env_t))

/* The simulator's app layer */
FM1SZ(app_fm1_app_t, sizeof(fm1_app_t))
FM1SZ(app_fm1_app_unit_t, sizeof(fm1_app_unit_t))
FM1SZ(app_fm1_tft_t, sizeof(fm1_tft_t))
FM1SZ(app_state_before_arenas, offsetof(fm1_app_t, sound_mem))
FM1SZ(app_arenas, sizeof(fm1_app_t) - offsetof(fm1_app_t, sound_mem))
