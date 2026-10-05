# A parity scenario's modulation over several sound units (docs/16 MG3;
# fm1-render --mod format, engines/host/mod_script.h): cables into every
# kind of unit at once, sound unit 1 (snd), sound units 2 and 4 (snd2,
# snd4), an insert on each of sound units 1, 2 and 4 (sndK.fxJ), both of
# sound unit 2's, the master slot (fx1) and HOST AMP; the default rack's
# envelopes restarted by the notes on any sound unit (RTRG); then an edit
# at 0.5 s and a cable switched off at 0.8 s.
seed 11
rack default
set 1 rate=0.62 shape=triangle
set 2 rate=0.45 shape=square width=0.3
set 3 attack=0.12 decay=0.3 sustain=0.4 release=0.3
set 4 attack=0.05 decay=0.2 sustain=0.2
mod 6 lfo rate=0.72
mod 7 chance rate=0.6
slot 3 lfo1 > snd:Timbre amt=35
slot 4 lfo2 > snd2:Color amt=-40
slot 5 env3 > snd4:Brightness amt=30
slot 6 lfo6 > snd1.fx1:Bits amt=25
slot 7 chance5 > snd2.fx1:Mix amt=50
slot 8 lfo1 > snd2.fx2:Fold amt=45 pol=uni
slot 9 env4 > fx1:Mix amt=-30
slot 10 lfo6 > host:amp amt=-15 pol=uni
slot 11 chance7.smth > snd4.fx1:Mix amt=40
@22059 slot 4 lfo2 > snd2:Color amt=60 curve=s
@35294 slot 7 chance5 > snd2.fx1:Mix amt=50 off
