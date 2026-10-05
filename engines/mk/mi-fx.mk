# mi-fx: Plate, Ensemble and Diffuse, audio effects from Mutable Instruments
# code (engines/src/mi_fx.cc, notes in engines/mi-fx.md). The vendored effects
# are header-only; Ensemble's sine table comes from plaits/resources.cc, which
# the main Makefile already builds.
#
# fm1-plate-test drives Plate's Freeze where fm1-render cannot: turned while
# audio runs, at changing block sizes and fills (engines/test/plate_test.cc,
# run by tests/test_engines_plate_freeze.py). Not in OUR_SRC: it has a main().
# This fragment adds a target to `all` before the main Makefile's first rule;
# keep `all` the default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/mi_fx.cc

PLATE_TEST_OBJ := $(BUILD)/our/test/plate_test.o

all: $(BUILD)/fm1-plate-test

# Plaits' resources: rings::Reverb needs none, but mi_fx.o also holds
# Ensemble, which reads Plaits' sine table.
$(BUILD)/fm1-plate-test: $(PLATE_TEST_OBJ) $(BUILD)/our/src/mi_fx.o $(BUILD)/tp/plaits/resources.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(PLATE_TEST_OBJ:.o=.d)
