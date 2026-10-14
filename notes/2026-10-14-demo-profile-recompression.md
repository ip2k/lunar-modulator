# Optional demo image preparation recompression

The offline `prepare_image_profile.py` and `prepare_demo_selection.py`
controllers now accept the trusted `--recompress-content` option. Their Python
entry points accept the keyword-only boolean `recompress_content`. The option
defaults to false; the browser request schema and pinned demo source identities
are unchanged.

The host encoder uses the existing bounded 4-KiB-window project chunk format.
Preparation reads native records before encoding and again afterward, refusing
any difference before emitting a success manifest. Each recompressed asset
retains the input/output hashes and sizes, saved bytes, encoder identity, and
zlib versions. The final prepared-manifest digest covers those details and the
packed bytes. Selected project order and startup identity remain unchanged.

No target decoder or runtime allocation was added. The option does not promote
sequence acceptance, native RAM/link fit, installability, hardware acceptance,
or a default composition. Sets still retain an incomplete dependency scan;
successful encoding must not be interpreted as complete set admission.

Validation is in `tests/test_native_profile_recompression.py`: all eight demos
through the real codec, project/set record equivalence, rejection of a changed
record stream with removal of the new output directory, and rejection of a
non-boolean option before creating output. Hera verification passed all 39 adapter/profile/integrity/selection tests using
the actual native reader. The pinned environment, exact overlay hashes and log
receipt are in `2026-10-14-native-profile-recompression-validation.md`. Local
focused host-encoder checks also passed (seven passed, one native-reader test
skipped because that executable is not built locally).

The separate exact-c083 target size experiment is recorded in
`notes/2026-10-14-all13-fullsong-link-comparison.md`. It linked a thirteen-engine
application with one recompressed legacy Afterglow project, with 928 bytes of
XIP margin. That experiment predates this controller adapter and does not
establish a released default or arbitrary multi-project fit.

Coordinator verification: the focused local selection passed eight tests with
one native-reader skip. An initial local `-k` filter accidentally selected
three native-reader cases without `FM1_STATE_TOOL`; those failed on missing
environment configuration. The configured Hera run passed those cases as part
of the 39-test suite. No source change was needed. The retained raw
`target-sections.txt` has objdump trailing spaces, intentionally preserved as
evidence; the staged whitespace check is otherwise clean.
