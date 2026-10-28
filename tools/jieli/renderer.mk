# Read after engines/Makefile and sim/web/mk/sim.mk. The actual shared app,
# including modulation text used only during setup. No WebAssembly glue or
# desktop sequencer script reader is needed by the target workload.
DEVKIT ?= $(abspath $(SIM)/../../firmware/devkit)
DEVKIT_RENDERER_OBJ = $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) \
  $(BUILD)/devkit/renderer_live.o $(BUILD)/devkit/renderer_timing.o \
  $(BUILD)/devkit/arithmetic_probe.o

ifneq ($(filter -DLUNAR_DEVKIT_FM6_PAIR=1,$(EXTRA)),)
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/fm6_pair_bridge.o $(BUILD)/devkit/fm6_pair_mailbox.o
endif
ifneq ($(filter -DLUNAR_DEVKIT_FM6_SDK=1,$(EXTRA)),)
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/fm6_pair_sdk.o
# SDK headers use GNU asm spelling. Keep the shared renderer strictly C99.
$(BUILD)/devkit/fm6_pair_sdk.o: SIM_CFLAGS += -std=gnu99
endif

# The pipelined transport and app adapter are opt-in; native DAC/preparation
# integration is separate.
# It owns CPU1; it cannot coexist with either older worker backend.
ifneq ($(filter -DLUNAR_DEVKIT_RENDERER_PIPELINE=1,$(EXTRA)),)
ifneq ($(filter -DLUNAR_DEVKIT_FM6_PAIR=1 -DLUNAR_DEVKIT_FM6_SDK=1 -DLUNAR_DEVKIT_QUEUE_SDK=1 -DLUNAR_DEVKIT_ENGINE_QUEUE=1,$(EXTRA)),)
$(error Renderer pipeline must not nest another SDK worker)
endif
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/renderer_pipeline_sdk.o
$(BUILD)/devkit/renderer_pipeline_sdk.o: SIM_CFLAGS += -std=gnu99
endif

# Native DAC driver remains a separate opt-in from host app/backend replay.
ifneq ($(filter -DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1,$(EXTRA)),)
ifeq ($(filter -DLUNAR_DEVKIT_RENDERER_PIPELINE=1,$(EXTRA)),)
$(error Pipeline DAC requires the renderer pipeline backend)
endif
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/renderer_pipeline_dac.o
$(BUILD)/devkit/renderer_pipeline_dac.o: SIM_CFLAGS += -std=gnu99
endif

ifneq ($(filter -DLUNAR_DEVKIT_ENGINE_QUEUE=1,$(EXTRA)),)
ifneq ($(filter -DLUNAR_DEVKIT_FM6_PAIR=1 -DLUNAR_DEVKIT_FM6_SDK=1,$(EXTRA)),)
$(error Whole-engine queue must not nest the FM6 worker)
endif
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/renderer_queue.o $(BUILD)/devkit/renderer_queue_bridge.o
ifneq ($(filter -DLUNAR_DEVKIT_QUEUE_SDK=1,$(EXTRA)),)
DEVKIT_RENDERER_OBJ += $(BUILD)/devkit/renderer_queue_sdk.o
$(BUILD)/devkit/renderer_queue_sdk.o: SIM_CFLAGS += -std=gnu99
endif
endif

$(BUILD)/devkit/%.o: $(DEVKIT)/%.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -I$(DEVKIT) -c $< -o $@

$(BUILD)/devkit/%.o: $(DEVKIT)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -I$(DEVKIT) -c $< -o $@

$(BUILD)/fm1-devkit-renderer-ref: $(DEVKIT_RENDERER_OBJ) $(BUILD)/devkit/renderer_reference.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

.PHONY: print-devkit-renderer-objs
print-devkit-renderer-objs:
	@printf '%s\n' $(sort $(DEVKIT_RENDERER_OBJ))

-include $(wildcard $(BUILD)/devkit/*.d)
