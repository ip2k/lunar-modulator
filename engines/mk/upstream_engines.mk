# mk/upstream_engines.mk -- build integration for the upstream-derived GPL
# modules (third_party/upstream-engines/UPSTREAM.md): Drawbar, Trio and Phase
# Bend. Their upstream names and attribution are documented in that notice.
# One shim (src/upstream_engine_shim.cc, C++, our API) over one C object
# (src/upstream_engine_bridge.c), which includes the selected vendor sources.
# Built only while the GPL switch is on (FM1_GPL_MODS,
# engines/Makefile); the registry entries and licence rows sit under
# #if FM1_GPL_MODS (src/registry.cc). With the switch off this fragment adds
# nothing, and tests/test_gpl_switch.py checks that nothing of it is in that
# build.
#
# The bridge is built as the vendor code expects: C (gnu11: core.h has a
# _Static_assert; the engines use designated initialisers and GNU
# attributes), -fwrapv (its fixed-point code multiplies and shifts signed
# values as its ARM build does; engines/sanitizers/ubsan.supp), no
# warnings (vendored code). Its headers are included with -I, so the
# object's dependency list names them.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

ifeq ($(FM1_GPL_MODS),1)

UPSTREAM_ENGINE_DIR := third_party/upstream-engines
UPSTREAM_ENGINE_CFLAGS := -std=gnu11 -fwrapv $(OPT) $(EXTRA) -w -Iinclude -I$(GPL_GEN) -Isrc \
              -I$(UPSTREAM_ENGINE_DIR)/src -I$(UPSTREAM_ENGINE_DIR)/gen -MMD -MP
UPSTREAM_ENGINE_OBJ := $(BUILD)/gpl/upstream_engines/upstream_engine_bridge.o

$(BUILD)/gpl/upstream_engines/upstream_engine_bridge.o: src/upstream_engine_bridge.c
	@mkdir -p $(dir $@)
	$(CC) $(UPSTREAM_ENGINE_CFLAGS) -c $< -o $@

# The shim: C++ with our flags; it includes only the bridge's header.
OUR_SRC += src/upstream_engine_shim.cc

GPL_OBJ += $(UPSTREAM_ENGINE_OBJ)

# fm1-upstream-engines-oracle (test/upstream_engines_oracle.c): the three engines through our
# API against the upstream voice oracle driving the same engine files
# (tests/test_engine_upstream_engines.py). A desktop test tool, C like the bridge.
UPSTREAM_ENGINE_ORACLE_OBJ := $(BUILD)/gpl/upstream_engines/upstream_engines_oracle.o

$(UPSTREAM_ENGINE_ORACLE_OBJ): test/upstream_engines_oracle.c
	@mkdir -p $(dir $@)
	$(CC) $(UPSTREAM_ENGINE_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-upstream-engines-oracle

$(BUILD)/fm1-upstream-engines-oracle: $(UPSTREAM_ENGINE_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(UPSTREAM_ENGINE_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(UPSTREAM_ENGINE_OBJ:.o=.d) $(UPSTREAM_ENGINE_ORACLE_OBJ:.o=.d)

endif
