# Focused actual-app Capture probe, after engines/Makefile and sim.mk.
$(BUILD)/sim/test/fm1_capture_check.o: SIM_CFLAGS += -Werror
$(BUILD)/fm1-capture-check: $(BUILD)/sim/test/fm1_capture_check.o $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/sim/test/fm1_capture_check.d
