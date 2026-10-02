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

# Every engine object fm1-render links, without its main().
SIM_ENGINE_OBJ := $(filter-out $(BUILD)/our/host/render.o,$(OUR_OBJ)) $(TP_OBJ) $(SW_OBJ)
SIM_APP_OBJ := $(BUILD)/sim/src/fm1_app.o $(BUILD)/sim/src/fm1_tft.o

$(BUILD)/sim/%.o: $(SIM)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -c $< -o $@

$(BUILD)/fm1-sim-render: $(SIM_APP_OBJ) $(BUILD)/sim/test/fm1_sim_render.o $(SIM_ENGINE_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# The WebAssembly module: standalone (no Emscripten JavaScript runtime), a
# reactor with no main, fixed memory, and only the fm1w_* functions exported.
# The page's own loader (www/fm1-wasm.mjs) stubs any import, so the module
# must not depend on one: test/parity.mjs lists them and fails on any.
WASM_EXPORTS := fm1w_init fm1w_default_chain fm1w_catalog fm1w_select fm1w_unit_index \
  fm1w_set_param fm1w_get_param fm1w_ram fm1w_unit_bytes fm1w_note_on fm1w_note_off \
  fm1w_pitch_bend fm1w_all_notes_off fm1w_key fm1w_button fm1w_encoder fm1w_master \
  fm1w_render fm1w_draw fm1w_screen fm1w_leds fm1w_leds_changed fm1w_mode
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
