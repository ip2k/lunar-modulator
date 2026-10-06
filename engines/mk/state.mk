# mk/state.mk -- saved state (stage E3; engines/state/README.md,
# notes/2026-10-06-state-files.md): the record model, the streaming JSON
# reader and the canonical writer, the binary container with its deflate,
# and the desktop tool fm1-state. fm1-render links it for --load and --save.
#
# The library is C99 with no heap, no stdio and no libm, and
# -ffp-contract=off (docs/14's ladder profile), so native, WebAssembly and
# the device read every number to the same bits; tests/test_state_codec.py
# checks its objects' symbols. The tool (host/state_tool.c) is host code.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

STATE_SRC := state/fm1_json.c state/fm1_num.c state/fm1_deflate.c state/state_names.c \
             state/state_json_read.c state/state_json_write.c state/state_bin.c \
             state/state_movy1.c state/state_print.c
STATE_CFLAGS := -std=c99 $(OPT) $(EXTRA) -ffp-contract=off -Iinclude -Istate -Wall -Wextra -Wpedantic \
                -Wconversion -Wno-sign-conversion -MMD -MP
STATE_OBJ := $(patsubst %.c,$(BUILD)/state/%.o,$(STATE_SRC))
# The registries' names (fm1_state_names_default): kept apart so a fuzz
# target links the codecs without every engine.
STATE_REG_OBJ := $(BUILD)/state/state/state_registry.o
STATE_TOOL_OBJ := $(BUILD)/state/host/state_tool.o

$(BUILD)/state/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(STATE_CFLAGS) -c $< -o $@

$(STATE_TOOL_OBJ): STATE_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Iinclude -Istate -Wall -Wextra -MMD -MP

all: $(BUILD)/fm1-state

# fm1-state links the registries, so every engine object fm1-render links
# but its main(); those lists are complete only once every fragment and the
# main Makefile are read, hence the second expansion.
.SECONDEXPANSION:
$(BUILD)/fm1-state: $(STATE_TOOL_OBJ) \
    $$(filter-out $(BUILD)/our/host/render.o $(BUILD)/our/host/render_state.o,$$(RENDER_OBJ))
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# The fuzz target as a seeded mutation loop (state/fuzz/state_fuzz.c); with
# clang's libFuzzer it is built by hand with -DFM1_LIBFUZZER (README).
STATE_FUZZ_OBJ := $(BUILD)/state/state/fuzz/state_fuzz.o
$(STATE_FUZZ_OBJ): STATE_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Iinclude -Istate -Wall -Wextra -MMD -MP
all: $(BUILD)/fm1-state-fuzz
$(BUILD)/fm1-state-fuzz: $(STATE_FUZZ_OBJ) \
    $$(filter-out $(BUILD)/our/host/render.o $(BUILD)/our/host/render_state.o,$$(RENDER_OBJ))
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# fm1-render's --load and --save (host/render_state.cc), with the library;
# not in OUR_SRC, so the virtual FM-1's module does not link them.
RENDER_EXTRA_OBJ += $(STATE_OBJ) $(STATE_REG_OBJ)

-include $(STATE_OBJ:.o=.d) $(STATE_REG_OBJ:.o=.d) $(STATE_TOOL_OBJ:.o=.d) $(STATE_FUZZ_OBJ:.o=.d)
