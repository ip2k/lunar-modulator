# mk/fx-warble.mk -- original compact Wow/Flutter effect and host contract test.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_warble.cc

WARBLE_SELFTEST_OBJ := $(BUILD)/our/test/warble_selftest.o $(BUILD)/our/src/fx_warble.o
all: $(BUILD)/fm1-warble-selftest

$(BUILD)/fm1-warble-selftest: $(WARBLE_SELFTEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/warble_selftest.d
