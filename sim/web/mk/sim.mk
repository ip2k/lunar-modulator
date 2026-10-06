# sim/web/mk/sim.mk -- the virtual FM-1's build, read after engines/Makefile so
# it reuses that Makefile's source lists, flags and object rules unchanged:
#
#   make -C engines -f Makefile -f $SIM/mk/sim.mk SIM=$SIM BUILD=$OUT TARGET...
#
# SIM and BUILD must be absolute paths. Targets:
#   $(BUILD)/fm1-sim-render   native harness (sim/web/test/fm1_sim_render.c)
#   $(BUILD)/fm1.wasm         the browser module, with CC=emcc CXX=em++
#   $(BUILD)/fm1-render.js    engines/host/render.cc for Node, with CC=emcc CXX=em++
# Engine objects land in $(BUILD) too, so a native and a WebAssembly build
# never share one. sim/web/build-on-aeon.sh and tests/test_sim_web.py drive it.

SIM ?= $(abspath ../sim/web)

SIM_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Wall -Wextra -Iinclude -I$(SIM)/src -MMD -MP

# Every engine object fm1-render links, without its main() (msfa's units,
# MSFA_OBJ, mk/msfa.mk, among them), the sequencer
# core with its host bridge (SEQ_OBJ, mk/seq.mk: C99, no heap, no stdio),
# and the modulation runtime with its kinds and primitives (MODC_OBJ,
# MOD_OBJ, mk/mod.mk: no heap, no stdio, no libm) and its script reader
# (MOD_SCRIPT_OBJ: snprintf and strtod, no files, no heap), which the app
# takes lines through. The verb script reader (SEQ_HOST_OBJ) allocates and
# uses stdio, so only the native harness links it; in fm1.wasm it would add
# WASI imports.
SIM_ENGINE_OBJ := $(filter-out $(BUILD)/our/host/render.o,$(OUR_OBJ)) $(TP_OBJ) $(SW_OBJ) $(MSFA_OBJ) $(SEQ_OBJ) \
  $(MODC_OBJ) $(MOD_OBJ) $(MOD_SCRIPT_OBJ) $(ARP_OBJ)
# The app layer: the panel, the chain and the screen, the sequencer's panel
# UI and screens (fm1_seq_ui, fm1_seq_view), and modulation's (fm1_mod_ui,
# fm1_mod_view; docs/16 MG3).
SIM_APP_OBJ := $(BUILD)/sim/src/fm1_app.o $(BUILD)/sim/src/fm1_tft.o \
  $(BUILD)/sim/src/fm1_seq_ui.o $(BUILD)/sim/src/fm1_seq_view.o \
  $(BUILD)/sim/src/fm1_mod_ui.o $(BUILD)/sim/src/fm1_mod_view.o

# The harness reads verb scripts (host/seq_script.h); the app reads
# modulation lines (host/mod_script.h).
$(BUILD)/sim/test/fm1_sim_render.o: SIM_CFLAGS += -Ihost
$(BUILD)/sim/src/fm1_app.o $(BUILD)/sim/src/fm1_mod_ui.o: SIM_CFLAGS += -Ihost

$(BUILD)/sim/%.o: $(SIM)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -c $< -o $@

$(BUILD)/fm1-sim-render: $(SIM_APP_OBJ) $(BUILD)/sim/test/fm1_sim_render.o $(SIM_ENGINE_OBJ) \
    $(SEQ_HOST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# The WebAssembly module: standalone (no Emscripten JavaScript runtime), a
# reactor with no main, fixed memory, and only the fm1w_* functions exported.
# The page's own loader (www/fm1-wasm.mjs) stubs any import, so the module
# must not depend on one: test/parity.mjs lists them and fails on any.
WASM_EXPORTS := fm1w_init fm1w_default_chain fm1w_catalog fm1w_select fm1w_unit_index \
  fm1w_set_param fm1w_get_param fm1w_ram fm1w_unit_bytes fm1w_note_on fm1w_note_off \
  fm1w_pitch_bend fm1w_all_notes_off fm1w_key fm1w_button fm1w_encoder fm1w_master \
  fm1w_render fm1w_draw fm1w_screen fm1w_leds fm1w_leds_changed fm1w_mode \
  fm1w_text_buf fm1w_text_cap fm1w_seq_text fm1w_seq_reset fm1w_seq_dropped \
  fm1w_seq_info fm1w_sound_unit fm1w_insert_unit fm1w_unit_current \
  fm1w_unit_set_current fm1w_unit_level fm1w_unit_set_level fm1w_unit_note_on \
  fm1w_unit_note_off fm1w_unit_route fm1w_ram_budget fm1w_mod_reset fm1w_mod_text \
  fm1w_arp_on fm1w_arp_set_on fm1w_arp_set_param fm1w_arp_get_param
comma := ,
empty :=
space := $(empty) $(empty)
WASM_LDFLAGS := --no-entry -sSTANDALONE_WASM=1 -sFILESYSTEM=0 -sALLOW_MEMORY_GROWTH=0 \
  -sINITIAL_MEMORY=8388608 -sSTACK_SIZE=262144 \
  -sEXPORTED_FUNCTIONS=$(subst $(space),$(comma),$(addprefix _,$(WASM_EXPORTS)))

$(BUILD)/fm1.wasm: $(SIM_APP_OBJ) $(BUILD)/sim/src/fm1_web.o $(SIM_ENGINE_OBJ)
	$(CXX) $(OPT) $(EXTRA) $(WASM_LDFLAGS) -o $@ $^

# The reference host itself compiled to WebAssembly and run by Node, so the
# parity test can separate the compiler and libm from the app layer. It links
# exactly what native fm1-render links (RENDER_OBJ: our engines, Mutable's,
# Schwung's modules and the sequencer), so it cannot fall behind the host.
$(BUILD)/fm1-render.js: $(RENDER_OBJ)
	$(CXX) $(OPT) $(EXTRA) -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sEXIT_RUNTIME=1 -o $@ $^

-include $(SIM_APP_OBJ:.o=.d) $(BUILD)/sim/src/fm1_web.d $(BUILD)/sim/test/fm1_sim_render.d
