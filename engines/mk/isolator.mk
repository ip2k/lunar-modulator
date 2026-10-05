# isolator.mk -- "Isolator", a three-band kill EQ with Linkwitz-Riley
# crossovers written for this repository (engines/src/fx_isolator.cc;
# parameters in engines/README.md), and fm1-isolator-test, which drives it
# where fm1-render cannot: parameters that change while audio runs, block
# sizes that change between calls, host rates, and its frequency response in
# float (engines/test/isolator_test.cc, run by tests/test_engines_isolator.py).
# No third-party code; the simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_isolator.cc

ISOLATOR_TEST_OBJ := $(BUILD)/our/test/isolator_test.o

all: $(BUILD)/fm1-isolator-test

$(BUILD)/fm1-isolator-test: $(ISOLATOR_TEST_OBJ) $(BUILD)/our/src/fx_isolator.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(ISOLATOR_TEST_OBJ:.o=.d)
