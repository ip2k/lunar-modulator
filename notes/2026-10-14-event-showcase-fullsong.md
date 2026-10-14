# Event Horizon Showcase full-song native-app render

Status: host-native offline check passed for one exact adapted showcase file; this is not owner listening, device playback, install admission, or musical approval.

## Exact input and method

Source checkout: `/home/claude/.local/share/codex-worktrees/event-showcase-fullsong-validation`, branch `feature/2026-10-14@event-showcase-fullsong-validation`, base `ddfe0e7a55b850ac79a1d6ca21c43ea0d6c2bf81` (verified at task start). The unchanged project file is [`event-horizon-showcase.lunar`](../engines/state/examples/replacement-showcases/event-horizon-showcase.lunar), SHA-256 `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f`. Its catalogue/materialization receipt identifies the adapted asset as 150 BPM, 68 bars, seven scenes, nominal 108.8 seconds; the duration is 68 × 4 beats × 60 / 150. The original authored song origin and the four metadata-only label substitutions remain documented in [`demo-preload-catalogue.md`](2026-10-14-demo-preload-catalogue.md) and [`native-demo-replacement-materialization.md`](2026-10-14-native-demo-replacement-materialization.md).

Built the real host application renderer target `fm1-sim-render` from the exact checkout with `sim/web/mk/sim.mk`, using the production module resolver and exactly 55 non-test modules (including GPL production modules). The pinned image was `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`; source mount was read-only, network disabled, cgroup `docker-batch.slice`, 4 CPUs and 4 GiB memory/swap. A fresh, separate build produced the same executable SHA-256 twice: `67f013bd7a2a6122bbdbc74c8bf76eef1be19202cbea4d09c0f0ac2ca952a04e`. Build and render container inspect receipts record zero exit status and the requested resource/image identities.

The renderer loaded the full `.lunar` project through `fm1_app_state_load`; the playback request used the same 142-line `set` extracted byte-for-byte from that project, then issued the normal `play` action and rendered 108.8 seconds through `fm1_app_render`. The CLI initializes its sequence before applying `--load`; therefore the subsequent project load restores the project's own embedded set, which is the set started by `play`. The extracted 142 line values exactly match the embedded `set` list; the newline-delimited `.movy1` file SHA-256 is `cfc53ae471b9541adaf817180de721e268e2a43adaeea77154c8ec9a6bb6b7f3`.

## Observed result

The native loader reported `OK`, kind `project`, four sound units, two effects, five active modules, eight tracks, 56 clips and seven song entries, with `left_out=0` and `skipped=0`. The project retained its seven named scenes (`Air`, `Call`, `Rise`, `Impact`, `Tense`, `Sky`, `Land`) and the embedded song arrangement.

The render emitted 4,800,038 frames at 44,118 Hz (108.799991 seconds after the CLI's integer frame conversion). The app reported peak `0.312920`, RMS `0.043009`, 7,681 sequencer events, 576 notes routed to engines, zero refused events, zero dropped events, zero held notes, zero busy lines, zero sequence lines left, and zero sequencer-sounding notes at completion. Event log counts were 576 note-ons, 576 note-offs, 6,528 clocks, and one start event. Final song state was seven entries, `entry=6`, `now=6`, `next=255`; this is the last of the seven scene entries and the song's configured end state. The last note event occurred at frame 4,778,163, before the end of the rendered interval.

The WAV is stereo 16-bit PCM at 44,118 Hz with 4,800,038 frames. All 9,600,076 channel samples are finite integer samples; min/max were -10,253/+10,088, absolute peak 10,253 (31.3% of signed 16-bit full scale), no samples reached the clipping rails, and 9,448,802 samples were nonzero (98.4%). This establishes active, non-clipped host-rendered audio numerically; it does not establish subjective sound quality.

SAVE/reload was checked in two ways. A zero-duration project load/save preserved the 142-line set, sounds, and master data exactly. The save-at-render-end project reloaded successfully and saved again to byte-identical canonical JSON (both SHA-256 `54d863725cf31ed4cc880060f6942c7a1d01d0f7a15d9831d971161d884b86f6`). Compared with the source set, the completed-save set has only the eight expected per-track UI cursor lines changed from `tk <track> 0 0` to `tk <track> 6 0`; all other 134 set lines are unchanged. The completion position is therefore persisted and reloadable rather than silently reset.

## Evidence and limits

Full render assets/logs remain off-repository on Hera at `/home/claude/.local/share/codex-coordination/receipts/lunar-event-showcase-fullsong-20261014/`; especially `attempt-c/{container-inspect.json,render.stdout,render.stderr,commands.log,events.jsonl,event-horizon-showcase.wav,roundtrip-end.lunar,run-output-hashes.txt}`. The independent fresh build receipt is `attempt-d/` (build stdout/stderr, inspect JSON, executable hash). WAV and logs are not checked into Git. Both build and render were host-native on the pinned Linux image, with no hardware commands.

This proves one native host application load/render/save/reload path at the 55-module configuration. It does not prove pi32v2 code generation or target RAM, physical FM-1 playback, installation, owner listening, or musical approval. The original and adapted compositions remain pending owner acceptance; no default preload is promoted by this result.

## Handoff

Owned artifact: this note only. No production source or test files changed. Branch is an isolated Hera worktree and has no commit/push yet; coordinator review and authorized GitHub backup remain pending. Next useful gate is owner listening on an approved playback path, followed separately by any target/physical acceptance the owner requests.
