# mk/fm1-x0x.mk -- the GPL modules built on fm1-x0x (Charles Vestal, GPL-3.0-only;
# third_party/fm1-x0x, UPSTREAM.md):
#   "Acid Bass" (acid-bass, src/acid_bass.cc), a bass after the TB-303, on its
#     303 bass (dsp/bass303.c);
#   "Acid Gen" (acid-gen, midi_fx/acid_gen.c), a MIDI effect that writes acid
#     lines, on its TB-3PO generator (seq/tb3po.c);
#   "Comet Kit" (comet, src/comet_kit.cc), a 16-pad kit after the TR-909, on
#     its 909 kit (dsp/drum909.c), with ER-99's cymbal recordings and the
#     tables its own script made of them (gen/, committed: no build needs
#     Python).
# Built only while the GPL switch is on (FM1_GPL_MODS, engines/Makefile); their
# registry entries and licence rows sit under #if FM1_GPL_MODS
# (src/registry.cc, midi_fx/registry.c). With the switch off this fragment
# adds nothing, and tests/test_gpl_switch.py checks that nothing of it is in
# that build.
#
# The vendored C is built as fm1-x0x builds it: C99, float, no contraction
# into fused multiply-adds unless EXTRA asks (the JieLi check's fast profile
# does), no warnings (vendored code). (fastmath.h makes 2^n by adding
# n << 23 to a float's bits, a left shift of a negative n below 2^0: UBSan's
# report of it is suppressed for that header alone, sanitizers/ubsan.supp.)
# Its headers are included with -I, not -isystem, so every object's
# dependency list names them.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

ifeq ($(FM1_GPL_MODS),1)

X0X_DIR := third_party/fm1-x0x
X0X_CFLAGS := -std=c99 -ffp-contract=off $(OPT) $(EXTRA) -w -I$(X0X_DIR) -I$(X0X_DIR)/gen -MMD -MP
X0X_OBJ := $(BUILD)/gpl/fm1-x0x/dsp/bass303.o $(BUILD)/gpl/fm1-x0x/seq/tb3po.o \
           $(BUILD)/gpl/fm1-x0x/dsp/drum909.o

$(BUILD)/gpl/fm1-x0x/%.o: $(X0X_DIR)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(X0X_CFLAGS) -c $< -o $@

# Acid Bass: our wrapper, C++ with our flags, reading the vendored headers.
OUR_SRC += src/acid_bass.cc
$(BUILD)/our/src/acid_bass.o: COMMON += -I$(X0X_DIR)

# Comet Kit: our wrapper, C++ with our flags, reading the vendored headers
# (drum909.h includes the generated tables' header).
OUR_SRC += src/comet_kit.cc
$(BUILD)/our/src/comet_kit.o: COMMON += -I$(X0X_DIR) -I$(X0X_DIR)/gen

# Acid Gen: our MIDI effect, C99 with the MIDI effects' flags (mk/midi_fx.mk).
ACIDGEN_OBJ := $(BUILD)/midi_fx/acid_gen.o
$(ACIDGEN_OBJ): ARP_CFLAGS += -I$(X0X_DIR)

GPL_OBJ += $(X0X_OBJ) $(ACIDGEN_OBJ)

# fm1-acid-oracle (test/acid_oracle.cc): Acid Bass beside a copy of its
# vendored unit driven directly on the same 16-sample grid, and the unit's
# derived values for parameter settings (tests/test_engine_acid_bass.py).
# A desktop test tool.
ACID_ORACLE_OBJ := $(BUILD)/our/test/acid_oracle.o
$(ACID_ORACLE_OBJ): COMMON += -I$(X0X_DIR) -Isrc

all: $(BUILD)/fm1-acid-oracle

$(BUILD)/fm1-acid-oracle: $(ACID_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(ACID_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

# fm1-comet-oracle (test/comet_oracle.cc): Comet Kit beside a copy of its
# vendored unit driven directly on the same 16-sample grid, the unit's
# values for knob settings, and the subnormal floats in its state
# (tests/test_engine_comet_kit.py). A desktop test tool.
COMET_ORACLE_OBJ := $(BUILD)/our/test/comet_oracle.o
$(COMET_ORACLE_OBJ): COMMON += -I$(X0X_DIR) -I$(X0X_DIR)/gen -Isrc

all: $(BUILD)/fm1-comet-oracle

$(BUILD)/fm1-comet-oracle: $(COMET_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(COMET_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(X0X_OBJ:.o=.d) $(ACIDGEN_OBJ:.o=.d) $(ACID_ORACLE_OBJ:.o=.d) $(COMET_ORACLE_OBJ:.o=.d)

endif
