# comp.mk -- "Comp", a feed-forward compressor written for this repository
# (engines/src/fx_comp.cc; parameters in engines/README.md), and
# fm1-comp-test, which drives it where fm1-render cannot: the static curve
# and time constants on exact test signals, parameters that change while
# audio runs, the gain-reduction accessor (include/fm1_comp.h), host rates,
# the accuracy of its log2/exp2 and its cost (engines/test/comp_test.cc, run
# by tests/test_engines_comp.py). No third-party code; the simulator's build
# (sim/web/mk/sim.mk) links the effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_comp.cc

COMP_TEST_OBJ := $(BUILD)/our/test/comp_test.o

all: $(BUILD)/fm1-comp-test

$(BUILD)/fm1-comp-test: $(COMP_TEST_OBJ) $(BUILD)/our/src/fx_comp.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(COMP_TEST_OBJ:.o=.d)
