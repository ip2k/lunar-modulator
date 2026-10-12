# Editor milestone CI contract repairs

The source at baseline `8ff54529` exposed two omissions and several stale
contracts [verified]. The four native transport verbs parsed and executed but
had no host formatter names; the same verbs also lacked manual descriptions.
The formatter now round-trips pause, resume, rewind and seekbar, and the manual
states their actual native behavior. This changes host tools only; the Wasm
application does not depend on this formatter [verified: build source list].

Updated contracts keep the existing limits [verified]: four-track instance
18192 bytes, eight-track instance 32080 bytes, 36628-byte sequencer allocation
under its 36864-byte bound, and the 4612-byte MIDI mapping allocation in the
simulator's fixed RAM accounting. The arp refusal fixture replaces Limiter with
Ensemble so the initial chain still fits and enabling the arp exceeds the same
387924-byte budget; the test asserts both inequalities and the refusal popup.

Static checks now read CI's actual shell loop/direct test invocations, recognize
synchronous worklet message handling, and narrowly exempt the sequencer's song
capacity expression from the modulation-source-number guard. Other source-ID
and layout checks remain active [verified].

Validation [verified]:
- Local focused static/manual/native track-name checks: 7 passed.
- Hera isolated source stage `/home/claude/mvave-fm1/ci-contract-repairs-20261012`:
  complete test_seq_render, test_seq_ui, test_sim_mod, test_sim_multi and
  test_sim_arp files: 308 passed, 6 skipped (existing optional coverage).
- Same Hera stage with `FM1_GPL_MODS=0`: all 25 focused renderer/formatter,
  fixed-RAM, multi-chain and arp-boundary checks passed.
- `git diff --check`: clean.

This subtask does not establish full CI, browser acceptance, deployment or
hardware acceptance. The parent editor milestone must integrate this commit,
run its combined review/CI gates and finish the authorized merge/live checks.
The isolated native render tools must be rebuilt after integration because the
host formatter changed. No device write or vendor binary was involved.
