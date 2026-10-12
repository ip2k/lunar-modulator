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
