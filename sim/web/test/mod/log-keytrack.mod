# Engine API v3's LOG law under modulation (docs/16 §2.3; fm1-render --mod
# format, engines/host/mod_script.h): NOTE at +100 % into the Filter's
# Cutoff keytracks it exactly (the octave rule), an LFO moves Cutoff and
# Echo's Time in octaves, and the scenario's knob turn at 0.5 s moves
# Cutoff's base under the routes (rule M1).
seed 11
rack default
set 1 rate=0.55 shape=triangle
slot 1 note > fx1:Cutoff amt=100
slot 2 lfo1 > fx1:Cutoff amt=25
slot 3 lfo1 > fx2:Time amt=-15
