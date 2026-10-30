# resampler.mk -- fm1-resampler-test, the measurement and contract binary for
# include/fm1_resampler.h (engines/test/resampler_test.cc, notes in
# engines/resampler.md, run by tests/test_engines_resampler.py). The header
# is static inline and needs no object of its own; the engines that use it
# include it.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

RESAMPLER_TEST_OBJ := $(BUILD)/our/test/resampler_test.o
# The same tool with the 51/47 fast path compiled out (FM1_RESAMPLER_POLY47=0):
# the two-stage design measured at Plaits' rate too, as every build had it
# before the fast path.
RESAMPLER_GENERIC_OBJ := $(BUILD)/our/test/resampler_test_generic.o

all: $(BUILD)/fm1-resampler-test $(BUILD)/fm1-resampler-test-generic

$(BUILD)/fm1-resampler-test: $(RESAMPLER_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

$(RESAMPLER_GENERIC_OBJ): test/resampler_test.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_RESAMPLER_POLY47=0 -c $< -o $@

$(BUILD)/fm1-resampler-test-generic: $(RESAMPLER_GENERIC_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/resampler_test.d $(BUILD)/our/test/resampler_test_generic.d
