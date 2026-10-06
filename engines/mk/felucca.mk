# mk/felucca.mk -- the GPL modules built on Felucca's engines (Leo
# Kuroshita / Hügelton Instruments, GPL-3.0-only; third_party/felucca,
# UPSTREAM.md):
#   "Drawbar" (drawbar), a tonewheel-style organ, on WHEEL (eng_wheel.c);
#   "Trio" (trio), three chip-style oscillators and a filter, on TRIO;
#   "Phase Bend" (phase-bend), phase distortion, on PHASE.
# One shim (src/felucca_shim.cc, C++, our API) over one C object
# (src/felucca_bridge.c), which includes Felucca's files as its felucca.c
# does. Built only while the GPL switch is on (FM1_GPL_MODS,
# engines/Makefile); the registry entries and licence rows sit under
# #if FM1_GPL_MODS (src/registry.cc). With the switch off this fragment adds
# nothing, and tests/test_gpl_switch.py checks that nothing of it is in that
# build.
#
# The bridge is built as Felucca builds its own code: C (gnu11: core.h has a
# _Static_assert; the engines use designated initialisers and GNU
# attributes), -fwrapv (its fixed-point code multiplies and shifts signed
# values as its ARM build does; engines/sanitizers/ubsan.supp), no
# warnings (vendored code). Its headers are included with -I, so the
# object's dependency list names them.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

ifeq ($(FM1_GPL_MODS),1)

FEL_DIR := third_party/felucca
FEL_CFLAGS := -std=gnu11 -fwrapv $(OPT) $(EXTRA) -w -Iinclude -I$(GPL_GEN) -Isrc \
              -I$(FEL_DIR)/src -I$(FEL_DIR)/gen -MMD -MP
FEL_OBJ := $(BUILD)/gpl/felucca/felucca_bridge.o

$(BUILD)/gpl/felucca/felucca_bridge.o: src/felucca_bridge.c
	@mkdir -p $(dir $@)
	$(CC) $(FEL_CFLAGS) -c $< -o $@

# The shim: C++ with our flags; it includes only the bridge's header.
OUR_SRC += src/felucca_shim.cc

GPL_OBJ += $(FEL_OBJ)

# fm1-felucca-oracle (test/felucca_oracle.c): the three engines through our
# API against Felucca's own voice.c driving the same engine files
# (tests/test_engine_felucca.py). A desktop test tool, C like the bridge.
FEL_ORACLE_OBJ := $(BUILD)/gpl/felucca/felucca_oracle.o

$(FEL_ORACLE_OBJ): test/felucca_oracle.c
	@mkdir -p $(dir $@)
	$(CC) $(FEL_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-felucca-oracle

$(BUILD)/fm1-felucca-oracle: $(FEL_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(FEL_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(FEL_OBJ:.o=.d) $(FEL_ORACLE_OBJ:.o=.d)

endif
