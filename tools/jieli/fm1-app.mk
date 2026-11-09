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
FM1_APP_OBJ := $(FM1_APP_SOURCES:%=$(BUILD)/fm1app/%.o)
DEVKIT_RENDERER_OBJ += $(FM1_APP_OBJ)

# SDK headers use GNU asm spelling, as the kit's pipeline transport does.
$(BUILD)/fm1app/%.o: $(FM1_FIRMWARE)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -std=gnu99 -DLUNAR_PI32V2=1 -I$(FM1_FIRMWARE)/fm1 \
	  -I$(FM1_FIRMWARE)/devkit -I$(FM1_FIRMWARE)/failopen -c $< -o $@

-include $(wildcard $(BUILD)/fm1app/*/*.d $(BUILD)/fm1app/third_party/fm1-nes/*.d)
endif
