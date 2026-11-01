# Private package audit capability fixture — 2026-11-01

At `42604fb03dcece54c54b9b0151467ededa79ee0f`, the composer test assumed the current checkout lacked native audit capabilities. The real `check_native_audit` now accepts that checkout, so the test proceeded to `git ls-tree` with its synthetic `aaaaaaaa…` commit and failed with `CalledProcessError` [verified: focused RED run].

The test now writes an explicitly incomplete `audit_link.py` under pytest's temporary directory and calls the real audit checker through `_require_native_capabilities`. It requires the missing function/`--objdump` diagnostics and fails if native prerequisites or wrapper capture are reached. This checks the intended fail-closed ordering without depending on the checkout's current capabilities. No production gate or wrapper changed.

Focused composer test and three neighboring server capability tests passed (4 total) using the existing installer service Python environment [verified]. No native wrapper, Docker, device, full service, or package build was run. RED/GREEN logs and cleanup record are retained privately under `audit-20261101/package-capability-fixture/` in the performance scratch.
