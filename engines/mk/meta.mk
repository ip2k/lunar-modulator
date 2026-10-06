# meta.mk -- the parameter metadata export (include/fm1_meta.h,
# state/fm1_meta.c; notes/2026-10-06-state-files.md §7.7) and the known ids
# and aliases it carries (include/fm1_known.h, state/fm1_known.c, written by
# tools/gen_known.py), linked into fm1-render for --meta. C99, built by
# seq.mk's rule for C sources. The simulator links them in stage A1.
.DEFAULT_GOAL := all

META_SRC := state/fm1_meta.c state/fm1_known.c
META_OBJ := $(patsubst %.c,$(BUILD)/c/%.o,$(META_SRC))

RENDER_EXTRA_OBJ += $(META_OBJ)

-include $(META_OBJ:.o=.d)

# fm1-meta-number-test: the export's float writer on float32 edges, knob
# values and random bits (tests/test_engine_metadata.py). It includes
# state/fm1_meta.c, so it links what that links, less that object.
META_NUMBER_TEST_OBJ := $(BUILD)/c/test/meta_number_test.o

all: $(BUILD)/fm1-meta-number-test

$(BUILD)/fm1-meta-number-test: $(META_NUMBER_TEST_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(META_NUMBER_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o $(BUILD)/c/state/fm1_meta.o,$(RENDER_OBJ)) -lm

-include $(META_NUMBER_TEST_OBJ:.o=.d)
