# A parity scenario's modulation (owner's decision, 2026-10-06): a cable at
# zero amount into EQ's Low Gain (FX1) is a cable all the same, so EQ never
# idles (FM1_PARAM_DRIVEN, engines/include/fm1_engine.h) and the short Low
# Gain move at 3 s is heard; Master Sat (FX2) has no cable, idles from 2 s,
# and its short Mix move at 3 s is lost in its warm-up, as before.
rack default
slot 1 lfo1 > fx1:LoGain amt=0
