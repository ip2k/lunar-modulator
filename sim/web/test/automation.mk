# Focused native automation probe, read after engines/Makefile and sim.mk.
$(BUILD)/sim/test/fm1_seq_automation_check.o: SIM_CFLAGS += -Istate -Ihost
$(BUILD)/fm1-seq-automation-check: $(BUILD)/sim/test/fm1_seq_automation_check.o $(filter-out $(BUILD)/sim/src/fm1_app.o,$(SIM_APP_OBJ)) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(SEQ_HOST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm
