# 15 — Firmware development

This branch develops a local Python application for decoding the FM-1 firmware,
editing and rebuilding it, and eventually validating replacement DSP on the
device. The final target includes our own installation, rollback, and recovery
tools. The current implementation is an intermediate step toward that target.

## Run

The GUI is the workbench website, served by Python on loopback. Python 3.10 or
later is required. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\.venv\Scripts\python.exe tools/fm1_workbench.py --open
```

The MIDI dependencies are optional for offline work. Inspection, project
storage, decoding, modification and rebuilding use Python's standard library.
The interface uses the local Python HTTP server. It requires no external web
service, M-UPGRADE, or installed vendor USB driver.

## Project files

A `.fm1proj` file contains the original firmware bytes, subsequent revisions,
their change manifests, and saved analysis. It is a private local SQLite file,
not a report suitable for publishing. These files are excluded from Git. An
explicit project save retains it under `scratch/projects/`; a download makes a
portable copy. Unsaved loaded files are held in a bounded in-memory cache.

[verified: `tests/test_fm1_project.py`] The original revision and all later
byte-bearing revisions are immutable through the application API. Every
revision has a SHA-256 digest and a parent. Its change manifest must name the
exact parent and result hashes. Analysis is attached to the corresponding
firmware hash, preventing an analysis from another version being saved against
it. Reopening checks the recorded hashes and revision chain. This detects
accidental corruption; it is not a signature or an authenticity guarantee.

Saving or exporting never overwrites an existing project or firmware file.
Firmware exports preserve the selected revision's bytes exactly. The project
stores labels rather than absolute source paths. Do not add personal data to
project labels or reports.

## Development workflow

1. Open an original package and save a project. The source remains available as
   the first revision throughout development.
2. Inspect the package, executable regions, strings, functions, feature
   associations and DSP findings. Separate byte-proven relationships from
   inferred names and unresolved calling conventions.
3. Select an application offset and prepare changes with both the expected old
   bytes and replacement bytes. Inspect the complete change manifest.
4. Rebuild to a new output and validate every supported container integrity
   layer. Record the result as a child revision of the exact source.
5. Roll back using the saved manifest and verify that the original package hash
   is recovered. Offline rollback verifies bytes, not a device recovery route.
6. Hardware validation follows only after the necessary recovery evidence and
   exact-operation confirmation. A transfer acknowledgement, a successful build,
   or passing container CRCs cannot establish that the intended DSP is running.

Details: [executable decoding](13-firmware-decoding.md),
[rebuilding](14-firmware-rebuild.md),
[package integrity coverage](12-package-inspection.md), and
[hardware recovery](07-recovery-and-risk.md).

## Full completion requirements

These requirements are retained in full. The GUI, partial decoding,
offline patches, and tests do not complete the firmware-development goal.

| Requirement | Evidence required before completion |
| --- | --- |
| Complete container and image decoding | All header, entry, executable, resource, boot and update layers accounted for; encryption/integrity algorithms independently validated; unknown/reserved fields explained |
| Complete executable and memory map | Instruction decoding coverage; code/data boundaries; RAM copy/BSS/stack/heap maps; functions, indirect calls and interrupt interfaces; verified flash/SFR interfaces |
| Every standard feature mapped | UI controls/pages, synthesis, MIDI routing/SysEx/CC, storage, sequencer/arpeggiator, effects, configuration and runtime behavior linked to version-specific implementations |
| Every core DSP component understood | Algorithms, parameter units/ranges, state layouts, data flow, call interfaces, fixed/floating-point behavior and reference vectors |
| DSP replacement | Our own compilation/injection path, relocation and size checks, correct rebuilt metadata, and predicted audible/measured behavior on the physical device |
| Reversible GUI workflow | Persistent version-aware projects, explicit change previews, exploration of mappings, reproducible rebuild/rollback and evidence reporting |
| Our own flash/verify/rollback/recovery | Proven device-specific readback and recovery; robust staged transfers, interruption handling, post-boot checks and known-good restoration |
| Independent finished workflow | No runtime dependence on M-UPGRADE, vendor applications/toolchains, proprietary USB drivers, or external browser services; the local workbench remains the GUI |

Every row remains open until its complete evidence exists. The executable
decoder reports unresolved items explicitly. Known library tables, matching
function bytes, and test counts are individual observations, not claims of
complete reverse engineering.

## Component boundaries

| Module | Responsibility |
| --- | --- |
| `fm1_package.py` | Container validation, application extraction and table inspection |
| `fm1_decode.py` | Executable, memory, feature and DSP analysis from image bytes |
| `fm1_dsp.py`, `fm1_effects.py` | Source-bound lookup-table fingerprints and V15 effect callback/stage observations |
| `fm1_pi32.py` | Bounded V15 integer interpreter with packet atomicity and explicit unsupported cases |
| `fm1_operator.py` | Independent three-operator state and reference block model |
| `fm1_verify_operator.py` | Finite V15 vector comparison between the interpreter and the reference model |
| `fm1_rebuild.py` | Source-bound patching, metadata reconstruction and inverse changes |
| `fm1_project.py` | Private original/revision storage and analysis provenance |
| `fm1_workspace.py` | Bounded loaded files, local projects, hex views and rebuild operations |
| `fm1_workbench.py`, `web/` | Local HTTP API and browser interface |

Research may compare our algorithms against previously generated vendor-tool
output. Such comparisons are independent development evidence; those vendor
tools must not become requirements of the finished application.
