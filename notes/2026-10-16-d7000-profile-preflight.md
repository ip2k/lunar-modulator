# D7000 named-profile prerequisites

The private `expanded-d7000` / `song-diagnostic` profile fixes the native
wavetable profile to Plaits Shapes8 and invokes `hall-o2-stage7-v1`. A valid
selection therefore includes Macro, Shapes, SixOp and Drums in the `engines`
group, plus Hall in `effects`. The caller selects these modules explicitly;
preflight does not add modules.

`tools/native/diagnostic_profile_contract.py` is the lightweight Python source
of truth for backend group membership. The API and preparer reject incomplete
requests before work is queued or staged, the worker repeats the preflight, and
the image builder retains its direct-call guard. Browser serializer and client
mirror the small grouped contract so malformed requests fail before a POST.
The browser contract test pins the same module IDs and groups.

Ordinary D9000 request bytes and default behavior remain unchanged. The static
installer page does not enable the optional private D7000 configuration. This
change makes no package publication, installability, hardware, playback or
release claim.

Focused validation on 2026-10-16: service and native-profile Python tests passed
149 with one existing skip; native-selection prerequisite preflight tests passed
6 (12 deselected); browser selection/client/page tests passed 33. See the
companion isolated-worktree `scratch/d7000-profile-preflight/HANDOFF.md` for
exact commands and commit/push evidence.
