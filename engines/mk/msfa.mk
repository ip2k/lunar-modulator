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
#
# The sine switch (FM1_DX7_SINE, engines/Makefile): with trunc12, msfa is
# compiled from a copy of its files in $(BUILD)/gen/msfa-trunc12/ whose sin.h
# is src/msfa_sin_trunc12.h (made by tools/msfa_tables.py), since msfa's .cc
# files include "sin.h" from their own directory and a header search path
# cannot come first. MSFA_DIR is where msfa is compiled from, MSFA_VENDOR_DIR
# the vendored files, which the oracle's reference build of msfa's own init
# always uses. The copy is remade when any vendored file or the trunc12
# header changes; the generated fm1_dx7_sine.h rebuilds every object that
# includes msfa when the switch turns (src/msfa_prelude.h).
MSFA_VENDOR_DIR := third_party/msfa
ifeq ($(FM1_DX7_SINE),trunc12)
MSFA_DIR := $(BUILD)/gen/msfa-trunc12
MSFA_STAGE := $(MSFA_DIR)/.staged
$(MSFA_STAGE): $(wildcard $(MSFA_VENDOR_DIR)/*.h $(MSFA_VENDOR_DIR)/*.cc) src/msfa_sin_trunc12.h
	@rm -rf '$(MSFA_DIR)' && mkdir -p '$(MSFA_DIR)'
	cp $(MSFA_VENDOR_DIR)/*.h $(MSFA_VENDOR_DIR)/*.cc '$(MSFA_DIR)/'
	cp src/msfa_sin_trunc12.h '$(MSFA_DIR)/sin.h'
	@touch '$@'
else
MSFA_DIR := $(MSFA_VENDOR_DIR)
MSFA_STAGE :=
endif
MSFA_UNITS := dx7note env fm_core fm_op_kernel freqlut lfo patch pitchenv
MSFA_OBJ := $(patsubst %,$(BUILD)/tp/msfa/%.o,$(MSFA_UNITS))

$(BUILD)/tp/msfa/%.o: src/msfa_unit.cc src/msfa_prelude.h $(MSFA_VENDOR_DIR)/%.cc $(MSFA_STAGE)
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -isystem $(MSFA_DIR) \
	  -DFM1_MSFA_UNIT='"$*.cc"' -c $< -o $@

MSFA_OUR_OBJ := $(patsubst %,$(BUILD)/our/src/%.o,msfa_dx7 dx7_voice dx7_loop msfa_tables msfa_rom)
$(MSFA_OUR_OBJ): COMMON += -isystem $(MSFA_DIR)
$(MSFA_OUR_OBJ): $(MSFA_STAGE)

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

$(BUILD)/tp/msfa-ref/%.o: src/msfa_unit.cc src/msfa_prelude.h $(MSFA_VENDOR_DIR)/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(TP_WARN) $(TP_DIALECT) -isystem $(MSFA_VENDOR_DIR) -DFM1_MSFA_REF \
	  -DFM1_MSFA_UNIT='"$*.cc"' -c $< -o $@

$(BUILD)/our/test/dx7_oracle.o: COMMON += -isystem $(MSFA_DIR)
$(BUILD)/our/test/dx7_oracle.o: $(MSFA_STAGE)
$(BUILD)/our/test/msfa_ref.o: COMMON += -isystem $(MSFA_VENDOR_DIR)

$(BUILD)/tp/felucca-fm6/dx7_felucca.o: test/dx7_felucca.c third_party/felucca-fm6/fm6_core.c
	@mkdir -p $(dir $@)
	$(CC) -std=c99 $(OPT) $(EXTRA) -w -fwrapv -Ithird_party/felucca-fm6 -MMD -MP -c $< -o $@

all: $(BUILD)/fm1-dx7-oracle

$(BUILD)/fm1-dx7-oracle: $(DX7_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm

-include $(DX7_ORACLE_OBJ:.o=.d)

# Copied-kernel adapter differential and late-job lifetime checks. Built with
# the same target/sanitizer flags as the renderer, including the 32-bit job.
DX7_KERNEL_TEST_OBJ := $(BUILD)/our/test/dx7_kernel_test.o
DX7_MAILBOX_TEST_OBJ := $(BUILD)/our/test/fm6_pair_mailbox.o
$(DX7_MAILBOX_TEST_OBJ): ../firmware/devkit/fm6_pair_mailbox.cc ../firmware/devkit/fm6_pair_mailbox.h include/fm1_dx7_kernel.h
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DLUNAR_MAILBOX_HOST_TEST -c $< -o $@
$(DX7_KERNEL_TEST_OBJ): COMMON += -pthread
all: $(BUILD)/fm1-dx7-kernel-test
$(BUILD)/fm1-dx7-kernel-test: $(DX7_KERNEL_TEST_OBJ) $(DX7_MAILBOX_TEST_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -pthread -o $@ $(DX7_KERNEL_TEST_OBJ) $(DX7_MAILBOX_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm
-include $(DX7_KERNEL_TEST_OBJ:.o=.d) $(DX7_MAILBOX_TEST_OBJ:.o=.d)

# Exact algorithm-5 paired stacks against the original scalar runner.
DX7_PAIR_TEST_OBJ := $(BUILD)/our/test/dx7_pair_test.o
$(DX7_PAIR_TEST_OBJ): COMMON += -isystem $(MSFA_DIR)
$(DX7_PAIR_TEST_OBJ): $(MSFA_STAGE)
all: $(BUILD)/fm1-dx7-pair-test
$(BUILD)/fm1-dx7-pair-test: $(DX7_PAIR_TEST_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_PAIR_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm
-include $(DX7_PAIR_TEST_OBJ:.o=.d)

# Render-owned, opt-in voice admission and block-boundary retirement.
DX7_BUDGET_TEST_OBJ := $(BUILD)/our/test/dx7_budget_test.o
all: $(BUILD)/fm1-dx7-budget-test
$(BUILD)/fm1-dx7-budget-test: $(DX7_BUDGET_TEST_OBJ) $(BUILD)/fm1-render $(FM1_DROP_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_BUDGET_TEST_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm
-include $(DX7_BUDGET_TEST_OBJ:.o=.d)

# fm1-dx7-sine-oracle (test/dx7_sine_oracle.cc): msfa's operator kernels
# through the build's sine (FM1_DX7_SINE) against FM in doubles, in dB
# (tests/test_dx7_sine.py).
DX7_SINE_ORACLE_OBJ := $(BUILD)/our/test/dx7_sine_oracle.o
$(DX7_SINE_ORACLE_OBJ): COMMON += -isystem $(MSFA_DIR)
$(DX7_SINE_ORACLE_OBJ): $(MSFA_STAGE)
all: $(BUILD)/fm1-dx7-sine-oracle
$(BUILD)/fm1-dx7-sine-oracle: $(DX7_SINE_ORACLE_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(DX7_SINE_ORACLE_OBJ) \
	  $(filter-out $(BUILD)/our/host/render.o,$(RENDER_OBJ)) -lm
-include $(DX7_SINE_ORACLE_OBJ:.o=.d)
