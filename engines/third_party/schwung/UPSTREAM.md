# Vendored Schwung plugin ABI headers

| | |
| --- | --- |
| Upstream | https://github.com/charlesvestal/schwung at `70c41718ce189c5c53ae8fc1a17d9b456096eb43` (2026-09-29, host v1.5.0), the commit docs/11 was researched at |
| Author | Charles Vestal |
| Licence | MIT. `LICENSE` is copied whole: the MIT text, then a note on the project's fork provenance (Move Anything by Bobby Digitales) and a pointer to `THIRD_PARTY_LICENSES.md`, which lists other licences for components that are **not** vendored here (the host's libraries). Checked 2026-09-30. GitHub's licence detector reports `NOASSERTION` for the repository because of that trailing note; the licence text itself is MIT |
| Local changes | **None.** Byte-identical to upstream; blob SHAs checked against the GitHub API at the pinned commit on 2026-09-30 |

| File | Upstream path | SHA-256 |
| --- | --- | --- |
| `plugin_api_v1.h` | `src/host/plugin_api_v1.h` | `dc0b9eda0163e9ccf77ec434ca029adbf0276c83dde5d1ac2e754962f88b9a03` |
| `audio_fx_api_v2.h` | `src/host/audio_fx_api_v2.h` | `bd66061432327f354ab51f508038ea1dbbfb751d254dbdad638e0353cd94bc4b` |
| `LICENSE` | `LICENSE` | `52af9df37f1a2a3dadbc0785f8753b8cea7606a236a5dbc82c9abfc92c9844d8` |

`tests/test_engines_schwung.py` recomputes these hashes, so an edit to a
vendored file fails the tests.

## What our code works around

- **`_Static_assert` at the end of `plugin_api_v1.h`.** It pins
  `offsetof(host_api_v1_t, reserved) == 120`, the aarch64 layout that shipped
  Move binaries rely on. It is C11 (g++ does not accept it in C++) and it
  fails with 4-byte pointers, where `reserved` sits at +68. The shim includes
  the headers through `engines/src/schwung_abi.h`, which maps it to C++11
  `static_assert` and applies the condition only when pointers are 8 bytes.
  Upstream candidate: guarding the assertion with `sizeof(void *) == 8` would
  let the header build for 32-bit hosts unchanged.
- **Header drift in modules.** Each module ships its own copy of these
  headers, often older (PSX Verb's `audio_fx_api_v2_t` has no `on_midi`).
  The shim reads only the fields every copy has.

Re-vendoring:

```bash
git clone https://github.com/charlesvestal/schwung reference/schwung
git -C reference/schwung checkout 70c41718ce189c5c53ae8fc1a17d9b456096eb43
cp reference/schwung/LICENSE reference/schwung/src/host/plugin_api_v1.h \
   reference/schwung/src/host/audio_fx_api_v2.h engines/third_party/schwung/
```
