# gate.mk -- "Gate", a triggerable noise gate with a Duck mode written for
# this repository (engines/src/fx_gate.cc; parameters in engines/README.md),
# and fm1-gate-test, which drives it where fm1-render cannot: open, hold and
# close timing read frame by frame from its state (include/fm1_gate.h),
# Range, Return's hysteresis, Duck, Lockout, the look-ahead's latency, the
# key filters' responses through Listen, a key other than the input
# (fm1_gate_render_key), chattering on noisy keys, bad keys, parameters that
# change while audio runs, host rates, its tan against libm, the output's
# bits and its cost (engines/test/gate_test.cc, run by
# tests/test_engines_gate.py). No third-party code; the simulator's build
# (sim/web/mk/sim.mk) links the effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_gate.cc

# The test links the effect built once more with FM1_GATE_PROBE, which only
# adds an entry point to its tan polynomial (checked against libm); the
# audio path is the same code.
GATE_TEST_OBJ := $(BUILD)/our/test/gate_test.o $(BUILD)/our/test/fx_gate_probe.o

all: $(BUILD)/fm1-gate-test

$(BUILD)/our/test/fx_gate_probe.o: src/fx_gate.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_GATE_PROBE -c $< -o $@

$(BUILD)/fm1-gate-test: $(GATE_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(GATE_TEST_OBJ:.o=.d)
