# Third-party notices

## JieLi package format, cipher and chip-key decoding

The decoding algorithms in `tools/fm1_package.py` are adapted from the format
work in [kagaimiq/jl-misctools](https://github.com/kagaimiq/jl-misctools), revision
`0a5b12db0ef38f3042acffbe2452730a37fd2405`. The following notice applies:

MIT License

Copyright (c) 2023 Andrey Grigoryev (kagaimiq)

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

## msfa algorithm table

The inspector imports the reference constants already in
`tools/check_msfa_table.py`; that file identifies the table's origin in Google's
Apache-2.0 music-synthesizer-for-android `fm_core.cc`. This contribution adds no
copy of firmware or synth implementation code. See `docs/04-prior-art.md` for the
existing project's source and license references.

## pi32v2 instruction-format research

The new Python decoder in `tools/fm1_decode.py` consulted the Apache-2.0
instruction-field descriptions in
[kagaimiq/ghidra-jieli](https://github.com/kagaimiq/ghidra-jieli), revision
`b5e60122b6cd3e6b615387035994b8bed0ea1a26`. Its
[license](https://github.com/kagaimiq/ghidra-jieli/blob/b5e60122b6cd3e6b615387035994b8bed0ea1a26/LICENSE)
applies to that reference project. No SLEIGH source or pcode implementation was
copied into this contribution. Field formulas were independently implemented
and checked against locally available vendor disassembly; several reference
decoding defects were corrected during those checks.

The annotated function names and older disassembly in
[AL-255/FM-1-RE](https://github.com/AL-255/FM-1-RE), revision
`95eca8488ac8c3b6f86287b2d3d43678e03e271a`, informed research hypotheses.
The reference project declares WTFPL. Vendor firmware and vendor-generated
listings were used only as local research evidence and are not redistributed
under that declaration. This contribution distributes original analysis,
small instruction-format test vectors, addresses and cryptographic fingerprints;
it contains no firmware image or wholesale proprietary listing.
