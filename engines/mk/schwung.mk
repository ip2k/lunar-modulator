# mk/schwung.mk -- the Schwung v2 compatibility shim, the Schwung modules built
# through it, and its selftest (engines/schwung.md).
#
# Vendored module sources are C, built with $(CC) and the same $(OPT) and
# $(EXTRA) as everything else. Each is compiled with:
#   -include src/schwung_module_prefix.h   malloc/calloc/realloc/free -> the
#                                          shim's bounded arena
#   -I <its own directory>                 its own copy of the Schwung headers,
#                                          as upstream builds it
#   -D<entry point>=fm1_sw_<id>_init       so several modules can be linked
#                                          into one firmware

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/schwung_shim.cc src/sw_sophie.cc src/sw_psxverb.cc

SW_DIR := third_party/schwung-modules
SW_PREFIX := src/schwung_module_prefix.h
SW_CFLAGS := -std=c11 $(OPT) $(EXTRA) -w -include $(SW_PREFIX)

SW_OBJ := $(BUILD)/sw/sophie/sophie.o $(BUILD)/sw/psxverb/psxverb.o

$(BUILD)/sw/sophie/%.o: SW_DEFS := -Dmove_plugin_init_v2=fm1_sw_sophie_init
$(BUILD)/sw/psxverb/%.o: SW_DEFS := -Dmove_audio_fx_init_v2=fm1_sw_psxverb_init

$(BUILD)/sw/%.o: $(SW_DIR)/%.c $(SW_PREFIX)
	@mkdir -p $(dir $@)
	$(CC) $(SW_CFLAGS) $(SW_DEFS) -I$(dir $<) -c $< -o $@

# The shim, the adapters and the selftest see the canonical ABI headers.
SW_OUR_OBJ := $(BUILD)/our/src/schwung_shim.o $(BUILD)/our/src/sw_sophie.o \
              $(BUILD)/our/src/sw_psxverb.o $(BUILD)/our/test/schwung_selftest.o
$(SW_OUR_OBJ): COMMON += -isystem third_party/schwung
$(SW_OUR_OBJ): src/schwung_shim.h src/schwung_abi.h

$(BUILD)/fm1-render: $(SW_OBJ)

# fm1-schwung-selftest: arena bounds and exhaustion, re-blocking, MIDI and
# parameter encoding, and the parameter tables against the modules' own
# chain_params (run by tests/test_engines_schwung.py).
SW_SELFTEST_OBJ := $(BUILD)/our/test/schwung_selftest.o $(BUILD)/our/src/schwung_shim.o \
                   $(BUILD)/our/src/sw_sophie.o $(BUILD)/our/src/sw_psxverb.o $(SW_OBJ)

all: $(BUILD)/fm1-schwung-selftest

$(BUILD)/fm1-schwung-selftest: $(SW_SELFTEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# fm1-schwung-race: instances render on a thread while others are created and
# destroyed. Meaningful only under ThreadSanitizer, so not part of `all`:
#   make -C engines EXTRA="-fsanitize=thread -g" OPT=-O1 build/fm1-schwung-race
SW_RACE_OBJ := $(BUILD)/our/test/schwung_race.o $(BUILD)/our/src/schwung_shim.o \
               $(BUILD)/our/src/sw_sophie.o $(BUILD)/our/src/sw_psxverb.o $(SW_OBJ)
$(BUILD)/our/test/schwung_race.o: COMMON += -pthread

$(BUILD)/fm1-schwung-race: $(SW_RACE_OBJ)
	$(CXX) $(OPT) $(EXTRA) -pthread -o $@ $^ -lm
