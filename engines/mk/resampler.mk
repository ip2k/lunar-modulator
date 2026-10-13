# resampler.mk -- fm1-resampler-test, the measurement and contract binary for
# include/fm1_resampler.h (engines/test/resampler_test.cc, notes in
# engines/resampler.md, run by tests/test_engines_resampler.py). The header
# is static inline; constrained builds may share its coefficient storage.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

RESAMPLER_TEST_OBJ := $(BUILD)/our/test/resampler_test.o
FM1_SHARED_RESAMPLER ?= 0
ifneq ($(filter $(FM1_SHARED_RESAMPLER),0 1),$(FM1_SHARED_RESAMPLER))
$(error FM1_SHARED_RESAMPLER must be 0 or 1)
endif
override EXTRA += -DFM1_RESAMPLER_SHARED_TABLES=$(FM1_SHARED_RESAMPLER)
# COMMON was expanded before fragments were loaded; keep C++ engine flags
# consistent with later C/application rules that expand EXTRA themselves.
COMMON += -DFM1_RESAMPLER_SHARED_TABLES=$(FM1_SHARED_RESAMPLER)
ifeq ($(FM1_SHARED_RESAMPLER),1)
OUR_SRC += src/resampler_tables.cc
RESAMPLER_TEST_OBJ += $(BUILD)/our/src/resampler_tables.o
endif

all: $(BUILD)/fm1-resampler-test

$(BUILD)/fm1-resampler-test: $(RESAMPLER_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/resampler_test.d
