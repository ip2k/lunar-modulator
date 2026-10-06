# engines/Makefile -- desktop build of the engine API, the engines and the
# renderer (docs/11 §8, stage A).
#
#   make -C engines            # build/fm1-render
#   make -C engines clean
#
# Flags follow the FM-1 toolchain profile (JieLi Clang 4.0.1): C++11, no
# exceptions, no RTTI. -DTEST selects stmlib's C fallbacks for its ARM inline
# assembly, as VCV Rack's build of the same code does.

CXX ?= c++
OPT ?= -O2
EXTRA ?=
BUILD := build

# The GPL switch (CLAUDE.md, "The GPL switch"; docs/12 §6). GPL modules, each
# vendored in its own third_party/<name>/ with its licence and UPSTREAM.md,
# are built in with FM1_GPL_MODS=1, the default in every build while we test,
# and left out with FM1_GPL_MODS=0: the MIT/BSD build, the only one a firmware
# image that links JieLi's libraries may be shared as. One switch for
# everything that builds through this Makefile: fm1-render, the virtual
# FM-1's native and WebAssembly builds (sim/web/mk/sim.mk) and the JieLi
# compile check (tools/jieli/objects.mk).
#
# Its value lives in one generated header, $(BUILD)/gen/fm1_gpl_mods.h, which
# is rewritten only when the value changes: the files that read it (the two
# registries and their licence table) include it, so -MMD rebuilds exactly
# them, and the programs that link them, when the switch is turned. A turn
# waits a second before it rewrites the header, so the header is newer than
# every object and program built before, also for a make that compares whole
# seconds (GNU make 3.81, macOS's). A
# fragment (mk/<name>.mk) adds a GPL module's sources only under
# `ifeq ($(FM1_GPL_MODS),1)`, its C objects to GPL_OBJ (built under
# $(BUILD)/gpl/<name>/, which the JieLi report counts as a group of their
# own), which every program and object list below and in sim.mk and
# objects.mk links or compiles, and its registry entries and licence row
# under `#if FM1_GPL_MODS`.
# tests/test_gpl_switch.py builds the switch off and checks that nothing GPL
# is left in it.
FM1_GPL_MODS ?= 1
ifeq ($(filter 0 1,$(FM1_GPL_MODS)),)
$(error FM1_GPL_MODS is 0 or 1, not "$(FM1_GPL_MODS)")
endif
GPL_GEN := $(BUILD)/gen
GPL_LINE := \#define FM1_GPL_MODS $(FM1_GPL_MODS)  /* engines/Makefile: the GPL switch */
$(shell mkdir -p '$(GPL_GEN)' && h='$(GPL_GEN)/fm1_gpl_mods.h' && \
  { [ "$$(cat "$$h" 2>/dev/null)" = '$(GPL_LINE)' ] || \
    { if [ -f "$$h" ]; then sleep 1; fi; printf '%s\n' '$(GPL_LINE)' > "$$h"; }; })
GPL_OBJ :=

COMMON := -std=c++11 -fno-exceptions -fno-rtti -DTEST $(OPT) $(EXTRA) \
          -Iinclude -I$(GPL_GEN) -isystem third_party/mutable -MMD -MP
OUR_WARN := -Wall -Wextra -Wno-unused-parameter
TP_WARN := -w
# Mutable's fixed-point code (Braids, stmlib) relies on signed arithmetic that
# wraps, as it did under ARM GCC on the modules. -fwrapv makes that defined
# for the compiler, so an optimiser cannot exploit it; keep it in any target
# build of this code (engines/sanitizers/ubsan.supp).
TP_DIALECT := -fwrapv

OUR_SRC := src/registry.cc src/mi_macro.cc src/mi_shapes.cc src/test_sine.cc src/test_gain.cc \
           src/test_ext.cc \
           host/render.cc

TP_SRC := \
  plaits/resources.cc \
  plaits/dsp/engine/virtual_analog_engine.cc \
  plaits/dsp/engine/waveshaping_engine.cc \
  plaits/dsp/engine/fm_engine.cc \
  plaits/dsp/engine/wavetable_engine.cc \
  plaits/dsp/engine2/virtual_analog_vcf_engine.cc \
  plaits/dsp/engine2/phase_distortion_engine.cc \
  plaits/dsp/engine2/wave_terrain_engine.cc \
  plaits/dsp/engine2/chiptune_engine.cc \
  plaits/dsp/chords/chord_bank.cc \
  braids/macro_oscillator.cc \
  braids/analog_oscillator.cc \
  braids/digital_oscillator.cc \
  braids/resources.cc \
  stmlib/dsp/units.cc \
  stmlib/utils/random.cc

# Engines added in their own fragment (mk/<name>.mk) append to OUR_SRC and
# TP_SRC, so parallel work on different engines does not collide here.
-include $(sort $(wildcard mk/*.mk))

OUR_OBJ := $(patsubst %.cc,$(BUILD)/our/%.o,$(OUR_SRC))
TP_OBJ := $(patsubst %.cc,$(BUILD)/tp/%.o,$(TP_SRC))
# Everything fm1-render links. Fragments add objects built by rules of their
# own (Schwung's C modules) to RENDER_EXTRA_OBJ, and a GPL module's C objects
# to GPL_OBJ; a variant of the renderer (mk/plaits-heavy.mk) links this list
# with one object swapped.
RENDER_OBJ = $(OUR_OBJ) $(TP_OBJ) $(RENDER_EXTRA_OBJ) $(GPL_OBJ)

.PHONY: all clean
all: $(BUILD)/fm1-render

$(BUILD)/fm1-render: $(RENDER_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

$(BUILD)/our/%.o: %.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -c $< -o $@

$(BUILD)/tp/%.o: third_party/mutable/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -c $< -o $@

clean:
	rm -rf $(BUILD)

# Header dependencies written by the compiler (-MMD), so editing any header,
# ours or vendored, rebuilds what includes it.
-include $(OUR_OBJ:.o=.d) $(TP_OBJ:.o=.d)
