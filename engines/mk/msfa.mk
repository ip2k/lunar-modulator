# mk/msfa.mk -- "FM6" (engine id dx7): six-operator FM on msfa, Google's
# music-synthesizer-for-android FM core (Apache-2.0, vendored byte-identical
# in third_party/msfa), and the Felucca oracle the tests compare it with
# (engines/msfa.md).
#
# Each vendored msfa .cc is compiled on its own through src/msfa_unit.cc,
# which includes it inside namespace fm1_msfa (src/msfa_prelude.h says why),
# with the vendored-code flags: no warnings, and -fwrapv, since msfa's phase
# accumulators wrap as int32_t, as they did under the compilers it was
# written for. Our files that include msfa's headers see them as system
# headers (no warnings from vendored code), as Mutable's are.
.DEFAULT_GOAL := all

OUR_SRC += src/msfa_dx7.cc src/dx7_voice.cc src/dx7_loop.cc

MSFA_DIR := third_party/msfa
MSFA_UNITS := dx7note env exp2 fm_core fm_op_kernel freqlut lfo patch pitchenv sin
MSFA_OBJ := $(patsubst %,$(BUILD)/tp/msfa/%.o,$(MSFA_UNITS))

$(BUILD)/tp/msfa/%.o: src/msfa_unit.cc src/msfa_prelude.h $(MSFA_DIR)/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -isystem $(MSFA_DIR) \
	  -DFM1_MSFA_UNIT='"$*.cc"' -c $< -o $@

$(BUILD)/our/src/msfa_dx7.o $(BUILD)/our/src/dx7_voice.o $(BUILD)/our/src/dx7_loop.o: COMMON += -isystem $(MSFA_DIR)

RENDER_EXTRA_OBJ += $(MSFA_OBJ)

-include $(MSFA_OBJ:.o=.d)

# fm1-dx7-oracle (test/dx7_oracle.cc): one voice through FM6 and through
# Felucca's fm6_core.c (third_party/felucca-fm6, Apache-2.0; set up in
# test/dx7_felucca.c), and how far apart they are; also msfa's start-up
# tables (tests/test_engines_dx7.py). A desktop test tool: fm6_core.c is in
# no engine. It is C, built with the vendored-code flags.
DX7_ORACLE_OBJ := $(BUILD)/our/test/dx7_oracle.o $(BUILD)/tp/felucca-fm6/dx7_felucca.o

$(BUILD)/our/test/dx7_oracle.o: COMMON += -isystem $(MSFA_DIR)

$(BUILD)/tp/felucca-fm6/dx7_felucca.o: test/dx7_felucca.c third_party/felucca-fm6/fm6_core.c
	@mkdir -p $(dir $@)
	$(CC) -std=c99 $(OPT) $(EXTRA) -w -fwrapv -Ithird_party/felucca-fm6 -MMD -MP -c $< -o $@

all: $(BUILD)/fm1-dx7-oracle

$(BUILD)/fm1-dx7-oracle: $(DX7_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(DX7_ORACLE_OBJ:.o=.d)
