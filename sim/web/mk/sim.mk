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

SIM_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Wall -Wextra -Iinclude -I$(GPL_GEN) -I$(SIM)/src -MMD -MP

# Every engine object fm1-render links, without its main() (msfa's units,
# MSFA_OBJ, mk/msfa.mk, among them, and the GPL modules' C objects, GPL_OBJ,
# while the GPL switch is on: engines/Makefile), the sequencer
# core with its host bridge (SEQ_OBJ, mk/seq.mk: C99, no heap, no stdio),
# and the modulation runtime with its kinds and primitives (MODC_OBJ,
# MOD_OBJ, mk/mod.mk: no heap, no stdio, no libm) and its script reader
# (MOD_SCRIPT_OBJ: snprintf and strtod, no files, no heap), which the app
# takes lines through. The verb script reader (SEQ_HOST_OBJ) allocates and
# uses stdio, so only the native harness links it; in fm1.wasm it would add
# WASI imports.
SIM_ENGINE_OBJ := $(filter-out $(BUILD)/our/host/render.o $(FM1_DROP_OBJ),$(OUR_OBJ) $(TP_OBJ) $(SW_OBJ) \
  $(MSFA_OBJ) $(SEQ_OBJ) $(MODC_OBJ) $(MOD_OBJ) $(MOD_SCRIPT_OBJ) $(ARP_OBJ) $(GPL_OBJ))
# The metadata export (META_OBJ, mk/meta.mk: fm1_meta.c and the known ids,
# with the state files' number formatter it writes floats with): the module
# returns its id (fm1w_meta_id) and the export a buffer at a time
# (fm1w_meta_read), from which build.sh writes the page's meta.json; the
# harness writes it too (--meta), with its own instance bytes.
# The app's saved state (fm1_app_state.c, stage A1): the state core's
# codecs, names and registries, the runtime's records and the clip merge.
SIM_META_OBJ = $(META_OBJ) $(STATE_OBJ) $(STATE_REG_OBJ) $(STATE_MOD_OBJ) $(STATE_CLIP_OBJ)
# The app layer: the panel, the chain and the screen, the sequencer's panel
# UI and screens (fm1_seq_ui, fm1_seq_view), and modulation's (fm1_mod_ui,
# fm1_mod_view; docs/16 MG3).
SIM_APP_OBJ := $(BUILD)/sim/src/fm1_app.o $(BUILD)/sim/src/fm1_tft.o \
  $(BUILD)/sim/src/fm1_seq_ui.o $(BUILD)/sim/src/fm1_seq_view.o \
  $(BUILD)/sim/src/fm1_mod_ui.o $(BUILD)/sim/src/fm1_mod_view.o $(BUILD)/sim/src/fm1_app_state.o \
  $(BUILD)/sim/src/fm1_edit.o

# The harness reads verb scripts (host/seq_script.h); the app reads
# modulation lines (host/mod_script.h).
$(BUILD)/sim/test/fm1_sim_render.o: SIM_CFLAGS += -Ihost
$(BUILD)/sim/src/fm1_app.o $(BUILD)/sim/src/fm1_mod_ui.o: SIM_CFLAGS += -Ihost
# The edit layer (fm1_edit.c, stage ED1) speaks the state core's records;
# the app takes its view verb's FM1_VIEW_* from there too.
$(BUILD)/sim/src/fm1_app.o: SIM_CFLAGS += -Istate
$(BUILD)/sim/src/fm1_app_state.o $(BUILD)/sim/src/fm1_web.o $(BUILD)/sim/test/fm1_sim_render.o \
  $(BUILD)/sim/src/fm1_edit.o $(BUILD)/sim/test/fm1_edit_check.o: SIM_CFLAGS += -Istate -Ihost

$(BUILD)/sim/%.o: $(SIM)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -c $< -o $@

