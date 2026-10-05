# fx3-hostile.mk -- fm1-fx3-hostile (engines/test/fx3_hostile.cc, run by
# tests/test_engines_fx3_hostile.py): a reviewer's hostile checks across the
# third effects pack, Room, Hall, Gate and Plate with Freeze, driven the same
# way: random parameter schedules (NaN and infinities included) and bad input
# at any block pattern, memory fill and three host rates; the Gate never
# amplifying; its key hook; and tails at the longest settings reaching exact
# zeros. It links the effects' ordinary objects. Not in OUR_SRC: it has a
# main().

# Fragments are read before the main Makefile's first rule; keep `all` the
# default goal.
.DEFAULT_GOAL := all

FX3_HOSTILE_OBJ := $(BUILD)/our/test/fx3_hostile.o $(BUILD)/our/src/fx_room.o \
                   $(BUILD)/our/src/fx_hall.o $(BUILD)/our/src/fx_gate.o \
                   $(BUILD)/our/src/mi_fx.o $(BUILD)/tp/plaits/resources.o

all: $(BUILD)/fm1-fx3-hostile

$(BUILD)/fm1-fx3-hostile: $(FX3_HOSTILE_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

-include $(BUILD)/our/test/fx3_hostile.d
