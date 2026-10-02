# fold.mk -- "Fold", a wavefolder audio effect written for this repository
# (engines/src/fx_fold.cc; parameters in engines/README.md), and
# fm1-fold-test, which drives it where fm1-render cannot: parameters that
# change while audio runs, block sizes that change between calls, host rates
# (engines/test/fold_test.cc, run by tests/test_engines_fold.py). No
# third-party code; the simulator's build (sim/web/mk/sim.mk) links the
# effect through OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_fold.cc

FOLD_TEST_OBJ := $(BUILD)/our/test/fold_test.o

all: $(BUILD)/fm1-fold-test

$(BUILD)/fm1-fold-test: $(FOLD_TEST_OBJ) $(BUILD)/our/src/fx_fold.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(FOLD_TEST_OBJ:.o=.d)
