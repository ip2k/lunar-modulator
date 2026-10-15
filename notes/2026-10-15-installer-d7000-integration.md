# D7000 installer profile integration

[verified: source and host tests] Worker commits `06d43fa2` and `cd8ecf36`
were reviewed and integrated as `d7a788b8` and
`4f1f8a3fddf042381c84a3afbf206d6494f7b222`. The latter SHA was independently
matched against the feature branch on origin after push.

The diagnostic service now accepts the explicit expanded-d7000 /
song-diagnostic pair and checks the fixed Macro + Shapes8 wavetable/storage
profile. Legacy omitted-profile requests preserve their canonical bytes.
Neither profile is promoted to installable or hardware accepted.

Initial review caught an actual downstream incompatibility: the API accepted
the new keys but prepare_selection rejected them. The correction accepts the
exact profile pair, retains it in the canonical request digest, and rejects
conflicting build layout/runtime flags before creating output. A regression
uses the real catalogue/stager and build_selection -> prepare_selection path,
intercepting the codec and native link, and checks the emitted link arguments
and retained request digest. This is boundary coverage, not a target build.

Root post-integration checks used the pinned environment at
`/tmp/lunar-installer-service-test-venv/bin/python`:

- Installer-service suite plus non-codec selection checks: exit 0, one skip.
- Six codec-dependent legacy selection checks: exit 0 with
  FM1_STATE_TOOL pointing at this worktree's engines/build/fm1-state.
- An initial worker-checkout run without FM1_STATE_TOOL failed those six
  tests with missing-environment KeyError; the configured rerun resolves that
  test prerequisite and is recorded separately from the first attempt.

Trusted tuple issuance, protected stock composition, artifact download,
browser admission and end-to-end hardware installation remain separate open
work. No device action or hardware acceptance occurred in this integration.

The separate Hall gain-cache target build completed all 16 Hera shards and
link. Worker receipt dc6e90491a440b30e7e53bc0cdd98a91785133844e979efadebb91501cc854d4
binds app 80175b90053bb568d485ebd71516f19889064a4c8c97c8f87c4d0f0747ad08d0.
Worker review reports 855700 app bytes, DSP ending 0x01c04164, and one float
subtraction moved from Render into Coefficients; no measured speedup is
claimed. Its durable Hera handoff SHA is
8749c440aadda181b6613c4b0df21ff256a7ed384531b31961c265e39d4e7b9e.
Root assigned a new file-only deployment preparation; physical deployment
requires independent review, fresh state/backups and all existing safeguards.
