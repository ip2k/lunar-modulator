# drive.mk -- "Drive", an overdrive and saturation effect written for this
# repository (engines/src/fx_drive.cc; parameters in engines/README.md), and
# fm1-drive-test, which includes the effect's source to reach its curves and
# drives it where fm1-render cannot: parameters and Types that change while
# audio runs, block sizes that change between calls, host rates, aliasing
# against a plain per-sample curve (engines/test/drive_test.cc, run by
# tests/test_engines_drive.py). No third-party code; the simulator's build
# (sim/web/mk/sim.mk) links the effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_drive.cc

DRIVE_TEST_OBJ := $(BUILD)/our/test/drive_test.o

all: $(BUILD)/fm1-drive-test

# The test includes src/fx_drive.cc itself, so it links no fx_drive.o.
$(BUILD)/fm1-drive-test: $(DRIVE_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(DRIVE_TEST_OBJ:.o=.d)
