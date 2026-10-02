# plaits-heavy.mk -- "Macro Heavy" (the heavy Plaits engines) and "Six-Op FM"
# (Plaits' six-operator engine). See engines/plaits-heavy.md.
#
# Third-party sources are appended only when no other fragment (or the base
# Makefile) lists them already, so two streams needing the same Plaits file do
# not link it twice. plaits/dsp/engine/speech_engine.cc is not listed: the
# speech model runs our adaptation of it (SpeechVoiceEngine, one word bank
# shared by all voices).

OUR_SRC += src/mi_macro_heavy.cc src/mi_sixop.cc

PLAITS_HEAVY_TP := \
  plaits/dsp/engine2/string_machine_engine.cc \
  plaits/dsp/engine/chord_engine.cc \
  plaits/dsp/chords/chord_bank.cc \
  plaits/dsp/speech/lpc_speech_synth.cc \
  plaits/dsp/speech/lpc_speech_synth_controller.cc \
  plaits/dsp/speech/lpc_speech_synth_phonemes.cc \
  plaits/dsp/speech/lpc_speech_synth_words.cc \
  plaits/dsp/speech/naive_speech_synth.cc \
  plaits/dsp/speech/sam_speech_synth.cc \
  plaits/dsp/engine/grain_engine.cc \
  plaits/dsp/engine/additive_engine.cc \
  plaits/dsp/engine/swarm_engine.cc \
  plaits/dsp/engine/noise_engine.cc \
  plaits/dsp/engine/particle_engine.cc \
  plaits/dsp/engine/string_engine.cc \
  plaits/dsp/physical_modelling/string.cc \
  plaits/dsp/physical_modelling/string_voice.cc \
  plaits/dsp/engine/modal_engine.cc \
  plaits/dsp/physical_modelling/modal_voice.cc \
  plaits/dsp/physical_modelling/resonator.cc \
  plaits/dsp/engine/bass_drum_engine.cc \
  plaits/dsp/engine/snare_drum_engine.cc \
  plaits/dsp/engine/hi_hat_engine.cc \
  plaits/dsp/engine2/six_op_engine.cc \
  plaits/dsp/fm/algorithms.cc \
  plaits/dsp/fm/dx_units.cc \
  plaits/resources.cc \
  stmlib/dsp/units.cc \
  stmlib/utils/random.cc

TP_SRC += $(filter-out $(TP_SRC),$(PLAITS_HEAVY_TP))

# fm1-render-original-names: fm1-render with Six-Op FM built with
# -DFM1_SIXOP_ORIGINAL_NAMES, so its Patch list shows the names stored in the
# patch data rather than the public ones (plaits-heavy.md, "The patch data").
# Built with everything else, so CI's 32-bit and sanitizer builds make it with
# their own flags; it costs one more compile of mi_sixop.cc and a link. The
# tests check that it lists the stored names and renders the same bytes.
.DEFAULT_GOAL := all

SIXOP_ORIGINAL_NAMES_OBJ := $(BUILD)/original-names/src/mi_sixop.o

all: $(BUILD)/fm1-render-original-names

# fm1-render as a prerequisite builds every object it links; the link line is
# expanded when it runs, after the main Makefile has set RENDER_OBJ.
$(BUILD)/fm1-render-original-names: $(SIXOP_ORIGINAL_NAMES_OBJ) $(BUILD)/fm1-render
	$(CXX) $(OPT) $(EXTRA) -o $@ $(SIXOP_ORIGINAL_NAMES_OBJ) \
	  $(filter-out $(BUILD)/our/src/mi_sixop.o,$(RENDER_OBJ)) -lm

$(SIXOP_ORIGINAL_NAMES_OBJ): src/mi_sixop.cc
	@mkdir -p $(dir $@)
	$(CXX) $(COMMON) $(OUR_WARN) -DFM1_SIXOP_ORIGINAL_NAMES -c $< -o $@

-include $(SIXOP_ORIGINAL_NAMES_OBJ:.o=.d)
