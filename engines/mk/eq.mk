# eq.mk -- "EQ", a three-band parametric equaliser written for this
# repository (engines/src/fx_eq.cc; parameters in engines/README.md), and
# fm1-eq-test, which drives it where fm1-render cannot: the frequency
# response measured in float precision, parameters that change while audio
# runs, the exact pass-through at 0 dB, host rates, the accuracy of its
# libm-free 2^x, log2 and tan, and its cost (engines/test/eq_test.cc, run by
# tests/test_engines_eq.py). No third-party code; the simulator's build
# (sim/web/mk/sim.mk) links the effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_eq.cc

EQ_TEST_OBJ := $(BUILD)/our/test/eq_test.o

all: $(BUILD)/fm1-eq-test

$(BUILD)/fm1-eq-test: $(EQ_TEST_OBJ) $(BUILD)/our/src/fx_eq.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(EQ_TEST_OBJ:.o=.d)
