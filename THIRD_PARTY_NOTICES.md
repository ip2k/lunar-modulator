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
