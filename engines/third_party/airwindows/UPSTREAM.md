# Airwindows — Squash's Types and the Limiter's Round mode

| | |
| --- | --- |
| Upstream | https://github.com/airwindows/airwindows at `e718c9bcfcdd736deeddb08bffe6bce2aa8e0eea` (2026-10-04), `plugins/LinuxVST/src/<name>/<name>Proc.cpp` and `LICENSE` |
| Author | Chris Johnson (Airwindows) |
| Licence | MIT: `LICENSE` here is upstream's, byte for byte ("Copyright (c) 2018 Chris Johnson"); each source file says "Copyright (c) 2016 airwindows, Airwindows uses the MIT license" |
| Vendored | **No upstream file is vendored.** The loops were read and ported into this repository's own files, which carry the notice and point here |
| Used by | `engines/src/fx_squash.cc` (Squash: Snap after Pop3, Mu after Pressure4, Split after ButterComp2) and `engines/src/fx_limit.cc` (the Limiter's Round mode, after ClipOnly2). Owner decisions of 2026-10-05; notes/2026-10-02-filters-dynamics-options.md §3 and decision 9 |
| Oracle | `oracle/airwindows_oracle.cc`: the four loops in double, copied with only the changes its header lists, for reference renders. Not built by `engines/Makefile` and never run on a developer's machine: `oracle/run-on-aeon.sh` builds and runs it in the `gcc:12` container on a Docker host and writes `tests/fixtures/squash-oracle.json` (`oracle/make_fixture.py`) |

The files read, by git blob and sha256:

| File | Blob | sha256 | Ported into |
| --- | --- | --- | --- |
| `Pop3/Pop3Proc.cpp` | `3d95c2fe2e6e62c56c4ad1cddeccf71ac84b0e90` | `fad69274bf57213c913e2f7dc65d255ef226cd1f1cf52deb7cc0ee74cfaedd0a` | `fx_squash.cc` `SnapFrame` |
| `Pressure4/Pressure4Proc.cpp` | `1111cce8ea88fb6a6341c3c77ce15216a1b0244e` | `0ce7634839ac59e0b469cb4fd7c786ae1d403138d553e7e06776aab58562409e` | `fx_squash.cc` `MuFrame` |
| `ButterComp2/ButterComp2Proc.cpp` | `418ac65c8f01bc9597e45999645e7dce68ca90ed` | `49ba9d4948f939f00b7c8875e11b4140a76bcf7b3f15f6277e6ef8907a05f298` | `fx_squash.cc` `SplitFrame` |
| `ClipOnly2/ClipOnly2Proc.cpp` | `f5d765a0dd25a4875ca2b70201d2d39374df1329` | `8bfe5b21c1e79643965dcaede54e213eb43795da67371cf9720dad6dc172c3e0` | `fx_limit.cc` `RoundStep` |
| `LICENSE` | | `b4f5719b00ba3fecf8c0ce651e843651bd80f08a10cf4cf1f00e673a5bcaf23b` | `LICENSE` here |

The plug-ins' parameter tables (`<name>.cpp`) were read for their knobs'
names, ranges and defaults.

## What the ports change

The porting rules of the filters note (§3), and what each port records in
its own header:

- Single precision, no libm: `sin` a Taylor polynomial on 0..π/2, `pow` as
  multiplications or `fm1_exp2f`, `sqrt` from the float's bits and Newton
  steps. Floating-point contraction off.
- The denormal dither (`fpd`) on input and output, and ButterComp2's "live
  air" residue (function-static, shared by every instance), are removed:
  silence in gives exact silence out, states flush to 0 under 1e-20.
- Knobs in units where the plug-in's 0..1 knob maps onto a time or a level,
  with the same arithmetic underneath; Output and Mix added for every Type.
- Pop3's stereo link is kept as the lower state and the gap (fx_squash.cc
  explains: as two floats its "pull both" hold never ended).
- Pressure4's steps are written c + (target − c) / n; its 1/threshold lift
  is divided back out after the detector, and its output sine is left out
  (Mu only turns down; Output makes up).
- ButterComp2's targets are held at 0.25 or more (its gains at 16 or less).
- ClipOnly2 is scaled to the Limiter's ceiling, and reads the next frame
  from the Limiter's line instead of giving each frame out a sample late, so
  Round adds no delay; it looks one frame ahead at any rate (upstream's
  spacing grows above 88.2 kHz).

## Re-checking

```bash
make -C engines
FM1_SIM_HOST=user@host engines/third_party/airwindows/oracle/run-on-aeon.sh
python -m pytest tests/test_engines_squash.py
```

The residuals measured on 2026-10-05 are in `engines/README.md`, "Squash".
