# mk/midi_fx.mk -- the MIDI effects (engines/midi_fx/): the arpeggiator core
# fm1_arp (C99, heap-free) and its test tool fm1-arp (engines/midi_fx/README.md).
#
# The core never allocates: tests/test_engine_arp.py checks its objects'
# symbols for malloc, free and stdio. The tool may.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

ARP_SRC := midi_fx/fm1_arp.c midi_fx/arp_rhythm.c
ARP_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Imidi_fx -Wall -Wextra -Wpedantic -Wshadow -MMD -MP
ARP_OBJ := $(patsubst midi_fx/%.c,$(BUILD)/midi_fx/%.o,$(ARP_SRC))
ARP_TOOL_OBJ := $(BUILD)/midi_fx/arp_tool.o

$(BUILD)/midi_fx/%.o: midi_fx/%.c
	@mkdir -p $(dir $@)
	$(CC) $(ARP_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-arp

$(BUILD)/fm1-arp: $(ARP_TOOL_OBJ) $(ARP_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^

-include $(ARP_OBJ:.o=.d) $(ARP_TOOL_OBJ:.o=.d)
