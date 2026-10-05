# room.mk -- Room, the reverb and diffuser of Mutable Instruments Clouds
# (engines/src/fx_room.cc; the classes are vendored unmodified in
# third_party/mutable/clouds and header-only; parameters in
# engines/README.md, "Room"), and two tools:
#
#   fm1-room-test  drives Room where fm1-render cannot: parameters changed
#                  while audio runs, block sizes that change between calls,
#                  host rates, the libm-free maths (engines/test/room_test.cc,
#                  run by tests/test_engines_room.py)
#   fm1-ref-room   the upstream side of the reference renders: clouds::Diffuser
#                  and clouds::Reverb driven as Clouds' granular processor
#                  drives them (engines/test/ref_room.cc, run by
#                  tests/test_engines_reference_room.py)
#
# Neither tool is in OUR_SRC: each has a main(). No third-party .cc is
# needed; the simulator's build (sim/web/mk/sim.mk) links Room through
# OUR_SRC.

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_room.cc

# fm1-room-test links the effect built once more with FM1_ROOM_PROBE, which
# only adds an entry point that counts the diffuser's tiny cells; the audio
# path is the same code.
ROOM_TEST_OBJ := $(BUILD)/our/test/room_test.o $(BUILD)/our/test/fx_room_probe.o
REF_ROOM_OBJ := $(BUILD)/our/test/ref_room.o

all: $(BUILD)/fm1-room-test $(BUILD)/fm1-ref-room

$(BUILD)/our/test/fx_room_probe.o: src/fx_room.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_ROOM_PROBE -c $< -o $@

$(BUILD)/fm1-room-test: $(ROOM_TEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

$(BUILD)/fm1-ref-room: $(REF_ROOM_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/room_test.d $(BUILD)/our/test/ref_room.d $(BUILD)/our/test/fx_room_probe.d
