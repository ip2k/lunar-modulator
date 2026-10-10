# Repeat: beat-synchronised stutter and slice hold, written here.
OUR_SRC += src/fx_repeat.cc

# The selftest includes the implementation so it can report and assert the
# effective beat division and exercise capture-state transitions directly.
all: $(BUILD)/fm1-repeat-selftest

$(BUILD)/fm1-repeat-selftest: $(BUILD)/our/test/repeat_selftest.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/repeat_selftest.d
