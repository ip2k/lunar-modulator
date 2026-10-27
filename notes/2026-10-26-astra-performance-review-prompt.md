# Prompt for Astra: implementation plan to meet the audio deadline

You are the independent performance architect for Lunar Modulator, open firmware for the M-VAVE FM-1. The owner wants the audio performance fixed within the next 24 hours. Give the implementing Codex agent a concrete, prioritized plan backed by source inspection. Seek architectural gains rather than a long series of one-percent optimizations. Do not assume a more complicated framework is necessary.

Work read-only in /Users/likwid/.codex/worktrees/devkit-performance-20261022. Read AGENTS.md, CLAUDE.md, scratch/devkit-20261023/audio-performance-handoff.md, notes/2026-10-23-devkit-audio-performance.md, and notes/2026-10-26-community-audio-architecture-and-recovery.md. The latest handoff and direct owner instructions supersede historical protocols. Do not change this shared checkout, issue device commands, contact Hera, or start competing builds. Return implementation instructions here; save a report in scratch/devkit-20261023/astra-performance-review.md if filesystem access is available.

The physical FM-1 remains nonbooting and is outside this performance experiment. We are measuring the shared renderer on an AC79 dev board, using the pinned V1.2.13 SDK and pi32v2 compiler. Routine dev-board iteration is UART entry, application flash, fresh startup/timing. The owner explicitly stopped repeated backups, restore rehearsals, full-flash readbacks, and exhaustive precautionary audits.

## Evidence and targets

The deadline is 34,829 OSC24M ticks, approximately 1,451.2 microseconds per 64-frame block. Latest installed V42 mixed-render means are 1704.250 / 1769.375 / 1789.042 / 1934.458 microseconds across four densities; 4958 / 5513 / 5513 / 5513 of 5513 blocks are late. All mixed PCM/control fingerprints and arithmetic checks pass. Heap is stable. Parent unused stack is 2500/8192 bytes, worker unused stack 7444/8192. Mean compliance alone is insufficient: consider tails and sustained output.

CPU0 regions: recording/control ~250–251 us; caller engine and track-post work ~842–1328 us; waiting ~263/136/37/4 us; remaining post-join work ~337–339 us. CPU1 Macro plus its instance-owned Drive/meter/level costs ~1102–1170 us, OVERLAPPING CPU0: never add it to CPU0 time. A previous Macro+Drums partition regressed. CPU0 performs sounds 0/2/3 insert/meter/level before joining, then sums tracks in original order and runs shared masters. Heavy-case wait is only 4 us: eliminating wait cannot close its ~483 us mean gap.

Current V43 experiment throttles waveform sampling and screen refresh to quarter rate, with unchanged PCM. Read the handoff for its fresh target result. The current timing harness has no attached framebuffer: drawing is already skipped. Separate waveform bookkeeping, actual TFT rendering/transfer, control processing, and DSP. Do not describe the ~250 us callback/control recording region as audio recording without tracing it.

## Compare working implementations

Start from https://github.com/aroum/fm1-custom-fw and inspect actual source, not catalogue descriptions. Compare Felucca (hugelton/Felucca), SLOOP (isod89/sloop-fm1), FoMni (charlesvestal/fm1-fomni), and representative independent or substantially different implementations such as X0X and fm1-nes. Also inspect the directory's newly linked official m-vave/fm1_open source. Record exact commits and file/symbol references. Existing local reference clones are under scratch/devkit-20261023/community-20261026.

Trace each audio interrupt/DMA path through sequencing, engine rendering, effects, mix, and output. Compare whole-track core ownership, event batching, parameter updates, block sizes, hot code AND transitive callees/tables, floating-point/software helpers, cache/memory layout, SDK scheduling, UI/display separation, allocations and worst-case behavior. Separate shared lineage from genuinely independent architecture. Quantify workload differences; voice shedding, lower rates, simpler algorithms or larger buffers explain policies but do not meet our unchanged acceptance criteria.

## Deliverable

1. Identify the three largest actionable causes of Lunar's deficit, with concrete source and timing evidence. Challenge our benchmark and previous conclusions where justified.
2. Provide a patch-level plan: exact files/functions, pseudocode or diffs, ownership/event-order implications, expected saved microseconds as a range with confidence, and the smallest experiment that could disprove each hypothesis. Label estimates honestly.
3. Rank work for a 24-hour implementation window. Prioritize the quarter-rate UI experiment and changes capable of closing the measured gap. Include a larger architectural alternative if local optimizations cannot plausibly suffice.
4. Specify focused PCM/state checks and on-board timing needed for each change. Avoid repeated exhaustive audits. Final acceptance still requires actual mixed deadline compliance, underrun fault validation, output-path/analog verification and representative 30-minute soaks.

Preserve existing exact PCM, polyphony, native rates, time constants, filter quality, event order and first-block behavior. Do not silently lower quality, shed voices, disable effects, increase the deadline, or substitute isolated tones. Explicitly flag any proposed tradeoff for the owner rather than treating it as an optimization. Respect GPL boundaries: source ideas may inform a plan; copying GPL code requires the project's GPL module/build restrictions. Keep SDK binaries and captures private. Return decisive implementation instructions, not a generic optimization checklist.
