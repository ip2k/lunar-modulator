# mk/x0x-crater.mk -- "Crater Kit" (crater, src/crater_kit.cc), a 16-pad kit
# after the TR-808, on fm1-x0x's 808 (Charles Vestal, GPL-3.0-only; ported
# from 8W8 by athousanddetails; third_party/fm1-x0x, UPSTREAM.md).
# Built only while the GPL switch is on (FM1_GPL_MODS, engines/Makefile); its
# registry entry and licence row sit under #if FM1_GPL_MODS (src/registry.cc).
# With the switch off this fragment adds nothing, and tests/test_gpl_switch.py
# checks that nothing of it is in that build.
#
# The vendored C (dsp/drum808.c) is built by mk/fm1-x0x.mk's rule for
# third_party/fm1-x0x, with its flags (X0X_CFLAGS): this fragment sorts after
# that one, so its variables are set here.

.DEFAULT_GOAL := all

ifeq ($(FM1_GPL_MODS),1)

ifndef X0X_DIR
$(error mk/x0x-crater.mk needs mk/fm1-x0x.mk, read before it)
endif

CRATER_OBJ := $(BUILD)/gpl/fm1-x0x/dsp/drum808.o
GPL_OBJ += $(CRATER_OBJ)

# Crater Kit: our wrapper, C++ with our flags, reading the vendored headers.
OUR_SRC += src/crater_kit.cc
$(BUILD)/our/src/crater_kit.o: COMMON += -I$(X0X_DIR)

# fm1-crater-oracle (test/crater_oracle.cc): Crater Kit beside a copy of its
# vendored kit driven directly on the same 16-sample grid
# (tests/test_engine_crater_kit.py). A desktop test tool.
CRATER_ORACLE_OBJ := $(BUILD)/our/test/crater_oracle.o
$(CRATER_ORACLE_OBJ): COMMON += -I$(X0X_DIR) -Isrc

all: $(BUILD)/fm1-crater-oracle

$(BUILD)/fm1-crater-oracle: $(CRATER_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(CRATER_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(CRATER_OBJ:.o=.d) $(CRATER_ORACLE_OBJ:.o=.d)

endif
