# param_get.mk -- fm1-param-get-test (engines/test/param_get_test.cc): engine
# API v4's read-back on every registered engine, effect and MIDI effect: an
# engine with get_param gives back every value it was set, every focus
# entry's included, and fm1_engine_copy_params restores an instance bit for
# bit; one without gives the same samples when a host replays only what it
# kept, in table order (tests/test_engine_api_v4.py). Our own code only.
.DEFAULT_GOAL := all

PARAM_GET_TEST_OBJ := $(BUILD)/our/test/param_get_test.o

all: $(BUILD)/fm1-param-get-test

# fm1-render as a prerequisite builds every object it links; the link line is
# expanded when it runs, after the main Makefile has set RENDER_OBJ.
$(BUILD)/fm1-param-get-test: $(PARAM_GET_TEST_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(PARAM_GET_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(PARAM_GET_TEST_OBJ:.o=.d)
