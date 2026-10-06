# tools/jieli/objects.mk -- read after engines/Makefile and sim/web/mk/sim.mk
# so the compile check takes its object list from the build itself:
#
#   make -C engines -f Makefile -f ../sim/web/mk/sim.mk -f ../tools/jieli/objects.mk \
#        SIM=<abs sim/web> BUILD=<abs dir> print-objs
#
# Everything a firmware would link: our engines and effects, the vendored
# Mutable, Schwung and msfa code (MSFA_OBJ, mk/msfa.mk), the sequencer core, the modulation primitives
# and runtime (MOD_OBJ, MODC_OBJ: mk/mod.mk), the simulator's app layer, and
# the GPL modules' C objects (GPL_OBJ) while the GPL switch is on
# (FM1_GPL_MODS, engines/Makefile: on by default, so the check compiles them;
# compile-check.sh passes FM1_GPL_MODS=0 through for the MIT/BSD build).
# Left out: the desktop host (host/render.cc, seq_script.c, seq_tool.c,
# mod_script.c), the reference renderers and tests, which read files and
# have a main().
# fm1_web.c (the WebAssembly glue) is listed so its compile is checked too.
# MIT licence, like the rest of this repository.

JIELI_OBJ := $(filter-out $(BUILD)/our/host/render.o,$(OUR_OBJ)) $(TP_OBJ) $(SW_OBJ) $(MSFA_OBJ) \
             $(SEQ_OBJ) $(MOD_OBJ) $(MODC_OBJ) $(SIM_APP_OBJ) $(BUILD)/sim/src/fm1_web.o $(GPL_OBJ)

.PHONY: print-objs
print-objs:
	@printf '%s\n' $(JIELI_OBJ)
