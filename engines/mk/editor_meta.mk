# mk/editor_meta.mk -- the tables an editor reads beside the registries (stage
# ED0, notes/2026-10-06-web-editor.md §6): knob page names and effect groups
# (include/fm1_engine_meta.h), refusal codes and their words
# (include/fm1_refusal.h), the telemetry block's layout (include/fm1_tele.h).
# In OUR_SRC, so everything that links the registry links it: fm1-render, the
# virtual FM-1 (its panel reads the page names here) and the JieLi object
# list. The modulation planner's per-slot reasons (fm1_mod_slot_refusal) are
# checked by fm1-mod-refusal-test (test/mod_refusal_test.c).
.DEFAULT_GOAL := all

OUR_SRC += src/editor_meta.cc

MOD_REFUSAL_TEST_OBJ := $(BUILD)/mod/test/mod_refusal_test.o
all: $(BUILD)/fm1-mod-refusal-test
# mk/mod.mk is read after this fragment: its lists expand on the second pass.
.SECONDEXPANSION:
$(BUILD)/fm1-mod-refusal-test: $(MOD_REFUSAL_TEST_OBJ) $(BUILD)/our/src/editor_meta.o $$(MODC_OBJ) \
    $$(MOD_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^

-include $(MOD_REFUSAL_TEST_OBJ:.o=.d)
