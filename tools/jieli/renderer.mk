# Read after engines/Makefile and sim/web/mk/sim.mk. The actual shared app,
# including modulation text used only during setup. No WebAssembly glue or
# desktop sequencer script reader is needed by the target workload.
DEVKIT ?= $(abspath $(SIM)/../../firmware/devkit)
DEVKIT_RENDERER_OBJ = $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) \
  $(BUILD)/devkit/renderer_live.o

$(BUILD)/devkit/%.o: $(DEVKIT)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -I$(DEVKIT) -c $< -o $@

$(BUILD)/fm1-devkit-renderer-ref: $(DEVKIT_RENDERER_OBJ) $(BUILD)/devkit/renderer_reference.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

.PHONY: print-devkit-renderer-objs
print-devkit-renderer-objs:
	@printf '%s\n' $(sort $(DEVKIT_RENDERER_OBJ))

-include $(BUILD)/devkit/renderer_live.d $(BUILD)/devkit/renderer_reference.d
