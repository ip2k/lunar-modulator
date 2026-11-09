# Host build of the FM-1 audio adapter (firmware/fm1/fm1_live.c) with the
# pipelined shared app, for tests/test_fm1_live.py. Read after
# engines/Makefile and sim/web/mk/sim.mk. replay.c includes fm1_live.c so it
# can reach the adapter's private app for the guard's negative control; the
# SDK glue (fm1_sdk_main.c) and the native pipeline are not linked.
FM1_FW := $(abspath $(SIM)/../../firmware)
FM1_LIVE_REPLAY ?= $(abspath $(SIM)/../../tests/fixtures/fm1_live/replay.c)
FM1_LIVE_HOST_SRC := fm1/fm1_input board/board_io board/adc board/midi_parser \
  third_party/fm1-nes/fm1_keys
FM1_LIVE_HOST_OBJ := $(FM1_LIVE_HOST_SRC:%=$(BUILD)/fm1host/%.o)
FM1_LIVE_INC := -I$(FM1_FW)/fm1 -I$(FM1_FW)/devkit

$(BUILD)/fm1host/%.o: $(FM1_FW)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) $(FM1_LIVE_INC) -c $< -o $@

$(BUILD)/fm1host/replay.o: $(FM1_LIVE_REPLAY) $(FM1_FW)/fm1/fm1_live.c
	@mkdir -p $(dir $@)
	$(CC) $(SIM_CFLAGS) $(FM1_LIVE_INC) -c $< -o $@

$(BUILD)/fm1-live-replay: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) \
    $(FM1_LIVE_HOST_OBJ) $(BUILD)/fm1host/replay.o
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm
