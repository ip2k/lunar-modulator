# filter.mk -- "Filter", a multimode filter audio effect written for this
# repository (engines/src/fx_filter.cc; parameters in engines/README.md),
# and fm1-filter-test, which drives it where fm1-render cannot: parameters
# that change while audio runs, block sizes that change between calls, host
# rates, frequency responses and self-oscillation
# (engines/test/filter_test.cc, run by tests/test_engines_filter.py). No
# third-party code; the simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_filter.cc

FILTER_TEST_OBJ := $(BUILD)/our/test/filter_test.o

all: $(BUILD)/fm1-filter-test

$(BUILD)/fm1-filter-test: $(FILTER_TEST_OBJ) $(BUILD)/our/src/fx_filter.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(FILTER_TEST_OBJ:.o=.d)
