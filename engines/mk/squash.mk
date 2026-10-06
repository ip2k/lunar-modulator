# squash.mk -- "Squash" (engines/src/fx_squash.cc: Snap, Mu and Split, after
# Airwindows Pop3, Pressure4 and ButterComp2, MIT; parameters in
# engines/README.md), "Transient" (engines/src/fx_shaper.cc, a transient
# shaper written for this repository), and fm1-squash-test, which drives both
# where fm1-render cannot: each Type against its recurrence, gains, timing,
# Type crossfades, parameters that change while audio runs, block sizes,
# memory fills, hostile input, host rates and the cost
# (engines/test/squash_test.cc, run by tests/test_engines_squash.py). No
# third-party file is compiled: the ports carry the Airwindows notice
# themselves. The simulator's build (sim/web/mk/sim.mk) links both effects
# through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_squash.cc src/fx_shaper.cc

SQUASH_TEST_OBJ := $(BUILD)/our/test/squash_test.o

all: $(BUILD)/fm1-squash-test

$(BUILD)/fm1-squash-test: $(SQUASH_TEST_OBJ) $(BUILD)/our/src/fx_squash.o $(BUILD)/our/src/fx_shaper.o \
                         $(BUILD)/our/src/fx_limit.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(SQUASH_TEST_OBJ:.o=.d)
