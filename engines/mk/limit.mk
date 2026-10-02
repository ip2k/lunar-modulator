# limit.mk -- "Limiter", a look-ahead brickwall limiter written for this
# repository (engines/src/fx_limit.cc; parameters in engines/README.md), and
# fm1-limit-test, which drives it where fm1-render cannot: float output
# against the ceiling on hostile input, latency, release time, parameters
# that change while audio runs, block sizes that change between calls, host
# rates and instance sizes (engines/test/limit_test.cc, run by
# tests/test_engines_limit.py). No third-party code; the simulator's build
# (sim/web/mk/sim.mk) links the effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_limit.cc

# The test links the effect built once more with FM1_LIMIT_PROBE, which only
# records the largest overshoot the final clamp meets (the envelope's own
# accuracy); the audio path is the same code.
LIMIT_TEST_OBJ := $(BUILD)/our/test/limit_test.o $(BUILD)/our/test/fx_limit_probe.o

all: $(BUILD)/fm1-limit-test

$(BUILD)/our/test/fx_limit_probe.o: src/fx_limit.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_LIMIT_PROBE -c $< -o $@

$(BUILD)/fm1-limit-test: $(LIMIT_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(LIMIT_TEST_OBJ:.o=.d)
