# Synthetic format fixtures

`generate.py` builds source-owned DX7 voices from `tools/dx7_bank.py` and
small independently constructed vendor-container probes. It contains no
factory bank, recording or vendor binary. Run:

```sh
python3 tests/fixtures/workbench/generate.py --out /tmp/workbench-vectors
```

The output directory may exist, but individual files must be new. Project and
timbre probes validate envelopes only; their all-zero semantic payloads are
not playable projects. Sample chunk probes contain SEA5 markers only, not
encoded audio. Large capacity boundaries are generated on demand to avoid
checking meaningless binary padding into Git. See
`notes/workbench/formats.md` for contracts and limitations.

