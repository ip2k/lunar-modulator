# mi-fx: Plate, Ensemble and Diffuse, audio effects from Mutable Instruments
# code (engines/src/mi_fx.cc, notes in engines/mi-fx.md). The vendored effects
# are header-only; Ensemble's sine table comes from plaits/resources.cc, which
# the main Makefile already builds.
OUR_SRC += src/mi_fx.cc
