# mk/midi_fx.mk -- the MIDI effects (engines/midi_fx/): the arpeggiator core
# fm1_arp (C99, heap-free), its engine API v3 wrapper (arp_engine.c, kind
# FM1_KIND_MIDI_FX) and the MIDI effects' registry (registry.c), which
# fm1-render and the virtual FM-1 link; and the core's test tool fm1-arp
# (engines/midi_fx/README.md).
#
# None of it allocates or prints: tests/test_engine_arp.py checks the
# objects' symbols for malloc, free and stdio. The tool may. The registry
# reads the GPL switch (FM1_GPL_MODS, engines/Makefile): a GPL MIDI effect is
# listed only when it is on, and its sources come from its own fragment.

# This fragment adds prerequisites to targets before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

ARP_SRC := midi_fx/fm1_arp.c midi_fx/arp_rhythm.c midi_fx/arp_engine.c midi_fx/registry.c
ARP_CFLAGS := -std=c99 $(OPT) $(EXTRA) -Imidi_fx -Iinclude -I$(GPL_GEN) -Wall -Wextra -Wpedantic -Wshadow -MMD -MP
ARP_OBJ := $(patsubst midi_fx/%.c,$(BUILD)/midi_fx/%.o,$(ARP_SRC))
ARP_TOOL_OBJ := $(BUILD)/midi_fx/arp_tool.o

$(BUILD)/midi_fx/%.o: midi_fx/%.c
	@mkdir -p $(dir $@)
	$(CC) $(ARP_CFLAGS) -c $< -o $@

all: $(BUILD)/fm1-arp

$(BUILD)/fm1-arp: $(ARP_TOOL_OBJ) $(ARP_OBJ)
	$(CC) $(OPT) $(EXTRA) -o $@ $^

# fm1-render runs MIDI effects in front of its sounds (--mfx); every renderer
# variant that links RENDER_OBJ gets them.
RENDER_EXTRA_OBJ += $(ARP_OBJ)

-include $(ARP_OBJ:.o=.d) $(ARP_TOOL_OBJ:.o=.d)
