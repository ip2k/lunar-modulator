# Draft: Computer Use reports automatic-unlock failure with Locked use enabled

Suggested destination: https://github.com/openai/codex/issues/32396

## Environment

- ChatGPT desktop app 26.1007.30912, build 20156.
- Computer Use helper 26.1005.1001425.
- macOS 27.0.1, build 26A434; Apple silicon (arm64).
- Settings screenshot supplied by the user shows Any App and Locked use enabled.
- Target: Packetry, a USB analyser application, launched with sudo through a local .app wrapper.

## Observed failure

During an active firmware-debugging task, I asked the assistant to use Computer Use to stop Packetry's capture. The app-selection call was:

```javascript
await cua.getApp('/Users/<user>/Applications/Packetry.app')
```

It returned:

> The Mac is locked and automatic unlock could not unlock it. Ask the user to unlock the Mac manually before continuing.

This blocked the assistant from seeing the window or clicking Stop. Earlier in this same workflow, I also reported that the Mac was unlocked while the assistant was receiving lock-related errors. That unlocked state was user-reported; the tool did not independently confirm it.

## Subsequent retry

On October 12, 2026, I supplied a screenshot showing Locked use enabled. After refreshing the Computer Use runtime documentation and retrying the same app-selection call, the assistant successfully obtained Packetry's accessibility tree and screenshot. It clicked Stop and verified that the toolbar control changed from a square to a play triangle. No permission-setting change was requested or performed between these adjacent attempts. Whether I manually unlocked the Mac between those attempts was not independently established.

## Expected behavior and impact

With Locked use enabled, eligible active tasks should operate through the documented guarded unlock flow. If automatic unlock fails or is temporarily suppressed, the error should distinguish that from incorrect configuration or a potentially incorrect lock-state determination, and identify an actionable failure stage.

This case interrupted an unattended hardware-debugging workflow and repeatedly required the user to return to the desktop despite having enabled Locked use. Ordinary Packetry screenshot and click control eventually worked, so the feature is intermittently failing rather than universally unavailable. Successful retry does not establish the root cause or prove that locked operation itself succeeded.

## Useful diagnostics

Please investigate lock-state detection, trusted-turn eligibility, local-input suppression, authorization-plugin interaction and post-unlock verification. The generic error does not distinguish these paths. No SecurityAgentHelper/authd logs were collected for the failing attempt, so this report does not assert a specific root cause or a sudo/GTK incompatibility.

Related report: https://github.com/openai/codex/issues/32396. This report was drafted with AI assistance from the actual tool responses; identifying local paths and hardware serial numbers have been omitted.

## Recorded time and token overhead

[verified] Local session telemetry was examined for this report. The cutoff is 2026-10-12T23:14:17.297Z. Subsequent editing, verification, commit/push and this reply are excluded; an exact self-inclusive final cost cannot be known before the final response finishes.

### Time impact

- 61 completed Computer Use calls returned the automatic-unlock failure. The first was 2026-10-12T08:22:15.425Z; the last was 2026-10-12T23:06:06.993Z. Packetry app access first succeeded at 2026-10-12T23:09:29.076Z. The observed failure-to-success window was **14 h 47 min 13.651 s**.
- The final explicit request for manual unlocking was sent at 2026-10-12T23:06:11.235Z. The user replied with the settings screenshot at 23:09:17.737Z: **3 min 6.502 s awaiting that reply**, and **3 min 17.841 s from the request until app access succeeded**. Stop was verified at 23:09:38.989Z.
- These are elapsed windows, not measured owner labor or continuous assistant idleness. Other firmware work continued during the wider window; the logs do not support attributing all elapsed time or all tokens to this bug. They also do not prove that the user manually unlocked the Mac before the successful retry.

### Token accounting

| Scope | Input tokens | Cached input (subset) | Uncached input | Output tokens | Total input + output |
| --- | ---: | ---: | ---: | ---: | ---: |
| Entire recorded session through cutoff | 312,839,791 | 302,731,776 | 10,108,015 | 1,445,873 | 314,285,664 |
| Original report interval | 1,073,834 | 1,008,000 | 65,834 | 2,694 | 1,076,528 |
| Accounting follow-up through cutoff | 323,442 | 311,552 | 11,890 | 1,461 | 324,903 |
| Report and accounting combined | 1,397,276 | 1,319,552 | 77,724 | 4,155 | 1,401,431 |

The original-report interval uses cumulative snapshots at 2026-10-12T23:10:27.580Z and 2026-10-12T23:13:34.766Z. The accounting interval runs from the latter snapshot to the cutoff; it includes calculating costs and preparing this accounting update. These interval totals may include concurrent continuation work and are interval-level measurements, not isolated per-document billing.

Input totals count context processed repeatedly on successive model requests; cached input is already included in input and must not be added again. Reasoning output is a subset of reported output and is not added separately. These totals are telemetry, not the amount of unique text written.

The separate goal counter reported **38,019,043 tokens** and **71,108 seconds** at the initial accounting query. Its scope/aggregation differs from the cumulative session telemetry; the values must not be summed or treated as equivalent billing counters.

**Monetary cost: unavailable.** This signed-in desktop session does not expose invoice amounts, an effective per-token rate, or a defensible bug-only dollar charge. Applying public API list prices to these subscription-session counters would invent a cost. OpenAI should correlate the recorded timestamps with server-side usage/billing and separate the 61 failed unlock attempts and resulting retry/context overhead.
