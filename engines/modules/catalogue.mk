# engines/modules/catalogue.mk -- every module the tree can build, and the
# build-time module list (FM1_MODULES) that picks which of them a build has.
# Read by engines/Makefile after the GPL switch and before the fragments.
# DEVELOPERS.md, "Choosing the modules", says how to use it.
#
#   make -C engines                          # every module (FM1_MODULES=all)
#   make -C engines FM1_MODULES=default      # modules/default.list, the FM-1's proposed list
#   make -C engines FM1_MODULES=my.list      # a list file (a path from engines/, or absolute)
#   make -C engines FM1_MODULES=macro,plate,arp,lfo,env   # the modules named
#
# A module is a sound engine, an audio effect, a MIDI effect or a modulation
# kind, named by its id. The list sets which are in the registries
# (src/registry.cc, midi_fx/registry.c, mod/mod_registry.c) through the
# generated header $(BUILD)/gen/fm1_modules.h (FM1_WITH_<ID> 0 or 1), and so
# in fm1-render --list, the metadata export (--meta, meta.json, meta_id) and
# the virtual FM-1's catalogue; the modules left out are listed there as
# known ids with the reason "list". The GPL switch comes first: with
# FM1_GPL_MODS=0 a GPL module is never in the build, listed or not.
#
# The products, fm1-render, the virtual FM-1's native and WebAssembly builds
# and the JieLi compile check's object list (tools/jieli/objects.mk), link or
# compile only the objects of the modules chosen, plus the core (everything
# no module owns): FM1_OBJ.<id> below names the objects each module needs
# beyond the core, relative to $(BUILD). An object several modules need is
# named under each of them and kept while any of them is chosen.
# tests/test_module_list.py checks these lists against the objects' symbol
# references, so a module that comes to need another object fails there
# first. Desktop test tools still link every object, so they build whatever
# the list (their registries list only the chosen modules).
#
# Adding a module: its id under its kind below, FM1_GPL_IDS if it is GPL, its
# objects as FM1_OBJ.<id>, and its registry line as FM1_IF(FM1_WITH_<ID>, ...).
# MIT licence, like the rest of this repository.

FM1_SOUND_IDS := macro shapes macro-heavy sixop dx7 sw-sophie drums acid-bass comet crater \
                 drawbar trio phase-bend test-sine
FM1_AUDIO_FX_IDS := plate ensemble diffuse sw-psxverb crush fold drive echo filter comb comp \
                    limit djfilter tilt sat isolator eq room hall gate squash shaper repeat test-gain \
                    test-ext
FM1_MIDI_FX_IDS := arp acid-gen
FM1_MOD_IDS := lfo env chance function bounce register coin divide burst slew quantize \
               compare logic calc mix resonator
FM1_GPL_IDS := acid-bass comet crater drawbar trio phase-bend acid-gen

# ---- What each module needs beyond the core (relative to $(BUILD)) ----------------------

FM1_PLAITS_BASE := tp/plaits/resources.o tp/stmlib/dsp/units.o tp/stmlib/utils/random.o
FM1_OBJ.macro := our/src/mi_macro.o $(FM1_PLAITS_BASE) tp/plaits/dsp/chords/chord_bank.o \
  $(patsubst %,tp/plaits/dsp/engine/%_engine.o,virtual_analog waveshaping fm wavetable) \
  $(patsubst %,tp/plaits/dsp/engine2/%_engine.o,virtual_analog_vcf phase_distortion wave_terrain chiptune)
FM1_OBJ.shapes := our/src/mi_shapes.o tp/stmlib/utils/random.o \
  $(patsubst %,tp/braids/%.o,macro_oscillator analog_oscillator digital_oscillator resources)
FM1_OBJ.macro-heavy := our/src/mi_macro_heavy.o $(FM1_PLAITS_BASE) tp/plaits/dsp/chords/chord_bank.o \
  $(patsubst %,tp/plaits/dsp/engine/%_engine.o,additive bass_drum chord grain hi_hat modal noise \
    particle snare_drum string swarm) \
  tp/plaits/dsp/engine2/string_machine_engine.o \
  $(patsubst %,tp/plaits/dsp/physical_modelling/%.o,modal_voice resonator string string_voice) \
  $(patsubst %,tp/plaits/dsp/speech/%.o,lpc_speech_synth lpc_speech_synth_controller \
    lpc_speech_synth_phonemes lpc_speech_synth_words naive_speech_synth sam_speech_synth)
FM1_OBJ.sixop := our/src/mi_sixop.o $(FM1_PLAITS_BASE) tp/plaits/dsp/engine2/six_op_engine.o \
  tp/plaits/dsp/fm/algorithms.o tp/plaits/dsp/fm/dx_units.o
# FM6's voice format (dx7_voice.o: VCED fields, SysEx in and out, with msfa's
# patch.o, which packs and unpacks a voice) is core:
# files, the metadata export and the desktop host read it without the engine.
FM1_OBJ.dx7 := $(patsubst %,our/src/%.o,msfa_dx7 dx7_loop msfa_tables msfa_rom) \
  $(patsubst %,tp/msfa/%.o,dx7note env fm_core fm_op_kernel freqlut lfo pitchenv)
FM1_OBJ.sw-sophie := our/src/sw_sophie.o our/src/schwung_shim.o sw/sophie/sophie.o
FM1_OBJ.drums := our/src/drums.o $(FM1_PLAITS_BASE)
FM1_OBJ.acid-bass := our/src/acid_bass.o gpl/fm1-x0x/dsp/bass303.o
FM1_OBJ.comet := our/src/comet_kit.o gpl/fm1-x0x/dsp/drum909.o
FM1_OBJ.crater := our/src/crater_kit.o gpl/fm1-x0x/dsp/drum808.o
# Felucca's three engines share one shim and one bridge.
FM1_OBJ.drawbar := our/src/felucca_shim.o gpl/felucca/felucca_bridge.o
FM1_OBJ.trio := $(FM1_OBJ.drawbar)
FM1_OBJ.phase-bend := $(FM1_OBJ.drawbar)
FM1_OBJ.test-sine := our/src/test_sine.o

# Plate, Ensemble and Diffuse share one file (Clouds' and Rings' effects).
FM1_OBJ.plate := our/src/mi_fx.o tp/plaits/resources.o
FM1_OBJ.ensemble := $(FM1_OBJ.plate)
FM1_OBJ.diffuse := $(FM1_OBJ.plate)
FM1_OBJ.sw-psxverb := our/src/sw_psxverb.o our/src/schwung_shim.o sw/psxverb/psxverb.o
FM1_OBJ.crush := our/src/fx_crush.o
FM1_OBJ.fold := our/src/fx_fold.o
FM1_OBJ.drive := our/src/fx_drive.o
FM1_OBJ.echo := our/src/fx_echo.o
FM1_OBJ.filter := our/src/fx_filter.o
FM1_OBJ.comb := our/src/fx_comb.o
FM1_OBJ.comp := our/src/fx_comp.o
FM1_OBJ.limit := our/src/fx_limit.o
FM1_OBJ.djfilter := our/src/fx_djfilter.o
FM1_OBJ.tilt := our/src/fx_tilt.o
FM1_OBJ.sat := our/src/fx_sat.o
FM1_OBJ.isolator := our/src/fx_isolator.o
FM1_OBJ.eq := our/src/fx_eq.o
FM1_OBJ.room := our/src/fx_room.o
FM1_OBJ.hall := our/src/fx_hall.o
FM1_OBJ.gate := our/src/fx_gate.o
FM1_OBJ.squash := our/src/fx_squash.o
FM1_OBJ.shaper := our/src/fx_shaper.o
FM1_OBJ.repeat := our/src/fx_repeat.o
FM1_OBJ.test-gain := our/src/test_gain.o
FM1_OBJ.test-ext := our/src/test_ext.o

# The arp: its engine. Its rhythm tables (arp_rhythm.o) serve the MIDI-effect
# stage (fm1_arp.o), which is core.
FM1_OBJ.arp := midi_fx/arp_engine.o
FM1_OBJ.acid-gen := midi_fx/acid_gen.o gpl/fm1-x0x/seq/tb3po.o

$(foreach k,$(FM1_MOD_IDS),$(eval FM1_OBJ.$(k) := mod/mod/kinds/mod_$(k).o))

# ---- The list ------------------------------------------------------------------------------

FM1_MODULES ?= all
# A literal '#' for the text below: GNU make 4.3 and later keep a backslash
# before '#' inside a function call, 3.81 (macOS's) drops it; a variable
# reads the same in both.
fm1_hash := \#
FM1_CATALOGUE_IDS := $(FM1_SOUND_IDS) $(FM1_AUDIO_FX_IDS) $(FM1_MIDI_FX_IDS) $(FM1_MOD_IDS)
# What this build can have: the GPL switch decides first.
FM1_AVAILABLE_IDS := $(if $(filter 1,$(FM1_GPL_MODS)),$(FM1_CATALOGUE_IDS),\
                       $(filter-out $(FM1_GPL_IDS),$(FM1_CATALOGUE_IDS)))
