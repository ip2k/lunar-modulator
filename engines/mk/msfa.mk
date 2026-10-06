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

OUR_SRC += src/msfa_dx7.cc src/dx7_voice.cc src/dx7_loop.cc src/msfa_tables.cc src/msfa_rom.cc

# msfa's sin.cc and exp2.cc only define and fill its sine and exp2 tables (and
# tanhtab, which nothing reads): the engine reads const copies instead
# (src/msfa_rom.cc, made by tools/msfa_tables.py; src/msfa_prelude.h), so
# they are compiled only into the oracle, to compare (MSFA_REF_OBJ below).
MSFA_DIR := third_party/msfa
MSFA_UNITS := dx7note env fm_core fm_op_kernel freqlut lfo patch pitchenv
MSFA_OBJ := $(patsubst %,$(BUILD)/tp/msfa/%.o,$(MSFA_UNITS))

$(BUILD)/tp/msfa/%.o: src/msfa_unit.cc src/msfa_prelude.h $(MSFA_DIR)/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -isystem $(MSFA_DIR) \
	  -DFM1_MSFA_UNIT='"$*.cc"' -c $< -o $@

MSFA_OUR_OBJ := $(patsubst %,$(BUILD)/our/src/%.o,msfa_dx7 dx7_voice dx7_loop msfa_tables msfa_rom)
$(MSFA_OUR_OBJ): COMMON += -isystem $(MSFA_DIR)

RENDER_EXTRA_OBJ += $(MSFA_OBJ)

-include $(MSFA_OBJ:.o=.d)

# fm1-dx7-oracle (test/dx7_oracle.cc): one voice through FM6 and through
# Felucca's fm6_core.c (third_party/felucca-fm6, Apache-2.0; set up in
# test/dx7_felucca.c), and how far apart they are; also msfa's start-up
# tables (tests/test_engines_dx7.py). A desktop test tool: fm6_core.c is in
# no engine. It is C, built with the vendored-code flags.
#
# For --tables-vs-msfa it also links msfa's own sin.cc, exp2.cc and
# freqlut.cc, compiled with FM1_MSFA_REF into namespace fm1_msfa_ref with
# their tables as plain arrays (src/msfa_prelude.h), as upstream builds them;
# test/msfa_ref.cc runs their init for the oracle.
MSFA_REF_OBJ := $(patsubst %,$(BUILD)/tp/msfa-ref/%.o,sin exp2 freqlut) $(BUILD)/our/test/msfa_ref.o
DX7_ORACLE_OBJ := $(BUILD)/our/test/dx7_oracle.o $(BUILD)/tp/felucca-fm6/dx7_felucca.o $(MSFA_REF_OBJ)

$(BUILD)/tp/msfa-ref/%.o: src/msfa_unit.cc src/msfa_prelude.h $(MSFA_DIR)/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -isystem $(MSFA_DIR) -DFM1_MSFA_REF \
	  -DFM1_MSFA_UNIT='"$*.cc"' -c $< -o $@

$(BUILD)/our/test/dx7_oracle.o $(BUILD)/our/test/msfa_ref.o: COMMON += -isystem $(MSFA_DIR)

$(BUILD)/tp/felucca-fm6/dx7_felucca.o: test/dx7_felucca.c third_party/felucca-fm6/fm6_core.c
	@mkdir -p $(dir $@)
	$(CC) -std=c99 $(OPT) $(EXTRA) -w -fwrapv -Ithird_party/felucca-fm6 -MMD -MP -c $< -o $@

all: $(BUILD)/fm1-dx7-oracle

$(BUILD)/fm1-dx7-oracle: $(DX7_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(DX7_ORACLE_OBJ:.o=.d)
