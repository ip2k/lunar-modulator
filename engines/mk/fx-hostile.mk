# fx-hostile.mk -- fm1-fx-hostile-test (engines/test/fx_hostile_test.cc, run
# by tests/test_engines_fx_hostile.py): the same hostile host-contract
# checks on every effect of the master-bus pack, DJ Filter, Tilt, EQ,
# Isolator and Master Sat, through their engine structs only. Each effect's
# own fragment adds its source to OUR_SRC; this links their objects.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

FX_HOSTILE_TEST_OBJ := $(BUILD)/our/test/fx_hostile_test.o
FX_HOSTILE_FX_OBJ := $(patsubst %,$(BUILD)/our/src/fx_%.o,djfilter tilt eq isolator sat)

all: $(BUILD)/fm1-fx-hostile-test

$(BUILD)/fm1-fx-hostile-test: $(FX_HOSTILE_TEST_OBJ) $(FX_HOSTILE_FX_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(FX_HOSTILE_TEST_OBJ:.o=.d)
