# Credits and notices for `engines/midi_fx/`

The arpeggiator core (`fm1_arp.c`, `arp_rhythm.c`) is this repository's own
C, MIT. It reimplements designs from the three projects below; no upstream
source file is compiled or vendored. Two pieces of Yarns data are carried:
the 22 rhythm masks, regenerated from Yarns' x-o strings, and the Euclidean
patterns, recomputed by a rewrite of Yarns' generator. `arp_rhythm.c` repeats
Yarns' notice for them. Each design source is named, with file, line and
commit, in the comment that opens `fm1_arp.c`. Their notices follow, as
their licences ask. All three licences allow use in the public simulator and
in a shareable FM-1 build (options note 2026-10-01 §6).

## Yarns and stmlib (Emilie Gillet, MIT)

Design: the arpeggiator loop (`yarns/part.cc` 366–446 at
[pichenettes/eurorack 08460a6](https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/yarns/part.cc)),
its clock, gate counter, latch and hold pedal, and stmlib's `NoteStack`
([pichenettes/stmlib e3bd7c9](https://github.com/pichenettes/stmlib/tree/e3bd7c9cc00e4364166f9905c0509b6ffd0535ec/algorithms)).
Data: the rhythm masks and Euclidean patterns of
`yarns/resources/lookup_tables.py`.

```
Copyright 2012-2014 Emilie Gillet.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## MCL (Justin Mammarella, BSD-3-Clause)

Design: the note orders of `ArpSeqTrack::render` and the trig-stepped rate
`ARP_RATE_TRIG`
([jmamma/MCL 693a410](https://github.com/jmamma/MCL/tree/693a410017833a732c24412db5fcce9049e78642/src/mcl/Drivers/Generic/Sequencer),
`ArpSeqTrack.cpp` 122–138 and 174–358, `ArpSeqTrack.h` 12–36).

```
Copyright 2020, Justin Mammarella <jmamma@gmail.com>
                Yatao Li <yatao.li@live.com>
                Manuel Odendahl <wesen@ruinwesen.com>

The following license applies to code, documentation or material
in this repository, created by the above authors.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Super Arp (Handcrafted Media, MIT)

Design: random modifiers that are a pure function of a seed and a step
index, so a loop length makes them repeat
([handcraftedcc/schwung-superarp 6eefd02](https://github.com/handcraftedcc/schwung-superarp/blob/6eefd02af91823e330f7ce86883dc097b634ecc1/src/dsp/superarp.c),
`superarp.c` 244–320 and 1380–1430).

```
MIT License

Copyright (c) 2026 Handcrafted Media

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
