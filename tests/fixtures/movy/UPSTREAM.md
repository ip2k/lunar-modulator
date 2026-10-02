# Movy's set fixtures

Three `movy1` sets from [schwung-movy](https://github.com/DimaDake/schwung-movy)
by megadake, MIT (`LICENSE` here is its notice), copied unmodified at commit
`9190e79a2f461e71d2bf0a9fa77042011945021e` and renamed `.movy1` (upstream calls
them `seq-state.json`; they are `movy1` text):

| Here | Upstream path | Git blob |
| --- | --- | --- |
| `movy-chains.movy1` | `browser-test/fixtures/old-sets/movy-chains/seq-state.json` | `77d02936232e3b3f6bf4201c4247adb8dfea3cbd` |
| `schwung-tracks.movy1` | `browser-test/fixtures/old-sets/schwung-tracks/seq-state.json` | `28040fe2da0a052128420ab21b55ab5ef9b825ff` |
| `device-set.movy1` | `scripts/fixtures/device-set/seq-state.json` | `651580d2b4a83634764e205c0247338dd0a51d04` |

`tests/test_seq_core.py` imports each into the sequencer core in compat mode and
checks the export against it (docs/13 §7).
