# D7000 named-profile prerequisites

The private `expanded-d7000` / `song-diagnostic` profile fixes the native
wavetable profile to Plaits Shapes8 and invokes `hall-o2-stage7-v1`. A valid
selection therefore includes Macro, Shapes, SixOp and Drums in the `engines`
group, plus Hall in `effects`. The caller selects these modules explicitly;
preflight does not add modules.

`tools/native/diagnostic_profile_contract.py` is the lightweight Python source
of truth for backend group membership. The API and preparer reject incomplete
requests before work is queued or staged, and the image builder retains its
direct-call guard. The deployed worker runs from a shallow `/input` mount before
its source archive exists, so it uses a small pinned bootstrap contract and
checks it against the shared module in the safely extracted source before
invoking the build. Browser serializer and client use the same JavaScript
contract exported by `native-build-selection.js`; tests pin the IDs and groups
independently in each language.

Ordinary D9000 request bytes and default behavior remain unchanged. The static
installer page does not enable the optional private D7000 configuration. This
change makes no package publication, installability, hardware, playback or
release claim.

Focused validation on 2026-10-16: service and native-profile Python tests passed
151 with one existing skip; native-selection prerequisite preflight tests passed
6 (12 deselected); browser selection/client/page tests passed 34. The deployed
worker bootstrap regression exercises contract agreement and mismatch from a
shallow entrypoint, and verifies mismatch stops before `make`. See the
companion isolated-worktree `scratch/d7000-profile-preflight/HANDOFF.md` for
exact commands and commit/push evidence.

Standalone-worker follow-up: branch
`fix/2026-10-16@d7000-profile-preflight`, commit
`6c38f3ff54480b8fab65c36b739ab531549795a8`, pushed to the authorized `origin`
branch and verified with `git ls-remote`.
