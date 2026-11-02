# SPDX-License-Identifier: MIT. Read after engines/Makefile and sim.mk.
NATIVE := $(abspath ../firmware/native)
SIM_NATIVE := $(abspath ../sim/web)
DIAGNOSTIC_OBJ := $(BUILD)/native/diagnostic_app.o
$(BUILD)/native/diagnostic_app.o: $(NATIVE)/diagnostic_app.c $(NATIVE)/diagnostic_app.h
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -I$(NATIVE) -c $< -o $@
$(BUILD)/native/diagnostic_host.o: $(NATIVE)/diagnostic_host.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) -I$(NATIVE) -c $< -o $@
$(BUILD)/native-diagnostic-check: $(DIAGNOSTIC_OBJ) $(BUILD)/native/diagnostic_host.o $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm
