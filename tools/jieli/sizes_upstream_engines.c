/* tools/jieli/sizes_upstream_engines.c -- the upstream engines' world (engines/src/
 * upstream_engine_bridge.c) as constants in the object file (`fm1sz_<name>`), beside
 * sizes.cc's SZ_UPSTREAM_ENGINES (the shim's Instance), for tools/jieli/analyze.py:
 * an instance is AlignUp16(sizeof Instance) + AlignUp16(world), the world
 * being the vendor's part (track_t) and, for Drawbar, WHEEL's part and voice
 * state (upstream_engine_shim.cc InstanceSize).
 *
 * It includes the bridge, so it holds GPL-3.0-only code: compiled only while
 * the GPL switch is on (tools/jieli/in-container.sh), from engines/ with the
 * bridge's include flags (engines/mk/upstream_engines.mk). Compile-only: never
 * linked. MIT licence (this file's own text). */

#include "../../engines/src/upstream_engine_bridge.c"

#define FM1SZ(name, expr) \
  __attribute__((used)) const uint32_t fm1sz_##name = (uint32_t)(expr);

FM1SZ(upstream_engine_track, sizeof(track_t))
FM1SZ(upstream_engine_voice, sizeof(voice_t))
FM1SZ(upstream_engine_world, offsetof(upstream_engine_world_t, wheel_part))
FM1SZ(upstream_engine_world_wheel, sizeof(upstream_engine_world_t))
FM1SZ(upstream_engine_wheel_part, sizeof(drw_trk_t))
FM1SZ(upstream_engine_wheel_voice, sizeof(drw_vc_t))
