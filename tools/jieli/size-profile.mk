# Image-size levers for the dev-kit pipeline image (prepare-pipeline-devkit.py
# --size-profile). Read after renderer.mk by the nested engine make, with
# COLDOPT (-Oz) set by the preparer. Compiler levers only: no feature is removed
# and no per-sample or per-block code changes its optimisation level.
# Measurements and the TUs that were tried and refused: notes/2026-11-08-fit-size.md.

# 1. libc++'s extern template for std::sort<float*> pulls the whole
#    libc++.a(algorithm.cpp.o) (17,342 B) for the one sort in Plaits' chord
#    bank. Instantiating it in the TU instead links only the sort itself.
SIZE_CHORD_BANK := tp/plaits/dsp/chords/chord_bank
$(foreach o,$(SIZE_CHORD_BANK),$(eval $$(BUILD)/$(o).o: SIM_CFLAGS += -D_LIBCPP_DISABLE_EXTERN_TEMPLATE))
$(foreach o,$(SIZE_CHORD_BANK),$(eval $$(BUILD)/$(o).o: COMMON += -D_LIBCPP_DISABLE_EXTERN_TEMPLATE))

# 2. Cold translation units at COLDOPT: they run on an edit, a command line or a
#    text script, never inside a block. The object variable names differ per
#    makefile (engines/Makefile, sim.mk and the mod/seq/state/arp fragments), so
#    each object appends to all of them.
#      mod_script    text modulation-script parser
#      seq_cmd       sequencer command-line interpreter
#      mod_plan      modulation plan builder and slot refusal checks
#      mod_registry  kind and source name lookup
#      fm1_edit      editor actions (setup and UI)
SIZE_COLD := c/host/mod_script c/seq/seq_cmd mod/mod/mod_plan mod/mod/mod_registry sim/src/fm1_edit
$(foreach v,SIM_CFLAGS SEQ_CFLAGS MOD_CFLAGS STATE_CFLAGS ARP_CFLAGS COMMON,\
  $(foreach o,$(SIZE_COLD),$(eval $$(BUILD)/$(o).o: $(v) += $(COLDOPT))))
