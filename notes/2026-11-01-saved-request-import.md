# Saved customization request import

Personal, non-commercial project. Base: `94a1553df8c6fd01eb44dbfc8171275a2b73da91`.

[verified] The offline customization page now has a labelled native JSON file
picker, an explicit Load button and polite live status. File selection alone does
nothing. Reading and reopening a request never submits a build, fetches another
resource, or performs a service/device operation. Existing export behavior stays.

[verified] Input is limited to 64 KiB before reading and again as UTF-8 text.
JSON grammar, duplicate object keys (including escaped equivalent spellings),
exact v1 keys, required module arrays and the optional configuration pair are
checked before calling the existing `buildNativeDemoSelectionRequest` validator.
The existing validator owns current catalogue IDs, dependencies, eight-project
limit, ordered startup index, companion SET parent/startup constraints and fixed
diagnostic mode policy. Unknown fields and stale choices refuse rather than
silently disappearing. Explicit empty SET lists canonicalize to omission, as
with existing exports; module/project/SET vector order is otherwise preserved.

[verified] Both views prepare validated, callback-free updates before either is
committed. Module controls, project order, startup radios, optional SET controls,
shared profile and diagnostic selector then update synchronously, followed by one
selection revision invalidating any prior receipt. Invalid requests preserve all
previous choices. A pending submission refuses import. An edit while the file is
being read refuses the eventual result; a destroyed page cannot be restored.

## Established platform choice

[verified] Reviewed the standard native file input and File/Blob API:
[HTML file input](https://html.spec.whatwg.org/multipage/input.html#file-upload-state-(type=file))
and [File API text](https://w3c.github.io/FileAPI/#blob-text). Native labelled
controls fit the current plain JavaScript/HTML stack, keep keyboard activation,
work offline, and need no framework, bundle or third-party licensing dependency.
The small adapter reads only the chosen file with `File.text()`; the `accept`
attribute is a picker hint and validation does not trust MIME or extension.

## Checks and limits

[verified] `node --test` across installer-page, native-demo-selection-view,
native-demo-selection, native-build-selection, installer-build-client and
installer-package-inspection: **74 passed**, zero failures/skips. This includes
actual exported Blob JSON after restoring each of legacy/song-diagnostic/
continuous modes; reordered module/project vectors, startup, companion SET;
malformed/oversize/extra/duplicate/escaped-duplicate JSON; stale IDs and missing
dependencies; invalid startup/SET/configuration; all-controls rollback; unreadable
files and asynchronous read/edit/destroy races; no build/additional fetch; and
native keyboard/label/live-status HTML structure. `git diff --check` passes.

[verified] Rarefaction status selects the main checkout, and orient/scope with
this worktree's absolute path refuse the external-worktree boundary. Serena
initial instructions/config were checked without shared activation/restart; an
absolute `installer-page.js` symbol overview returned downloadRequest,
findButton and mountInstallerPage, matching source. Exact absolute-worktree
source and tests were used for investigation/edits. No graph was built.

Real Chrome visual/interaction acceptance remains pending because its controls
are unavailable; no CUA/OS/browser workaround was used. These Node checks do not
prove visual layout, assistive-technology behavior or real browser file picking.
No firmware/build/container/download/device operation was performed. Source
review, integration and exact-head CI remain coordinator dependencies.

Lifecycle: only the owned worktree and small log/handoff under
`scratch/request-import/` remain. Node checks create no retained build products
or temporary directories. Mac free space after checks: 1,114 GiB (500 GiB floor).
Coordinator removes this worktree with `git worktree remove` after integration;
retain the branch backup and small evidence until review is complete.
