# Bounded sequencer source review

[verified: root source inspection] Read all 242 lines of
`tools/bench_capture/lifecycle-v1/sequence-once.py`, SHA-256
`102f72e380393bcf3efa314810cf437dfaee1a3a957c603e2500c5b02ca3b5e5`.
This is a source inspection of the closed historical-root proposal, not
independent acceptance, fresh campaign authorization, or a completed whole-code
audit. No source pin or execution gate was changed.

The four authority pins remain `None`. `require_open()` precedes persistent
activity and process creation. The historical V3 roots must not be reused for a
new campaign; successful model tests do not supply the missing review receipts.

The launch path requires nonoptimized Linux root, owner-private direct
directories, empty wrapper runs and unused destinations. Closure checking hashes
the staged files, entry inputs, derivatives, wire validator and review receipts.
Each command preserves a durable exclusive intent before launching one synchronous
child with fixed interpreter flags, environment and working directory. Its exit
record retains nonzero results; no phase retry or outer timeout is implemented.
The chain marker is consumed before the pipeline runs. Interruption requires
inspection of descendants and capture receipts; an intent is not an exit record.

The pipeline preserves the original backup completion and ROM observation times
when checking the 120-second freshness bounds. It replays the canonical baseline
factory without invoking its reset opener, then installs and boots once. Boot and
native-read nonzero exits are retained before subsequent admission validates their
evidence; they are not automatically accepted as successful recovery. Native RAM
reading precedes the returned loader-backed backup and stock restore.

The completed restore check calls the canonical restore validator with frozen
campaign, command, result and journal hashes. Even after that check, the completion
receipt explicitly leaves stock boot, display observation and physical recovery
unverified. A stopped chain explicitly refuses to assume unchanged stock or cleaned
up captures and grants no automatic recovery.

Remaining gates: review the fresh root and recovery-plan proposal against the
current-reader source closure, retain and verify its full model rehearsal, obtain
independent acceptance, and run exact-head CI. The historical-root sequencer alone
is insufficient for hardware execution.

## Live check at this checkpoint

[verified: passive USB observation] Bench01 enumerated normal `4c4a:c755`
bus 1/device 8 with `/dev/snd/midiC2D0`; no UBOOT enumeration was present. No
physical power cycle was required and no FM-1 command was issued.

[verified: UI boundary] Computer Use again reported a locked Mac and failed
automatic unlock. The pending manual-unlock request remains unresolved; no
Packetry UI interaction or new capture is claimed.

[verified: CI] Run
[38301026217](https://github.com/ip2k/lunar-modulator/actions/runs/38301026217)
completed successfully with all 13 jobs on exact commit
`292f1d8a1f9f0d39b32c8404ed7ff81aecc3430d`. It does not cover later checkpoint
commits or activate the hardware sequencer. The V6k full rehearsal remained
running on Hera at this inspection.
