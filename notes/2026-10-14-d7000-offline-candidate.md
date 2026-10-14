# D7000 offline raw candidate boundary — 2026-10-14

The native linker now supports `expanded-d7000`, but the previous offline
raw constructor always cleared the application area through D9000. This
change adds explicit `expanded-d7000` selection to both the raw geometry
constructor/validator and the provenance/ELF-bound candidate CLI. The default
remains `expanded-d9000`, preserving existing callers and campaigns.

The selected boundary limits the complete app plus retained cfg-tool/cfg,
not merely the ELF text. D7000's application budget is 860644 bytes. Every
physical byte from D7000 onward is preserved from the matching baseline;
the candidate receipt excludes those sectors from allowed writes and marks
them protected. Unknown layouts and applications fitting only D9000 are
rejected. An independent validator checks unchanged tail bytes, record
contents/CRCs and padding. No loader bytes, stage ownership or completion
records are generated.

Verification uses synthetic stock records and ELF inputs, not owner backups
or vendor binaries. Tests cover the exact D7000 budget, the measured 845036
application size, altered bytes in both reserved sectors, both RAM layouts,
ELF/app binding and continued false hardware/migration/installability flags.
This is an offline construction capability; existing physical adapters have
not been widened and no new hardware campaign is admitted. A preserved tail
is not proof it holds a working rescue loader or survives interrupted writes.

Semantic navigation remains selected to the primary checkout rather than the
coordinator worktree. It was left unchanged to avoid disturbing other active
sessions; this edit was reviewed with file inspection and synthetic tests.

[verified] Both focused pytest files passed: 60 tests, exit zero, with the
existing repository Python venv. `git diff --check` passed. No device command
was issued.
