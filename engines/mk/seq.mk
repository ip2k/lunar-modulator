# mk/seq.mk -- the sequencer core (engines/seq/, include/fm1_seq.h; a C99
# rewrite of Movy's seq-core, engines/seq.md), its test tool fm1-seq and the
# checking build fm1-seq-check, which traps if a cached fire tick is stale.
#
# The core is C99 and never allocates: tests/test_seq_core.py checks its
# objects' symbols for malloc, free and new. Host code (host/seq_*.c) may.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

SEQ_SRC := seq/seq_clip.c seq/seq_engine.c seq/seq_cmd.c seq/seq_persist.c seq/seq_capture.c
# The host bridge (include/fm1_seq_host.h): commands, advance and the split
# renders every host shares; and the effects' side of it (engine API v3's
# extension: tempo, beats and transport events, include/fm1_fx_host.h), and
# the MIDI effects in front of the sounds (include/fm1_mfx_host.h).
# Core rules apply to both: C99, no heap, no stdio.
SEQ_SRC += seq/seq_host.c seq/fx_host.c seq/mfx_host.c
SEQ_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Iinclude -Wall -Wextra -Wpedantic -MMD -MP
SEQ_OBJ := $(patsubst %.c,$(BUILD)/c/%.o,$(SEQ_SRC))
SEQ_CHECK_OBJ := $(patsubst %.c,$(BUILD)/c-check/%.o,$(SEQ_SRC))
SEQ_HOST_OBJ := $(BUILD)/c/host/seq_script.o
SEQ_TOOL_OBJ := $(BUILD)/c/host/seq_tool.o

$(BUILD)/c/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(SEQ_CFLAGS) -c $< -o $@

$(BUILD)/c-check/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(SEQ_CFLAGS) -DSQ_CHECK_INDEX -c $< -o $@

all: $(BUILD)/fm1-seq $(BUILD)/fm1-seq-check $(BUILD)/fm1-seq-host-test

$(BUILD)/fm1-seq: $(SEQ_TOOL_OBJ) $(SEQ_HOST_OBJ) $(SEQ_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^ -lm

$(BUILD)/fm1-seq-check: $(SEQ_TOOL_OBJ) $(SEQ_HOST_OBJ) $(SEQ_CHECK_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^ -lm

# The host bridge's own checks, where fm1-render does not reach it
# (test/seq_host_test.c; tests/test_seq_render.py runs it).
SEQ_BRIDGE_TEST_OBJ := $(BUILD)/c/test/seq_host_test.o
$(BUILD)/fm1-seq-host-test: $(SEQ_BRIDGE_TEST_OBJ) $(SEQ_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^ -lm

# fm1-render plays sequences through the sound engine (--seq, --cmd). The
# objects go into RENDER_EXTRA_OBJ, not onto fm1-render's prerequisites, so
# every renderer variant that links RENDER_OBJ (fm1-render-original-names in
# mk/plaits-heavy.mk) gets them too.
RENDER_EXTRA_OBJ += $(SEQ_OBJ) $(SEQ_HOST_OBJ)

-include $(SEQ_OBJ:.o=.d) $(SEQ_CHECK_OBJ:.o=.d) $(SEQ_HOST_OBJ:.o=.d) $(SEQ_TOOL_OBJ:.o=.d) \
  $(SEQ_BRIDGE_TEST_OBJ:.o=.d)
