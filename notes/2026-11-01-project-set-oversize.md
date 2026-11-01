# PROJECT saves must retain the set or refuse

Personal, non-commercial work. Exact starting commit:
`da7bd022d8b1244f9668a0498ff3dd866b33d652`.

## Scope and implementation

[verified] `set_text` returned zero both for absent sequencers and exports at
least 65,538 bytes long. PROJECT collection interpreted either as absence and
succeeded without SEQS. The source inspection finding became a measured
regression below; it was not initially a verified default-pool reproducer.

The plan saved before editing was to distinguish overflow in the private
helper, preflight PROJECT before collecting records, and reuse that export in
collection. This is the implemented change. Oversize PROJECT saves now return
`FM1_STATE_TOO_BIG` before any external output. An absent sequencer still omits
SEQS. Workspace interfaces, codecs, caps and other format paths are unchanged.
The existing fitting 65,537-byte behavior is preserved; no buffer/format cap is
silently reduced. No native storage, codec rewrite, UI or hardware changes.

## Focused regression

[verified] Source and tests frozen at
`9ce42c4b2acdceaaf58210feba4f021d98d82f56`; production source has been unchanged
since checkpoint `6344680720afe490d78bf60c9109280408b7871c`.

`tests/test_project_set_oversize.py` builds the actual app with test-sine,
test-gain and the existing minimal modulation modules, then runs
`sim/web/test/fm1_project_set_oversize_check.c`. An optional
`FM1_PROJECT_SET_BASELINE_SOURCE` substitutes only the exact starting state TU
into an otherwise identical source closure. The export symbol fixture delegates
to the real exporter except for explicitly selected exact-length tests.

The real dense default eight-track set has 1,536 notes, 1,536 locks and 256 trig
rows and exports 64,920 bytes. It is positive fitting coverage. The real
oversized set uses supported caller-selected limits in the unchanged 32,768-byte
app arena: Capture history is disabled and the note pool grows to 1,600; other
pools remain unchanged. Factory size/create checks prove this fits that arena.
Its canonical export is 66,456 bytes. Both sets import/export/import/export
without refused edits or Movy faults. This custom pool case is not claimed to
be reachable through the default UI; no production limit changes.

[verified] Fresh normal and Clang ASan/UBSan builds passed:

- The exact baseline reports success and calls output on the real oversized
  set, then fails the new refusal assertion (expected RED).
- The fixed app refuses that set and the exact 65,538-byte fixture with code 7,
  zero output calls/bytes, in all four PROJECT modes, through both the host
  wrapper and explicit workspace API.
- Whole-app and attached edit-history byte snapshots remain unchanged. Live
  held-note PCM is equal across saves and explicitly required to be nonzero.
- Subsequent fitting saves succeed, proving refusal releases the workspace.
- Empty real sets, absent sets, exact 65,536/65,537-byte fixtures and the real
  default dense set succeed in every mode/API. All four baseline/fixed,
  normal/sanitized valid-corpus digests are `8bcc4635`.

ASan used `-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer`, leak
checking and UBSan halt-on-error. No sanitizer diagnostics occurred; the expected
baseline assertion appears in both logs. The immutable container images and
source/log SHA256 values are recorded in the private receipt.

The container images have no pytest install. A small runner loaded the actual
pytest test function, supplied its temporary path, and executed every compile,
subprocess and assertion. Its only pytest API, the missing-tool skip, was
replaced with an exception; tools were present. Parent CI still runs normal
pytest discovery/integration. These focused builds do not prove target ABI,
WASM integration, the complete engine registry or hardware acceptance.

## Orientation and lifecycle

Rarefaction primary-root status and bounded scope were checked; external
worktree orientation was refused. Serena instructions/config and bounded helper
query were read without changing its shared primary project; that body belongs
to the other checkout. Direct source/caller/build reads were the fallback. No
claim of complete indexed analysis of this isolated worktree.

LAN work used the preapproved lan-compute skill and existing access docs,
verified SSH host keys, uniquely reserved CPU 12–15, maximum 4 CPU/6 GiB,
`docker-batch.slice`, network disabled, `--rm` and task labels. Both closures
built fresh; no cached engine objects. Data lives in the single owned stage
`/home/likwid/datasets/lunar/project-set-oversize-20261101`.

Small logs/commands/receipt are mirrored in this worktree's ignored
`scratch/project-set-oversize-20261101/evidence/`. Independent review and final
cleanup are recorded below. The source worktree stays available for parent
integration and is removed after merge. Mac free space before work: 1,116 GiB.

[verified] Independent reviewer audit_effects approved frozen `9ce42c4b` after
rerunning both original normal/sanitized harnesses and verifying source hashes.
A private normal shadow fixture captured every valid output callback with its
length prefix. All 40 operations produced byte-identical baseline/fixed streams:
1,005,670 bytes, SHA256
`d5966e351f45ee1eb337e4c63d96d3fd9140e7e4158651eda35c2571cf9fe60f`.
The reviewer removed its shadow source, object, executables and captures.

[verified] After reviewer release, the owned source, exact baseline TU and all
normal/sanitized build directories were removed. No task-labelled containers
remain. CPU 12–15 is released and the next worker was notified. LAN retains
128 KiB of logs/commands/receipt; the local ignored evidence is 76 KiB. Mac free
space at handoff is 1,116 GiB. No vendor binaries or build products entered Git.

Next dependency: parent reviews/integrates the frozen branch through required CI
and pins the final WASM build and future persistence oracle to that integrated
source. This bounded fix does not make native persistence fit or enable it.
