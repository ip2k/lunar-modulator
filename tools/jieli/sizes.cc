// tools/jieli/sizes.cc -- every engine's instance size as a constant in the
// object file, so a cross-compiler reports it without anything being run.
//
// Compiled once per engine with -DSZ_<NAME>, from engines/ with the engines'
// own include flags (-Iinclude -isystem third_party/mutable -isystem
// third_party/schwung -isystem third_party/msfa -DTEST). Each build includes that engine's source, so
// its Instance type (often in an unnamed namespace) is in scope, and emits
// `fm1sz_<name>` = sizeof, which tools/jieli/analyze.py reads back from the
// symbol table and section data. The same file is compiled for pi32v2, i386
// (-m32) and x86-64, and the three tables are compared.
//
// instance_size() is sizeof(Instance) for every engine but these:
//   - Plate, Ensemble, Diffuse round sizeof(Instance) up to 16 (mi_fx.cc);
//   - Sophie and PSX Verb are AlignUp(sizeof(shim Instance)) +
//     AlignUp(the module's arena), with AlignUp to kAlign (schwung_shim.cc).
// analyze.py applies those rules to the constants below.
//
// Compile-only: the objects are never linked. MIT licence.

#include <stddef.h>
#include <stdint.h>

#define FM1SZ(name, expr) \
  extern "C" __attribute__((used)) const uint32_t fm1sz_##name = (uint32_t)(expr)
#define FM1SZ_TYPE(name, T) \
  FM1SZ(name, sizeof(T));   \
  FM1SZ(name##__align, alignof(T))

#if defined(SZ_MACRO)
#include "../../engines/src/mi_macro.cc"
FM1SZ_TYPE(macro, fm1::macro::Instance);
#elif defined(SZ_SHAPES)
#include "../../engines/src/mi_shapes.cc"
FM1SZ_TYPE(shapes, fm1::shapes::Instance);
#elif defined(SZ_MACRO_HEAVY)
#include "../../engines/src/mi_macro_heavy.cc"
FM1SZ_TYPE(macro_heavy, fm1::macro_heavy::Instance);
#elif defined(SZ_SIXOP)
#include "../../engines/src/mi_sixop.cc"
FM1SZ_TYPE(sixop, fm1::sixop::Instance);
#elif defined(SZ_DX7)
#include "../../engines/src/msfa_dx7.cc"
FM1SZ_TYPE(dx7, fm1::dx7::Instance);
#elif defined(SZ_TEST_SINE)
#include "../../engines/src/test_sine.cc"
FM1SZ_TYPE(test_sine, fm1::test_sine::Instance);
#elif defined(SZ_TEST_GAIN)
#include "../../engines/src/test_gain.cc"
FM1SZ_TYPE(test_gain, fm1::test_gain::Instance);
#elif defined(SZ_MI_FX)
#include "../../engines/src/mi_fx.cc"
FM1SZ_TYPE(plate, fm1::mi_fx::plate::Instance);
FM1SZ_TYPE(ensemble, fm1::mi_fx::ensemble::Instance);
FM1SZ_TYPE(diffuse, fm1::mi_fx::diffuse::Instance);
#elif defined(SZ_ACID_BASS)       /* a GPL module: compiled only with FM1_GPL_MODS=1 */
#include "../../engines/src/acid_bass.cc"
FM1SZ_TYPE(acid_bass, fm1::acid_bass::Instance);
FM1SZ_TYPE(bass303, bass303_t);
#elif defined(SZ_COMET_KIT)       /* a GPL module: compiled only with FM1_GPL_MODS=1 */
#include "../../engines/src/comet_kit.cc"
FM1SZ_TYPE(comet_kit, fm1::comet_kit::Instance);
FM1SZ_TYPE(drum909, drum909_t);
#elif defined(SZ_SCHWUNG)
#include "../../engines/src/schwung_shim.cc"
#include "../../engines/src/sw_sophie.cc"
#include "../../engines/src/sw_psxverb.cc"
FM1SZ_TYPE(schwung_instance, fm1::schwung::Instance);
FM1SZ(schwung_align, fm1::schwung::kAlign);
FM1SZ(sophie_arena, fm1::sw_sophie::kArenaBytes);
FM1SZ(psxverb_arena, fm1::sw_psxverb::kArenaBytes);
#else
#error "define one SZ_<NAME>"
#endif
