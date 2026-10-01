# mk/ref-plaits.mk -- fm1-ref-plaits: upstream plaits::Voice, unmodified, as
# the module's firmware drives it, plus the comparison metrics the reference
# tests assert (engines/reference-plaits.md, tests/test_engines_reference_plaits.py).
#
# The tool links Voice with all 24 of its engines, so it needs two vendored
# files fm1-render does not build: plaits/dsp/voice.cc and Plaits' own
# SpeechEngine (plaits/dsp/engine/speech_engine.cc; Macro Heavy runs its own
# adaptation). They are compiled here, with the vendored-code flags, and
# linked into this binary only: TP_SRC, and so fm1-render, is left alone.

# This fragment adds a prerequisite to `all` before the main Makefile's first
# rule; keep `all` the default goal.
.DEFAULT_GOAL := all

REF_PLAITS_TP := \
  plaits/dsp/voice.cc \
  plaits/dsp/engine/speech_engine.cc \
  plaits/dsp/engine/virtual_analog_engine.cc \
  plaits/dsp/engine/waveshaping_engine.cc \
  plaits/dsp/engine/fm_engine.cc \
  plaits/dsp/engine/grain_engine.cc \
  plaits/dsp/engine/additive_engine.cc \
  plaits/dsp/engine/wavetable_engine.cc \
  plaits/dsp/engine/chord_engine.cc \
  plaits/dsp/engine/swarm_engine.cc \
  plaits/dsp/engine/noise_engine.cc \
  plaits/dsp/engine/particle_engine.cc \
  plaits/dsp/engine/string_engine.cc \
  plaits/dsp/engine/modal_engine.cc \
  plaits/dsp/engine/bass_drum_engine.cc \
  plaits/dsp/engine/snare_drum_engine.cc \
  plaits/dsp/engine/hi_hat_engine.cc \
  plaits/dsp/engine2/virtual_analog_vcf_engine.cc \
  plaits/dsp/engine2/phase_distortion_engine.cc \
  plaits/dsp/engine2/six_op_engine.cc \
  plaits/dsp/engine2/wave_terrain_engine.cc \
  plaits/dsp/engine2/string_machine_engine.cc \
  plaits/dsp/engine2/chiptune_engine.cc \
  plaits/dsp/chords/chord_bank.cc \
  plaits/dsp/fm/algorithms.cc \
  plaits/dsp/fm/dx_units.cc \
  plaits/dsp/physical_modelling/modal_voice.cc \
  plaits/dsp/physical_modelling/resonator.cc \
  plaits/dsp/physical_modelling/string.cc \
  plaits/dsp/physical_modelling/string_voice.cc \
  plaits/dsp/speech/lpc_speech_synth.cc \
  plaits/dsp/speech/lpc_speech_synth_controller.cc \
  plaits/dsp/speech/lpc_speech_synth_phonemes.cc \
  plaits/dsp/speech/lpc_speech_synth_words.cc \
  plaits/dsp/speech/naive_speech_synth.cc \
  plaits/dsp/speech/sam_speech_synth.cc \
  plaits/resources.cc \
  stmlib/dsp/units.cc \
  stmlib/dsp/atan.cc \
  stmlib/utils/random.cc

# voice.cc includes plaits/user_data.h, whose TEST build calls printf without
# including <cstdio>. macOS's headers happen to pull it in; libstdc++'s do not
# (GCC and clang on Linux). The vendored file stays as it is.
$(BUILD)/tp/plaits/dsp/voice.o: TP_DIALECT += -include cstdio

REF_PLAITS_OBJ := $(BUILD)/our/test/ref_plaits.o \
                  $(patsubst %.cc,$(BUILD)/tp/%.o,$(REF_PLAITS_TP))

all: $(BUILD)/fm1-ref-plaits

$(BUILD)/fm1-ref-plaits: $(REF_PLAITS_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm

# Header dependencies for the objects only this binary uses.
-include $(REF_PLAITS_OBJ:.o=.d)
