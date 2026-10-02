# resampler.mk -- fm1-resampler-test, the measurement and contract binary for
# include/fm1_resampler.h (engines/test/resampler_test.cc, notes in
# engines/resampler.md, run by tests/test_engines_resampler.py). The header
# is static inline and needs no object of its own; the engines that use it
# include it.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

RESAMPLER_TEST_OBJ := $(BUILD)/our/test/resampler_test.o

all: $(BUILD)/fm1-resampler-test

$(BUILD)/fm1-resampler-test: $(RESAMPLER_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/resampler_test.d
