# A parity scenario's per-voice modulation (docs/16 MG9; fm1-render --mod
# format, engines/host/mod_script.h): each note on sound unit 1 its own
# Envelope into Timbre (ENV3 per voice, its attack shortened by velocity
# per voice) and a random detune of its own (RAND per voice into the
# note's pitch); sound unit 2's notes an LFO each in trig mode into Color
# per voice; sound unit 2's notes alone gating ENV4 (S2RTRG), which bends
# sound unit 2 (PITCH2); an LFO on the current sound's pitch (PITCHC),
# moved to sound unit 2 at 0.6 s; an edit at 0.5 s and a per-voice cable
# switched off at 0.9 s. Sound unit 1's chord re-strikes a held key.
seed 13
rack default
set 1 rate=0.7 shape=triangle mode=trig
set 2 rate=0.55 shape=square
set 3 attack=0.35 decay=0.4 sustain=0.3 release=0.35
set 4 attack=0.1 decay=0.25 sustain=0.2
slot 3 env3 > snd:Timbre amt=55 voice
slot 4 vel > env3:attack amt=-30 voice
slot 5 rand > host:pitch amt=0.4 voice
slot 6 lfo1 > snd2:Color amt=-45 voice
slot 7 s2rtrg > env4:gate amt=100
slot 8 env4 > host:pitch2 amt=3
slot 9 lfo2 > host:pitchc amt=1
@22059 slot 3 env3 > snd:Timbre amt=70 curve=s voice
@26471 current 2
@39706 slot 6 lfo1 > snd2:Color amt=-45 voice off
