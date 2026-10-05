# The virtual FM-1's modulation (fm1-sim-render --log-cmds): its state at
# the start, then every edit at the block it led (fm1-render --mod).
seed 1
mod 1 lfo
mod 2 lfo
mod 3 env
mod 4 env
mod 5 chance
mod 6 none
mod 7 none
mod 8 none
slot 1 rtrg > mod3:Gate amt=100 ofs=0 pol=auto curve=lin
slot 2 rtrg > mod4:Gate amt=100 ofs=0 pol=auto curve=lin
@6656 slot 3 mod1.1 > snd:Timbre amt=40.0024414062 ofs=0 pol=auto curve=lin
@41920 slot 4 mod3.1 > snd:Harm amt=-29.9987792969 ofs=0 pol=auto curve=lin
