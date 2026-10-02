# mk/mod.mk -- modulation: the primitives (engines/mod/mp_*.c, fm1_mp.h) and
# their desktop test tool fm1-mod (engines/mod/README.md,
# tests/test_engines_mod.py); and the runtime of docs/16 (include/fm1_mod.h,
# fm1_mod_host.h; engines/mod/mod_*.c and kinds/), which fm1-render hosts
# (--mod, --log-mod) and fm1-mod-core-test checks
# (tests/test_engines_mod_runtime.py).
#
# C99, no heap, no libm. -ffp-contract=off is docs/14's ladder profile: no
# fused multiply-add, so float results match on every rung (macOS arm64 clang
# contracts by default). The tests check the objects' symbols for
# allocators, stdio and libm.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

MOD_SRC := mod/mp_rng.c mod/mp_lfo.c mod/mp_env.c mod/mp_slew.c mod/mp_sah.c \
           mod/mp_turing.c mod/mp_clkdiv.c mod/mp_tables.c
MOD_CFLAGS := -std=c99 $(OPT) $(EXTRA) -ffp-contract=off -Imod -Iinclude -Wall -Wextra -Wpedantic \
              -Wconversion -Wno-sign-conversion -MMD -MP
MOD_OBJ := $(patsubst %.c,$(BUILD)/mod/%.o,$(MOD_SRC))
MOD_TOOL_OBJ := $(BUILD)/mod/mod/mp_tool.o

# The runtime: core, planner, registry, curves, the bridge glue, the kinds.
MODC_SRC := mod/mod_core.c mod/mod_plan.c mod/mod_registry.c mod/mod_curves.c mod/mod_glue.c \
            mod/kinds/mod_lfo.c mod/kinds/mod_env.c mod/kinds/mod_chance.c
MODC_OBJ := $(patsubst %.c,$(BUILD)/mod/%.o,$(MODC_SRC))
# fm1-render's text format for racks and slots (host code: stdio allowed).
MOD_SCRIPT_OBJ := $(BUILD)/c/host/mod_script.o

$(BUILD)/mod/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(MOD_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-mod $(BUILD)/fm1-mod-core-test

$(BUILD)/fm1-mod: $(MOD_TOOL_OBJ) $(MOD_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^

# The runtime's own checks (test/mod_core_test.c): the planner fuzz, chains,
# feedback, fills and NaN, on the runtime alone. The bridge's side of the
# hook is checked in fm1-seq-host-test (test/seq_host_test.c).
MOD_CORE_TEST_OBJ := $(BUILD)/mod/test/mod_core_test.o
$(BUILD)/fm1-mod-core-test: $(MOD_CORE_TEST_OBJ) $(MODC_OBJ) $(MOD_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^

# fm1-render hosts the runtime; every renderer variant that links
# RENDER_OBJ gets it.
RENDER_EXTRA_OBJ += $(MODC_OBJ) $(MOD_OBJ) $(MOD_SCRIPT_OBJ)

-include $(MOD_OBJ:.o=.d) $(MOD_TOOL_OBJ:.o=.d) $(MODC_OBJ:.o=.d) $(MOD_CORE_TEST_OBJ:.o=.d) \
  $(MOD_SCRIPT_OBJ:.o=.d)
