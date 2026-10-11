# Hera demo runtime fallback — 2026-10-11

The owner authorized Hera as the compute fallback when aeon is unavailable, with up to 30 parallel jobs. [verified: owner instruction]

SSH as `claude@192.168.1.48` returned hostname `hera`, 64 CPUs, 125 GiB RAM (115 GiB available), Docker 29.9.0, and NVIDIA RTX A5000 with 24,564 MiB VRAM. [verified: live SSH preflight]

An Alpine 3.22 container ran successfully with `--cgroup-parent=docker-batch.slice --cpus=30 --memory=1g --memory-swap=1g`. Its `cpu.max` was `3000000 100000`, confirming the CPU quota; host-visible processor count remained 64. Explicit `make -j30` or a smaller per-job limit is still required, and concurrent jobs must respect the aggregate 30-job cap. No host service or infrastructure configuration was changed. [verified: container preflight]

Aeon became reachable during this preflight. The composition agent was instructed to retain underway aeon jobs and run an independent actual song runtime job on Hera in an isolated remote directory. Actual song acceptance is pending its returned receipt.

The runtime acceptance harness now accepts `--expected-count N`; the browser harness accepts an optional fourth argument N. Both default to four, require a positive integer, and require unique song titles. These options permit bounded individual rewrite checks without reducing the default complete-set check.

Semantic-tool limitation: Rarefaction remains selected to the primary checkout and rejects the integration worktree absolute path; Serena is selected to the primary checkout with cpp only. Shared project selections were left untouched; this small JavaScript harness edit used direct file inspection.
