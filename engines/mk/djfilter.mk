# djfilter.mk -- "DJ Filter", a one-knob low-pass / high-pass written for
# this repository (engines/src/fx_djfilter.cc; parameters in
# engines/README.md), and fm1-djfilter-test, which drives it where
# fm1-render cannot: parameters that change while audio runs, block sizes
# that change between calls, exact bypass, frequency response, host rates
# (engines/test/djfilter_test.cc, run by tests/test_engines_djfilter.py). No
# third-party code; the simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_djfilter.cc

DJFILTER_TEST_OBJ := $(BUILD)/our/test/djfilter_test.o

all: $(BUILD)/fm1-djfilter-test

$(BUILD)/fm1-djfilter-test: $(DJFILTER_TEST_OBJ) $(BUILD)/our/src/fx_djfilter.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(DJFILTER_TEST_OBJ:.o=.d)
