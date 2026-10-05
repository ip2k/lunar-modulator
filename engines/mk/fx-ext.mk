# fx-ext.mk -- fm1-fx-ext-test: engine API v3 where fm1-render cannot reach
# it (engines/test/fx_ext_test.cc, run by tests/test_engine_api_v3.py): the
# effect extension's plumbing (include/fm1_fx_host.h, seq/fx_host.c) with
# Test Ext (src/test_ext.cc) and a real sequencer, and the LOG law with the
# sequencer's 7-bit lock grid. Test Ext itself is in OUR_SRC (the Makefile),
# so fm1-render and the virtual FM-1 have it too.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

FX_EXT_TEST_OBJ := $(BUILD)/our/test/fx_ext_test.o
# The sequencer core and its bridges, as mk/seq.mk builds them (that fragment
# is read after this one, so its SEQ_OBJ is not set yet here).
FX_EXT_SEQ_OBJ := $(patsubst %.c,$(BUILD)/c/%.o,$(sort $(wildcard seq/*.c)))

all: $(BUILD)/fm1-fx-ext-test

$(BUILD)/fm1-fx-ext-test: $(FX_EXT_TEST_OBJ) $(BUILD)/our/src/test_ext.o $(BUILD)/our/src/test_gain.o \
    $(FX_EXT_SEQ_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(FX_EXT_TEST_OBJ:.o=.d)
