# mk/mod.mk -- the modulation primitives (engines/mod/, fm1_mp.h) and their
# desktop test tool fm1-mod (engines/mod/README.md, tests/test_engines_mod.py).
#
# C99, no heap, no libm. -ffp-contract=off is docs/14's ladder profile: no
# fused multiply-add, so float results match on every rung (macOS arm64 clang
# contracts by default). tests/test_engines_mod.py checks the objects' symbols
# for allocators, stdio and libm.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

MOD_SRC := mod/mp_rng.c mod/mp_lfo.c mod/mp_env.c mod/mp_slew.c mod/mp_sah.c \
           mod/mp_turing.c mod/mp_clkdiv.c mod/mp_tables.c
MOD_CFLAGS := -std=c99 $(OPT) $(EXTRA) -ffp-contract=off -Imod -Wall -Wextra -Wpedantic \
              -Wconversion -Wno-sign-conversion -MMD -MP
MOD_OBJ := $(patsubst %.c,$(BUILD)/mod/%.o,$(MOD_SRC))
MOD_TOOL_OBJ := $(BUILD)/mod/mod/mp_tool.o

$(BUILD)/mod/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(MOD_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-mod

$(BUILD)/fm1-mod: $(MOD_TOOL_OBJ) $(MOD_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^

-include $(MOD_OBJ:.o=.d) $(MOD_TOOL_OBJ:.o=.d)
