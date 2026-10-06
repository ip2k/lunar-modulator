# ref-braids-fx.mk -- fm1-ref-braids-fx, the upstream reference for Shapes,
# Plate, Ensemble and Diffuse (engines/test/ref_braids_fx.cc, notes in
# engines/reference-braids-fx.md, run by
# tests/test_engines_reference_braids_fx.py).
#
# The tool links the vendored classes only, not the engines: it is the
# upstream side of the comparison. Every third-party source it needs is
# already in TP_SRC (the main Makefile builds Braids, stmlib and
# plaits/resources.cc); the list is spelled out here because TP_OBJ is not
# defined yet when fragments are read.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

REF_BFX_TP := \
  braids/macro_oscillator.cc \
  braids/analog_oscillator.cc \
  braids/digital_oscillator.cc \
  braids/resources.cc \
  plaits/resources.cc \
  stmlib/utils/random.cc

TP_SRC += $(filter-out $(TP_SRC),$(REF_BFX_TP))

REF_BFX_OBJ := $(BUILD)/our/test/ref_braids_fx.o \
               $(patsubst %.cc,$(BUILD)/tp/%.o,$(REF_BFX_TP))

all: $(BUILD)/fm1-ref-braids-fx

$(BUILD)/fm1-ref-braids-fx: $(REF_BFX_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/ref_braids_fx.d
