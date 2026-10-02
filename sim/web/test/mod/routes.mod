# A parity scenario's modulation (docs/16 MG3; fm1-render --mod format,
# engines/host/mod_script.h): cables into every kind of sink at once, the
# sound, both effects, HOST PITCH and AMP; a chain of three modules (ENV2
# into LFO2's rate, LFO2 into CHANCE's gate); a gate cable at 70 %; a VIA
# and a curve; then an edit at 0.5 s and a cable switched off at 0.8 s.
seed 7
rack default
set 1 rate=0.62 shape=triangle
set 2 rate=0.45 shape=square width=0.3
set 3 attack=0.15 decay=0.35 sustain=0.4 release=0.3
set 4 attack=0.05 decay=0.2 sustain=0 mode=trigger
set 5 mode=smooth rate=0.7
slot 1 key > env3:gate amt=100
slot 2 trig > env4:gate amt=70
slot 3 lfo1 > snd:Timbre amt=35
slot 4 env3 > snd:Morph amt=-40 curve=square
slot 5 lfo2 > fx1:Mix amt=30 pol=uni
slot 6 chance5.smth > fx2:Fdbk amt=25
slot 7 lfo1 > host:pitch amt=1 via=env3
slot 8 env3 > host:amp amt=-30
slot 9 env4 > lfo2.rate amt=40
slot 10 lfo2.wrap > chance5:trig amt=100
@22059 slot 3 lfo1 > snd:Timbre amt=60 ofs=-10 curve=s
@35294 slot 8 env3 > host:amp amt=-30 off
