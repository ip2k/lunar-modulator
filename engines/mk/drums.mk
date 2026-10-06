# drums.mk -- "Drums", a 16-pad kit on MIDI notes 36-51 (engines/src/drums.cc):
# Mutable Instruments Plaits' drum classes (header-only, vendored unmodified
# in third_party/mutable; MIT) and four voices of this repository's own
# (engines/src/drum_voices.h). The Plaits sources the classes need
# (resources.cc for the lookup tables, stmlib's random.cc) are linked
# already for Macro; the simulator's build (sim/web/mk/sim.mk) links the
# engine through OUR_SRC. Tests: tests/test_engine_drums.py.

OUR_SRC += src/drums.cc
