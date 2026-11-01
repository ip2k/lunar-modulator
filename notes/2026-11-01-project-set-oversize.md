# PROJECT saves must retain the set or refuse

Personal, non-commercial work. Exact starting commit: da7bd022d8b1244f9668a0498ff3dd866b33d652.

## Bounded plan, before editing

[verified] `set_text` returns zero both for absent sequencers and exports at least
65538 bytes long. PROJECT collection interprets either as absence and succeeds
without SEQS. The complete app can therefore be saved without its set.

Change only `sim/web/src/fm1_app_state.c` and focused host regression/driver:
report overflow separately inside the private helper, preflight PROJECT before
collecting records, and reuse that exported text during collection. Preserve
workspace interfaces, caps, codecs, absent-set behavior, all valid bytes and
other format paths. Refuse with TOO_BIG before any external output. No native
storage, codec rewrite, UI, device or hardware work.

Build the real app with minimal test engines. Fill its existing sequencer pools
with a valid oversized set, roundtrip it through the existing importer/exporter,
and check four PROJECT modes, zero callback calls, app/edit byte snapshots and
PCM. Use a link-local export fixture for exact boundary lengths only. Compare
valid output hashes to the exact baseline and demonstrate that the unchanged
baseline fails the new oversized assertion. Run normal and Clang ASan/UBSan.

Rarefaction primary-root status and bounded scope were checked; external worktree
orientation was refused. Serena was read without changing its shared primary
project; its helper body reflects that other checkout. Both are insufficient to
prove this isolated source graph. Direct source/caller/build reads are the
fallback; no target ABI or hardware claims.

Lifecycle: source worktree is lunar-project-set-oversize-20261101. LAN stage is
/home/likwid/datasets/lunar/project-set-oversize-20261101; CPU12–15, max4CPU6GiB,
docker-batch.slice, --rm and task labels. Preserve small logs and remove owned
source/build intermediates after results. Mac free space before work:1116GiB.

## First measured fixture correction

[verified] Normal build found the default eight-track pools with 1536 notes,
1536 locks and256 trig rows export64920 bytes in this dense fixture. That is
fitting coverage, not an oversized reproducer. The real oversized fixture uses
supported caller-selected pools in the unchanged32768-byte app arena: disable
unsaved Capture history and add64 notes (1600 total). Its real canonical export
is66456 bytes, and import/export/import/export roundtrips without refused edits.
The fixture states this distinction; no production pool/cap is changed.

[verified] First normal run demonstrated old success with one output callback
and new TOO_BIG with zero callbacks in all four PROJECT modes. Exact synthetic
65536/65537 export boundaries fit and65538 refuses. Additional final runs will
cover both host wrappers and explicit caller workspace plus default dense parity.

[verified] Frozen afded052 normal and Clang ASan/UBSan both passed; valid digest
8bcc4635 matches baseline/fixed. Before final acceptance the PCM assertion is
strengthened to require a nonzero held voice after any set-import note releases;
this is a fixture-only change and requires final reruns. Production source is
unchanged since6344680.
