# Lunar platform identifier migration

The Dinghy-derived platform now uses `LUNAR_*` for its configuration/identity
macros and `lunar_font.h` / `lunar_font_t` for the generated local font API.
The offline expanded-loader fixture lives at
`firmware/third_party/expanded-loader-offline` and uses
`LUNAR_EXPANDED_OFFLINE_TEST`. Build transforms and direct tests use the same
names. The old generated font and the renamed header are byte-identical after
normalizing only the font type and naming tokens. USB configuration is compiled
from the platform's actual `LUNAR_*` settings in the regression test, which
checks the emitted interface count, descriptor length, and 44.1/48 kHz rates.

The literal OTA marker `FELUCCA-LOADER-1` remains unchanged because it is a
legacy loader signature consumed by the compatibility parser. It is not used
as a product/platform identifier. Dinghy/Felucca/SLOOP source attribution and
license notices are retained. The inventory records the pinned upstream and
new local hashes for each edited vendor-derived file; `UPSTREAM.md` describes
the local adaptations. Historical notes had references to the moved fixture
path corrected while keeping prior-art attribution intact.

Validation on Hera, branch `codex/2026-10-15-lunar-platform-names`:

- `pytest -q tests/test_native_firmware_identity.py tests/test_native_compact_font.py tests/test_expanded_loader_offline.py`: 37 passed.
- `pytest -q tests/test_native_demo_image_controller.py tests/test_native_project_capacity.py tests/test_build_application_probe_save_service.py tests/test_expanded_loader_offline.py tests/test_native_firmware_identity.py tests/test_native_compact_font.py`: 113 passed.
- `git diff --check`: passed.
- Every local hash in `firmware/third_party/dinghy/inventory.json` matches the current bytes.

This is a source-level naming change, not a device or package validation. The
engine-side `FELUCCA_*` names and GPL module identifiers remain outside this
platform task's ownership and were not changed; they need a separately scoped
engine review if the naming policy applies there too.
