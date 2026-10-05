# smooth.mk -- fm1-smooth-test (engines/test/smooth_test.cc): every registered
# engine and effect driven through its fm1_engine_t with parameter changes at
# any frame and render calls cut at 64, 1, 7 or random frames, to show that
# the SMOOTH ramp (include/fm1_smooth.h, docs/15 stage S7b) is keyed to
# samples (tests/test_engine_smooth.py). Our own code only.
.DEFAULT_GOAL := all

SMOOTH_TEST_OBJ := $(BUILD)/our/test/smooth_test.o

all: $(BUILD)/fm1-smooth-test

# fm1-render as a prerequisite builds every object it links; the link line is
# expanded when it runs, after the main Makefile has set RENDER_OBJ.
$(BUILD)/fm1-smooth-test: $(SMOOTH_TEST_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(SMOOTH_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(SMOOTH_TEST_OBJ:.o=.d)
