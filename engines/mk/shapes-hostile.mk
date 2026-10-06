# shapes-hostile.mk -- fm1-shapes-hostile (engines/test/shapes_hostile.cc, run
# by tests/test_engines_shapes_hostile.py): a reviewer's hostile checks of
# Shapes at Braids' edges: random scripts within the engine API on every
# shape, at any block pattern and memory fill (and, under CI's sanitizer
# build, with no report), and the clamps holding bit for bit under turning
# knobs, bends and per-note offsets. It links Shapes' ordinary objects. Not in
# OUR_SRC: it has a main().

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

SHAPES_HOSTILE_TP := \
  braids/macro_oscillator.cc \
  braids/analog_oscillator.cc \
  braids/digital_oscillator.cc \
  braids/resources.cc \
  stmlib/dsp/units.cc \
  stmlib/utils/random.cc

TP_SRC += $(filter-out $(TP_SRC),$(SHAPES_HOSTILE_TP))

SHAPES_HOSTILE_OBJ := $(BUILD)/our/test/shapes_hostile.o $(BUILD)/our/src/mi_shapes.o \
                      $(patsubst %.cc,$(BUILD)/tp/%.o,$(SHAPES_HOSTILE_TP))

all: $(BUILD)/fm1-shapes-hostile

$(BUILD)/fm1-shapes-hostile: $(SHAPES_HOSTILE_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/shapes_hostile.d