fm1_mod_comma := ,
FM1_MODULES_SPEC := $(strip $(subst $(fm1_mod_comma), ,$(FM1_MODULES)))
ifeq ($(FM1_MODULES_SPEC),all)
FM1_MODULES_NAME := all
FM1_MODULES_WANT := $(FM1_CATALOGUE_IDS)
else ifneq ($(and $(filter-out %.list,$(FM1_MODULES_SPEC)),$(wildcard modules/$(FM1_MODULES_SPEC).list)),)
FM1_MODULES_NAME := $(FM1_MODULES_SPEC)
FM1_MODULES_WANT := $(shell sed -e 's/$(fm1_hash).*//' 'modules/$(FM1_MODULES_SPEC).list')
else ifneq ($(filter %.list,$(lastword $(FM1_MODULES_SPEC))),)
ifeq ($(wildcard $(FM1_MODULES_SPEC)),)
$(error FM1_MODULES: no list file "$(FM1_MODULES_SPEC)" (a path from engines/, or absolute))
endif
FM1_MODULES_NAME := $(basename $(notdir $(FM1_MODULES_SPEC)))
FM1_MODULES_WANT := $(shell sed -e 's/$(fm1_hash).*//' '$(FM1_MODULES_SPEC)')
else
FM1_MODULES_NAME := custom
FM1_MODULES_WANT := $(FM1_MODULES_SPEC)
endif
FM1_MODULES_UNKNOWN := $(filter-out $(FM1_CATALOGUE_IDS),$(FM1_MODULES_WANT))
ifneq ($(FM1_MODULES_UNKNOWN),)
$(error FM1_MODULES: no module "$(firstword $(FM1_MODULES_UNKNOWN))" (engines/modules/catalogue.mk lists them))
endif
FM1_MODULE_IDS := $(filter $(FM1_MODULES_WANT),$(FM1_AVAILABLE_IDS))
ifeq ($(filter $(FM1_SOUND_IDS),$(FM1_MODULE_IDS)),)
$(error FM1_MODULES: the list "$(FM1_MODULES_NAME)" has no sound engine this build can have)
endif
FM1_LEFT_OUT_IDS := $(filter-out $(FM1_MODULE_IDS),$(FM1_AVAILABLE_IDS))

# The objects the products leave out: those of the modules left out that no
# chosen module needs. (A GPL module's objects are not even defined with the
# switch off.)
FM1_KEEP_OBJ := $(sort $(foreach m,$(FM1_MODULE_IDS),$(FM1_OBJ.$(m))))
FM1_DROP_OBJ := $(addprefix $(BUILD)/,$(filter-out $(FM1_KEEP_OBJ),\
                  $(sort $(foreach m,$(FM1_LEFT_OUT_IDS),$(FM1_OBJ.$(m))))))

fm1_what = $(if $(filter $(1),$(FM1_SOUND_IDS)),sound,$(if $(filter $(1),$(FM1_AUDIO_FX_IDS)),audio_fx,$(if \
  $(filter $(1),$(FM1_MIDI_FX_IDS)),midi_fx,mod)))

# ---- The generated header, rewritten only when the list changes (as fm1_gpl_mods.h) ------

FM1_MODULE_MACROS := $(shell printf '%s\n' $(FM1_CATALOGUE_IDS) | tr 'a-z-' 'A-Z_')
FM1_MODULES_LINES := \
  '/* fm1_modules.h -- written by engines/modules/catalogue.mk: the module list (FM1_MODULES) */' \
  '$(fm1_hash)define FM1_MODULES_NAME "$(FM1_MODULES_NAME)"' \
  $(foreach p,$(join $(addsuffix :,$(FM1_CATALOGUE_IDS)),$(FM1_MODULE_MACROS)),\
    '$(fm1_hash)define FM1_WITH_$(word 2,$(subst :, ,$(p))) $(if $(filter $(word 1,$(subst :, ,$(p))),$(FM1_MODULE_IDS)),1,0)') \
  '/* The modules this build can have but its list leaves out, as fm1_known_id_t rows */' \
  '$(fm1_hash)define FM1_LEFT_OUT_ROWS $(foreach m,$(FM1_LEFT_OUT_IDS),{ "$(m)", "$(call fm1_what,$(m))", "list", 0 },)' \
  '/* An entry of a registry or licence table and its comma, kept when c is 1:' \
  '   FM1_IF(FM1_WITH_X, entry) */' \
  '$(fm1_hash)define FM1_IF(c, ...) FM1_IF_(c, __VA_ARGS__)' '$(fm1_hash)define FM1_IF_(c, ...) FM1_IF_$(fm1_hash)$(fm1_hash)c(__VA_ARGS__)' \
  '$(fm1_hash)define FM1_IF_0(...)' '$(fm1_hash)define FM1_IF_1(...) __VA_ARGS__,'
# Each make writes its own temporary file and renames it into place, so makes
# run side by side (the JieLi check runs one per object) never read a header
# another is still writing.
$(shell mkdir -p '$(GPL_GEN)' && h='$(GPL_GEN)/fm1_modules.h' && t="$$h.$$$$" && \
  printf '%s\n' $(FM1_MODULES_LINES) > "$$t" && \
  { if cmp -s "$$t" "$$h"; then rm -f "$$t"; else \
    if [ -f "$$h" ]; then sleep 1; fi; mv -f "$$t" "$$h"; fi; })

# This file defines a rule before the main Makefile's first one; keep `all`
# the default goal.
.DEFAULT_GOAL := all
.PHONY: print-modules
# One line per module this build can have: id, kind, 1 if chosen, then its
# objects (tools/jieli/analyze.py's flash per module; tests/test_module_list.py).
print-modules:
	@$(foreach m,$(FM1_AVAILABLE_IDS),printf '%s\n' '$(m) $(call fm1_what,$(m)) $(if $(filter $(m),$(FM1_MODULE_IDS)),1,0) $(FM1_OBJ.$(m))';)
	@printf '%s\n' 'list $(FM1_MODULES_NAME)'
