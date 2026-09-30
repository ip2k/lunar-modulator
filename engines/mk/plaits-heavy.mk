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