$(BUILD)/fm1-sim-render: $(SIM_APP_OBJ) $(BUILD)/sim/test/fm1_sim_render.o $(BUILD)/sim/test/fm1_edit_check.o \
    $(SIM_ENGINE_OBJ) \
    $(SIM_META_OBJ) $(SEQ_HOST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# The WebAssembly module: standalone (no Emscripten JavaScript runtime), a
# reactor with no main, fixed memory, and only the fm1w_* functions exported.
# The page's own loader (www/fm1-wasm.mjs) stubs any import, so the module
# must not depend on one: test/parity.mjs lists them and fails on any.
WASM_EXPORTS := fm1w_init fm1w_default_chain fm1w_catalog fm1w_select fm1w_unit_index \
  fm1w_set_param fm1w_get_param fm1w_ram fm1w_ram_part fm1w_mod_records fm1w_state_hash fm1w_unit_bytes fm1w_note_on fm1w_note_off \
  fm1w_pitch_bend fm1w_all_notes_off fm1w_key fm1w_button fm1w_encoder fm1w_master \
  fm1w_render fm1w_draw fm1w_screen fm1w_leds fm1w_leds_changed fm1w_mode \
  fm1w_text_buf fm1w_text_cap fm1w_seq_text fm1w_seq_reset fm1w_seq_dropped \
  fm1w_seq_info fm1w_sound_unit fm1w_insert_unit fm1w_unit_current \
  fm1w_unit_set_current fm1w_unit_level fm1w_unit_set_level fm1w_unit_note_on \
  fm1w_unit_note_off fm1w_unit_route fm1w_ram_budget fm1w_mod_reset fm1w_mod_text \
  fm1w_arp_on fm1w_arp_set_on fm1w_arp_set_param fm1w_arp_get_param fm1w_mfx_select \
  fm1w_dx7_load fm1w_dx7_result fm1w_dx7_name fm1w_meta_id fm1w_meta_read \
  fm1w_state_save fm1w_state_check fm1w_state_load fm1w_state_pack fm1w_state_report \
  fm1w_save_gen fm1w_store_ready fm1w_saved \
  fm1w_edit_buf fm1w_edit_codes fm1w_edit fm1w_edit_verb fm1w_edit_text fm1w_edit_gen \
  fm1w_changes_buf fm1w_changes fm1w_tele_mask fm1w_subscribe fm1w_tele_buf fm1w_telemetry \
  fm1w_view_get fm1w_edit_dump fm1w_param_text fm1w_param_parse fm1w_param_value
comma := ,
empty :=
space := $(empty) $(empty)
WASM_LDFLAGS := --no-entry -sSTANDALONE_WASM=1 -sFILESYSTEM=0 -sALLOW_MEMORY_GROWTH=0 \
  -sINITIAL_MEMORY=8388608 -sSTACK_SIZE=262144 \
  -sEXPORTED_FUNCTIONS=$(subst $(space),$(comma),$(addprefix _,$(WASM_EXPORTS)))

$(BUILD)/fm1.wasm: $(SIM_APP_OBJ) $(BUILD)/sim/src/fm1_web.o $(SIM_ENGINE_OBJ) $(SIM_META_OBJ)
	$(CXX) $(OPT) $(EXTRA) $(WASM_LDFLAGS) -o $@ $^

# The reference host itself compiled to WebAssembly and run by Node, so the
# parity test can separate the compiler and libm from the app layer. It links
# exactly what native fm1-render links (RENDER_OBJ: our engines, Mutable's,
# Schwung's modules and the sequencer), so it cannot fall behind the host.
$(BUILD)/fm1-render.js: $(RENDER_PRODUCT_OBJ)
	$(CXX) $(OPT) $(EXTRA) -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sEXIT_RUNTIME=1 -o $@ $^

-include $(SIM_APP_OBJ:.o=.d) $(BUILD)/sim/src/fm1_web.d $(BUILD)/sim/test/fm1_sim_render.d \
  $(BUILD)/sim/test/fm1_edit_check.d
