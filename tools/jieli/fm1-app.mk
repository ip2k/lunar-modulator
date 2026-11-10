# The FM-1 application image (tools/jieli/prepare-fm1-app.py). Read by the
# nested engine make after renderer.mk and size-profile.mk. With
# -DLUNAR_FM1_APP=1 in EXTRA it swaps the dev-kit workload for the FM-1
# application: the kit's fixed test pattern (renderer_live), its timing and
# arithmetic probes and its internal-DAC transport leave the link; the app
# adapter, the SDK glue, the board layer, the display transport and the
# fm1-nes key tables (Apache-2.0) come in. Without the flag nothing changes.
ifneq ($(filter -DLUNAR_FM1_APP=1,$(EXTRA)),)
ifeq ($(filter -DLUNAR_PIPELINE_UNBOUNDED=1,$(EXTRA)),)
$(error The FM-1 application needs -DLUNAR_PIPELINE_UNBOUNDED=1)
endif
ifneq ($(filter -DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1,$(EXTRA)),)
$(error The FM-1 application must not link the dev-kit DAC transport)
endif
FM1_FIRMWARE ?= $(abspath $(SIM)/../../firmware)
DEVKIT_RENDERER_OBJ := $(filter-out $(BUILD)/devkit/renderer_live.o $(BUILD)/devkit/renderer_timing.o \
  $(BUILD)/devkit/arithmetic_probe.o $(BUILD)/devkit/renderer_pipeline_dac.o,$(DEVKIT_RENDERER_OBJ))
FM1_APP_SOURCES := fm1/fm1_input fm1/fm1_live fm1/fm1_sdk_main \
  board/board_io board/matrix board/adc board/midi_parser board/midi_uart \
  board/alnk0_audio board/alnk0_audio_mmio \
  display/spi1_transport display/panel_probe display/m5_pattern \
  third_party/fm1-nes/fm1_keys
# USB-MIDI device (prepare-fm1-app.py --usb-midi on): our descriptors and
# the glue on cpu.a's low-level driver; no SDK device class is compiled.
ifneq ($(filter -DLUNAR_FM1_USB_MIDI=1,$(EXTRA)),)
FM1_APP_SOURCES += fm1/fm1_usb_midi fm1/fm1_usb_sdk
endif
# Size levers (prepare-fm1-app.py --size-levers; notes/2026-11-10-size-levers.md).
# Each object appends to every object variable, as size-profile.mk does.
FM1_SIZE_VARS := SIM_CFLAGS SEQ_CFLAGS MOD_CFLAGS STATE_CFLAGS ARP_CFLAGS COMMON
# cold: units that run on an edit, a load or a save, at boot or in the
# panel's drawing, never in a block or at the drained barrier, at COLDOPT
# (-Oz); and the two text parsers' strtod/strtof mapped to firmware/fm1's
# exact fast-path parser, so newlib's strtod.o is not pulled into the link.
# SRAM code is unchanged [verified: nm, 2026-11-10].
ifneq ($(filter -DLUNAR_FM1_SIZE_COLD=1,$(EXTRA)),)
FM1_SIZE_COLD := sim/src/fm1_mod_ui sim/src/fm1_app_state c/seq/seq_persist \
  c/state/fm1_known c/state/fm1_meta state/host/state_clip state/state/fm1_deflate \
  state/state/fm1_json state/state/fm1_num state/state/state_bin state/state/state_json_read \
  state/state/state_json_write state/state/state_mod state/state/state_movy1 \
  state/state/state_names state/state/state_print state/state/state_registry \
  our/src/editor_meta our/src/registry midi_fx/registry \
  fm1app/display/m5_pattern fm1app/display/panel_probe fm1app/third_party/fm1-nes/fm1_keys
$(foreach v,$(FM1_SIZE_VARS),$(foreach o,$(FM1_SIZE_COLD),$(eval $$(BUILD)/$(o).o: $(v) += $(COLDOPT))))
FM1_SIZE_STRTOD := c/host/mod_script sim/src/fm1_edit
$(foreach v,$(FM1_SIZE_VARS),$(foreach o,$(FM1_SIZE_STRTOD),\
  $(eval $$(BUILD)/$(o).o: $(v) += -Dstrtod=lunar_fm1_strtod -Dstrtof=lunar_fm1_strtof)))
FM1_APP_SOURCES += fm1/fm1_strtod
endif
# control: also the app and the panel's input and drawing units that run
# around a block (the app's produce step, the step-sequencer UI, capture, the
# key, encoder and MIDI input, the display transport) at COLDOPT. This changes
# SRAM code. On the dev kit it costs about 2.4% of the producer's mean block
# time with bit-identical audio; the sequencer engine, the arpeggiator and the
# modulation runtime stay at the build's level, because at COLDOPT they cost
# about 6.4% (notes/2026-11-10-size-levers.md). Needs cold.
ifneq ($(filter -DLUNAR_FM1_SIZE_CONTROL=1,$(EXTRA)),)
ifeq ($(filter -DLUNAR_FM1_SIZE_COLD=1,$(EXTRA)),)
$(error -DLUNAR_FM1_SIZE_CONTROL=1 needs -DLUNAR_FM1_SIZE_COLD=1)
endif
FM1_SIZE_CONTROL := sim/src/fm1_app sim/src/fm1_seq_ui c/seq/seq_capture \
  fm1app/fm1/fm1_input fm1app/fm1/fm1_live fm1app/board/matrix fm1app/board/adc \
  fm1app/board/midi_parser fm1app/board/midi_uart fm1app/display/spi1_transport
$(foreach v,$(FM1_SIZE_VARS),$(foreach o,$(FM1_SIZE_CONTROL),$(eval $$(BUILD)/$(o).o: $(v) += $(COLDOPT))))
endif
FM1_APP_OBJ := $(FM1_APP_SOURCES:%=$(BUILD)/fm1app/%.o)
DEVKIT_RENDERER_OBJ += $(FM1_APP_OBJ)

# SDK headers use GNU asm spelling, as the kit's pipeline transport does.
$(BUILD)/fm1app/%.o: $(FM1_FIRMWARE)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -std=gnu99 -DLUNAR_PI32V2=1 -I$(FM1_FIRMWARE)/fm1 \
	  -I$(FM1_FIRMWARE)/devkit -I$(FM1_FIRMWARE)/failopen -c $< -o $@

-include $(wildcard $(BUILD)/fm1app/*/*.d $(BUILD)/fm1app/third_party/fm1-nes/*.d)
endif
