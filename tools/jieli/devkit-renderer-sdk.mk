# Included by the prepared private SDK board Makefile before its link rules.
# Reuse the engine/app build lists and flags; do not maintain a second DSP list.
LUNAR_ROOT := $(abspath ../../../../../lunar-source)
LUNAR_BUILD := $(abspath ../../../../../lunar-build)
LUNAR_INCLUDES := $(foreach i,$(filter -I%,$(INCLUDES)),-I$(abspath $(patsubst -I%,%,$(i))))
LUNAR_EXTRA := $(filter-out -Oz -g,$(CFLAGS)) $(DEFINES) $(LUNAR_INCLUDES) \
  -DFM1_APP_EXTERNAL_ARENAS=1 -fno-data-sections -ffp-contract=off
LUNAR_MAKE = $(MAKE) --no-print-directory -s -C $(LUNAR_ROOT)/engines \
  -f Makefile -f $(LUNAR_ROOT)/sim/web/mk/sim.mk -f $(LUNAR_ROOT)/tools/jieli/renderer.mk \
  SIM=$(LUNAR_ROOT)/sim/web BUILD=$(LUNAR_BUILD) \
  FM1_GPL_MODS=0 FM1_DX7_SINE=msfa FM1_MODULES=dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance \
  CC="$(CC)" CXX="$(CXX)" OPT=-O2 EXTRA="$(LUNAR_EXTRA)"
LUNAR_OBJS := $(shell $(LUNAR_MAKE) print-devkit-renderer-objs)
ifeq ($(strip $(LUNAR_OBJS)),)
$(error Could not obtain shared-renderer objects; refusing SDK link)
endif
OBJS += $(LUNAR_OBJS)
.PHONY: lunar-renderer-build
lunar-renderer-build:
	+$(LUNAR_MAKE) -j4 $(LUNAR_OBJS)
# The outer SDK Makefile lists these files as link prerequisites too. Delegate
# their dependency graph once to the nested build before checking each output.
$(LUNAR_OBJS): lunar-renderer-build
	@test -f "$@"
# Always relink after checking the nested source dependencies. The SDK's link
# recipe uses OBJS explicitly, so this phony prerequisite is never a link input.
$(OUT_ELF): lunar-renderer-build
