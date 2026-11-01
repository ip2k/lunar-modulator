# CI RAM fixture and sequencer specification correction

Personal, non-commercial Lunar work, based on
`6ece5032bb4a2e7f3856350c89015725f727a473`.

[verified] Mac CI run 41331077051, job 124921216033, exposed two app-state
fixture failures and a stale manual specification. `test_each_kind_loads_into_its_target`
attempted to import the complete Deep Bass sound (Shapes + Filter + its LFO
and cable) into Sound 2 beside the Macro/Plate starter. The application correctly
refused it at 101% RAM. The full-rack case in
`test_every_refusal_changes_nothing` used the same combination, so RAM
preflight refused before the intended `NO_ROOM` rack check. The source checks
RAM before modulation merge capacity; this priority is unchanged.

[verified] The successful import and full-rack fixtures now use explicit
Macro/Room instead of the starter's Macro/Plate. Metadata reports Plate as
65,728 bytes and Room as 41,184 bytes: 24,544 bytes are removed from an unrelated
master effect while preserving the incoming sound, insert parameters, LFO,
cable target remap, full eight-position rack, refusal-state byte comparison,
and `--without` behavior. The original starter/Deep Bass combination is now
also checked explicitly for a transactional RAM refusal. No budget, preflight
priority, sound example or engine implementation changes.

[verified] The manual test was correct. The sequence allocation changed from
36,864 to 45,056 bytes when immutable event targets were added (`a75cdef3`),
while chapter 13 retained 10% (36 KB). The chapter now gives 12% (44 KB), using
the existing metadata budget of 387,924 bytes and upward meter rounding. The
specification test remains unchanged. This says nothing about hardware RAM fit
or the separate eight-voice release acceptance target.

[verified] Local specification test reproduced the missing `12 % (44 KB)`
failure before the edit and passes after it. The remaining manual tests that
do not build an engine: 15 passed, 7 skipped because Markdown is absent,
1 deselected (`test_full_build`). An initial broad manual selection accidentally
reached the renderer fixture; it was interrupted and its 2 MB partial build
was removed. Native app proof is pending the coordinator's bounded LAN lane.

[verified] Rarefaction status/orient/scope and Serena initial/config/find_symbol
agreed on the representative test body in the shared main checkout. Their root
is `/Users/likwid/Developer/mvave-fm1-firmware`, outside this isolated worktree;
no shared activation/restart occurred. Exact base source reads and bounded
searches in this checkout are authoritative for this change. No graph was built.

No device traffic, firmware/vendor processing or protected-target work occurred.
The lane's ignored evidence lives under `scratch/ci-ram-spec-fixtures/`; final
handoff and cleanup status will be recorded there and in the coordinator's
requested performance evidence directory. Built-in drive free space: 1,114 GiB.
