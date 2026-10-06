# idle.mk -- fm1-idle-test, which checks the idle paths of EQ, Isolator and
# Master Sat (include/fm1_fx_idle.h) against the same three effects built
# without them: -DFM1_FX_IDLE=0, the code as it was, linked under the names
# fm1_engine_<id>_ref (engines/test/idle_test.cc, run by
# tests/test_engines_idle.py). The effects themselves are built by their own
# fragments (eq.mk, isolator.mk, sat.mk).

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

IDLE_TEST_OBJ := $(BUILD)/our/test/idle_test.o
IDLE_REF_OBJ := $(BUILD)/idle-ref/fx_eq.o $(BUILD)/idle-ref/fx_isolator.o $(BUILD)/idle-ref/fx_sat.o

all: $(BUILD)/fm1-idle-test

$(BUILD)/idle-ref/fx_%.o: src/fx_%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_FX_IDLE=0 -Dfm1_engine_$*=fm1_engine_$*_ref -c $< -o $@

$(BUILD)/fm1-idle-test: $(IDLE_TEST_OBJ) $(BUILD)/our/src/fx_eq.o $(BUILD)/our/src/fx_isolator.o \
                        $(BUILD)/our/src/fx_sat.o $(IDLE_REF_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(IDLE_TEST_OBJ:.o=.d) $(IDLE_REF_OBJ:.o=.d)
