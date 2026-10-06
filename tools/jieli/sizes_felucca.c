/* tools/jieli/sizes_felucca.c -- the Felucca engines' world (engines/src/
 * felucca_bridge.c) as constants in the object file (`fm1sz_<name>`), beside
 * sizes.cc's SZ_FELUCCA (the shim's Instance), for tools/jieli/analyze.py:
 * an instance is AlignUp16(sizeof Instance) + AlignUp16(world), the world
 * being Felucca's part (track_t) and, for Drawbar, WHEEL's part and voice
 * state (felucca_shim.cc InstanceSize).
 *
 * It includes the bridge, so it holds GPL-3.0-only code: compiled only while
 * the GPL switch is on (tools/jieli/in-container.sh), from engines/ with the
 * bridge's include flags (engines/mk/felucca.mk). Compile-only: never
 * linked. MIT licence (this file's own text). */

#include "../../engines/src/felucca_bridge.c"

#define FM1SZ(name, expr) \
  __attribute__((used)) const uint32_t fm1sz_##name = (uint32_t)(expr);

FM1SZ(felucca_track, sizeof(track_t))
FM1SZ(felucca_voice, sizeof(voice_t))
FM1SZ(felucca_world, offsetof(fel_world_t, wheel_part))
FM1SZ(felucca_world_wheel, sizeof(fel_world_t))
FM1SZ(felucca_wheel_part, sizeof(drw_trk_t))
FM1SZ(felucca_wheel_voice, sizeof(drw_vc_t))
