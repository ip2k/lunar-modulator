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
# Squash without Mu's partial makeup (2026-10-06), the code as it was, under
# the name fm1_engine_squash_ref: the oracle's cases and the makeup's checks
# compare with it.
SQUASH_REF_OBJ := $(BUILD)/squash-ref/fx_squash.o

all: $(BUILD)/fm1-squash-test

$(BUILD)/squash-ref/fx_squash.o: src/fx_squash.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_SQUASH_MU_MAKEUP=0 -Dfm1_engine_squash=fm1_engine_squash_ref -c $< -o $@

$(BUILD)/fm1-squash-test: $(SQUASH_TEST_OBJ) $(BUILD)/our/src/fx_squash.o $(BUILD)/our/src/fx_shaper.o \
                         $(BUILD)/our/src/fx_limit.o $(SQUASH_REF_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(SQUASH_TEST_OBJ:.o=.d) $(SQUASH_REF_OBJ:.o=.d)
