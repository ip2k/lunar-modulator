# Private continuous installer service

Work in progress on `feature/2026-10-16@continuous-installer-service`, based on
`2788c82dc098f68f41919d4c00f10d4a81911bd2`. Coordinator owns integration and
fresh target links; this worker owns installer API/worker/provenance/browser and
narrow continuous-only selection adapter changes. No Hera/device access.

Implemented separate private continuous D7000 selection contract, FM-1_500
identity, fixed no-return runtime, Shapes8 selected namespace policy, enabled
TRS receipt checks, disarmed SAVE policy, distinct provenance/evidence branches
and explicit browser selector. Existing diagnostic defaults and canonical
requests remain. HTML service marker remains disabled. No binary route.

Validation checkpoint: existing installer API/profile/controller tests passed.
Initial combined run had missing FM1_STATE_TOOL environment for six content
preparer tests and two obsolete tests requiring Hall modules for continuous
mode; addressing these next. Browser old assertions need updated button label.
New adversarial continuous-specific tests remain to be added. No target fit is
claimed: all55 previous size is historical, and every new subset still needs
actual target ABI/link measurements. Existing CONTINUOUS_TARGET_STORAGE is
reused from recorded all55 target measurements, not newly measured here.

Semantic MCP check: Serena initial instructions/current config and Rarefaction
Python status identify /Users/likwid/Developer/mvave-fm1-firmware. Bounded
BuildRequest/find_symbol and worker/orient requests fail ENOENT because primary
checkout lacks these files. Did not retarget shared active servers; worktree
file inspection and meaningful tests are the available coverage.

Next: complete adversarial API/worker/evidence/browser coverage, rerun focused
suites using repository venv and configured state tool, review changes, push
verified checkpoint and report exact integration dependency.
