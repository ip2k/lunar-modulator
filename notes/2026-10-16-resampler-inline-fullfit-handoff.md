# Matched thirteen-engine full-fit experiment: blocked before execution

## Exact source and saved work

[verified] Integration baseline is `86154bc7843d7b1965d346af78620917fd2836f1`.
It differs from the first experiment's `d168869b` only in installer, associated
web tests/docs and a NOR-verifier anchor; there are no DSP/native build changes.
Compared to stage-7 source `66c95bb2`, the two changed DSP lines are SPDX comments;
other changes are vendor notices/tools and selection/preparation wrappers.
No old source snapshot was silently reused as the new baseline.

[verified] Candidate **`e75335164423dead395213373bcf221a4d962ea3`** applies the
previously tested experiment onto that integration baseline. The resampler
header is byte-identical to `fd853c5c05b61818281daa1427c73355dbf1da00`.
The only baseline->candidate paths are the resampler header, its placement
regression, differential driver and two experiment evidence files. The
installer changes remain present.

Branch: `codex/resampler-inline-fullfit-20261016`.
Worktree: `/Users/likwid/.codex/worktrees/resampler-inline-fullfit`.
Source/build driver checkpoint **`4cb369b24424bbdc0984a13345762c06cf785740`**
was pushed with explicit refspec and independently matched on origin.
This note is a later documentation checkpoint; the build candidate stays e753.

## Reproducible build and analysis

`notes/2026-10-16-resampler-inline-fullfit/build_pair.py` pins the reviewed
current stage-7 runner SHA256
`60448560af6f6bbe479a1510b1af4e4cd84e6186f3d01fdd0e0f61425915f446` and receipt
`6db18a773eeb48cd18b64d1d01ad184b6a691182f5800bf9e727f2cafcc0fd56`.
It verifies all ten retained output hashes, original profile/selection pins,
current link and catalogue commands, original/candidate header identity and
exact source-path delta. It archives each clean exact Git checkout and runs
fresh baseline then candidate 16-shard catalogues and links in the existing
bounded container policy. No package constructor or hardware tool is called.

`analyze_pair.py` verifies pair receipt/output hashes, all thirteen selected
production engines, exact Hall-O2/SixOp-Os current profile, disarmed SAVE,
linked ELF sections and image budget, and maps each actual RAM Render caller
to its ready-pop and nested FIR callees. It saves prologue instructions for
stack review, counts calls and reports the complete code/section deltas.

[verified: historical fixture only] Byte compilation and help smoke check
passed. The analyzer was evaluated against the retained stage-7 ELF/artifact,
independently finding all thirteen engines, app855920/860644 bytes (4724slack),
RAM code7704 bytes slack, globals/pool1264 bytes slack, Drums pop412 bytes and
SixOp pop408 bytes, each with one call site inside its two-iteration loop.
These validate the analysis tool against existing evidence, not candidate fit.

## Actual blocker and limits

[verified] Hera was reachable for the earlier isolated-object experiment but
became unreachable before this full-fit task. Multiple bounded existing SSH
connections failed with timeout or IPv4 `No route to host`; the documented
IPv6 link-local alternative via en12 also timed out. en12 remained active at
10G. The coordinator independently reproduced SSH timeout after ARP resolved.
No power, network configuration, reboot or device action was performed.

**Neither full baseline nor full candidate build has started.** No remote
claim was acquired or remote checkout created for this follow-up. Do not
represent prepared drivers or historical-fixture analysis as completed builds,
current candidate RAM fit, measured performance, hardware acceptance or merge.

## Resume after host reachability returns

1. Re-read the coordination README; atomically acquire
   `claims/lunar--resampler-inline-fullfit-20261016` on Hera and write owner,
   session, UTC start, exact source/driver branch, scope and status.
2. Push `codex/resampler-inline-fullfit-20261016` from the Mac into Hera's
   exchange bare repo with an explicit refspec; verify its SHA. This transfers
   exact base86154, candidatee753 and driver commits through Git.
3. Create a separate detached driver worktree from the pushed branch. Run:

```
python3 notes/2026-10-16-resampler-inline-fullfit/build_pair.py \
  --output /home/claude/mvave-fm1/resampler-inline-fullfit-20261016
python3 notes/2026-10-16-resampler-inline-fullfit/analyze_pair.py \
  --pair-output /home/claude/mvave-fm1/resampler-inline-fullfit-20261016
```

If an external pin mismatches, inspect the original retained input/runner;
do not bypass it. A failed attempt leaves its output intact; choose a new
explicit output directory for a reviewed retry.

4. Inspect `linked-comparison.json`, full link logs/maps, guard slack and the
   exact Drums/SixOp/ready-pop prologues and calls. Add actual results/hashes to
   notes; commit/push/verify. Save the atomic shared handoff and release only
   this task's claim. Keep the branch isolated from root integration.
5. The coordinator reviews fit/codegen before deciding whether a concrete
   hardware trial is warranted. Offline codegen does not establish speedup;
   physical stack high-water and audio acceptance remain separate gates.

## Aeon migration checkpoint

[verified] Hera resumed long enough to complete baseline catalogue compilation,
then owner maintenance steering interrupted the link. Owned session
`engine-render-profile-dd8e3ac98e` was stopped; no running owned container remained.
Hera claim was released after atomic shared handoff. Candidate never started.
Those partial outputs will not serve as the matched comparison.

Aeon now owns unique claim `lunar--resampler-inline-fullfit-aeon-20261016`.
Frozen read-only stage-7 evidence was copied to
`/home/claude/mvave-fm1/resampler-fullfit-frozen-20261016`; active checkouts were
not used for source exchange. Exact sources are transferred through Git.
`run_aeon.py` derives from the pinned runner with only image identity, UID1003,
four concurrent shards and no-swap policy changes. Sixteen logical shards and
all compile/link flags remain identical. The Aeon image is pinned separately
at `sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`;
it differs from Hera's image and no cross-image binary equivalence is assumed.
Both fresh builds use this same image and frozen target compiler. Maximum is
8 aggregate CPUs/8GiB catalogue RAM, then a separate 4CPU/4GiB link.
