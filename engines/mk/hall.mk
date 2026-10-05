# mk/hall.mk -- Hall, the feedback-delay-network reverb written here
# (engines/src/fx_hall.cc), and its selftest.
#
# This fragment adds a target to `all` before the main Makefile's first rule;
# keep `all` the default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_hall.cc

# fm1-hall-selftest: what a render cannot show -- parameters turned while it
# runs (Freeze, Size and Pre-delay swept), host rates it must refuse, decay
# to exact zeros, the decay time it promises (run by
# tests/test_engines_hall.py). Not in OUR_SRC: it has a main().
HALL_SELFTEST_OBJ := $(BUILD)/our/test/hall_selftest.o $(BUILD)/our/src/fx_hall.o

all: $(BUILD)/fm1-hall-selftest

$(BUILD)/fm1-hall-selftest: $(HALL_SELFTEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm
