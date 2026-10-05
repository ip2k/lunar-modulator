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

COMMON := -std=c++11 -fno-exceptions -fno-rtti -DTEST $(OPT) $(EXTRA) \
          -Iinclude -isystem third_party/mutable -MMD -MP
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
  stmlib/dsp/atan.cc \
  stmlib/utils/random.cc

# Engines added in their own fragment (mk/<name>.mk) append to OUR_SRC and
# TP_SRC, so parallel work on different engines does not collide here.
-include $(sort $(wildcard mk/*.mk))

OUR_OBJ := $(patsubst %.cc,$(BUILD)/our/%.o,$(OUR_SRC))
TP_OBJ := $(patsubst %.cc,$(BUILD)/tp/%.o,$(TP_SRC))
# Everything fm1-render links. Fragments add objects built by rules of their
# own (Schwung's C modules) to RENDER_EXTRA_OBJ; a variant of the renderer
# (mk/plaits-heavy.mk) links this list with one object swapped.
RENDER_OBJ = $(OUR_OBJ) $(TP_OBJ) $(RENDER_EXTRA_OBJ)

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
