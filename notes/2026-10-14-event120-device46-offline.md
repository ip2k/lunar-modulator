# Device 46 Event120 repeat adapters (offline preparation)

[verified] Based on source commit `dab9daae8f0d40d663b835ddb5f4dc241c914ba8`, this change adds device-specific read and one-shot boot campaign adapters for the passive USB enumeration `1-1`, bus 1, device 46, VID:PID `4c4a:8057`. It does not access the bench or device.

[verified] The read adapter uses fresh, exact device-46 snapshot and campaign kinds, an enumeration-bound one-use marker, the pinned fixed-loader/read/profile/inventory sources, and requires two complete 1 MiB dumps to match SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. The boot adapter pins the new reader source at `fe5b3d4fcf8650a4e7e0a83683fc3bf63751065ac3bc73dd35e791d0453e3636`, verifies its receipt and current flash identity, and preserves the exact one-shot FC0C request bytes `fc0c00000001ffffffffffffffffffff`. Ambiguous completion is latched without retry. The adapter records boot observation and physical recovery as false.

[verified] The existing device-44 campaign and all shared fixed-loader/profile/source pins are unchanged. Device-46 evidence cannot satisfy the old device-44 campaign, and device-44/42/45 enumerations are rejected by the new tests. This avoids accidental reuse of receipts or one-shot markers across devices.

[verified] Before this addition, the repeat adapter templates were device-44-specific. The new files give device 46 its own identity, evidence schema, marker namespace, and source-hash chain while preserving the same narrow read and exact one-shot request contract. During review, stale inherited device-44 docstrings, error text, and test names, plus device-42 messages and a Device44Reset class name, were corrected; the dependent reader hash pin was recalculated before tests.

[verified] Focused command ran in the bounded, network-disabled Hera container:
```sh
docker run --rm --network none --cpus=1 --memory=2g --memory-swap=2g --pids-limit=256 \
  --label codex.task=lunar-event120-device46-offline --cgroup-parent=docker-batch.slice \
  -v "$wt:/src:ro" -v "$venv:/pytest-deps:ro" -w /src \
  -e PYTHONPATH=/pytest-deps -e PYTHONDONTWRITEBYTECODE=1 \
  lunar-preload-tests@sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313 \
  python3 -m pytest -p no:cacheprovider -q -rA \
  tests/test_event120_device46_repeat_read.py tests/test_event120_device46_repeat_boot.py
```
Result: 21 passed. The test log is stored outside Git at `/home/claude/.local/share/codex-coordination/receipts/lunar-event120-device46-offline/pytest.log` (SHA-256 `57fd3a989946c6b31562459e0b0812c6a431ab672b0af0353101741630d7cdbe`). The focused Python syntax compilation also passed.

[verified] No USB, MIDI, flash, reset, power, or device commands were run. Tests exercise offline preparation/refusal and a mocked one-shot contract only. A fresh live device-46 paired read and its current USB/SG evidence remain required before root may use the boot adapter; this commit does not establish current identity, boot, installation history, or recovery.
