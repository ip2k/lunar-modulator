# tilt.mk -- "Tilt", a tilt equaliser written for this repository
# (engines/src/fx_tilt.cc; parameters in engines/README.md), and
# fm1-tilt-test, which drives it where fm1-render cannot: its frequency
# response in float, the exact bypass bit for bit, parameters that change
# while audio runs, block sizes that change between calls, host rates
# (engines/test/tilt_test.cc, run by tests/test_engines_tilt.py). No
# third-party code; the simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_tilt.cc

TILT_TEST_OBJ := $(BUILD)/our/test/tilt_test.o

all: $(BUILD)/fm1-tilt-test

$(BUILD)/fm1-tilt-test: $(TILT_TEST_OBJ) $(BUILD)/our/src/fx_tilt.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(TILT_TEST_OBJ:.o=.d)
