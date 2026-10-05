# sat.mk -- "Master Sat", band-limited saturation for the master bus written
# for this repository (engines/src/fx_sat.cc; parameters in engines/README.md),
# and fm1-sat-test, which drives it where fm1-render cannot: parameters that
# change while audio runs, block sizes that change between calls, host rates,
# float-exact bypass, and tones of any frequency and level
# (engines/test/sat_test.cc, run by tests/test_engines_sat.py). The curve
# coefficients follow Airwindows (MIT, notice in the source); no third-party
# code is compiled. The simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_sat.cc

SAT_TEST_OBJ := $(BUILD)/our/test/sat_test.o

all: $(BUILD)/fm1-sat-test

$(BUILD)/fm1-sat-test: $(SAT_TEST_OBJ) $(BUILD)/our/src/fx_sat.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(SAT_TEST_OBJ:.o=.d)
