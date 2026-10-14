# FIRST ORBIT diagnostic boot — 2026-10-14

[verified] Owner approved Event Horizon Showcase as the default full-length song and was available to watch. This boot exercised the already installed FIRST ORBIT twenty-second diagnostic, not the Event Horizon two-minute candidate.

[verified] The completed 213-sector installation proof was replayed offline before the boot; its complete target SHA-256 is `c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903`. Fresh passive mapping matched the original device36 loader connection. A new one-use campaign passed preflight. No upload or flash operation occurred.

[verified] One FC0C arg1 command was submitted. Campaign SHA-256: `e39897f8a56f89b4ed48a8b59420172dffe049bced47edbf504f6c830e884faf`. The adapter stopped ambiguously because its post-submit check required the old SG node after that node disappeared. It was not retried. Private copied receipts are in ignored `build/native-first-orbit-boot-20261014/`; the source receipts remain on bench01 under `/home/claude/fm1-expanded36-source-20261013/native-first-orbit-boot-20261014`.

[verified] Passive enumeration after submission saw native USB `1209:0001`, bus1/device37. A later passive check saw mask ROM `4c4a:8057`, bus1/device38. This establishes the USB transition and timed return. Owner screen/audio/control observations remain pending; no full-song acceptance, physical interrupted-write recovery, or release admission is claimed.

Next: retain the consumed campaign; never replay it. Establish fresh device38 loader/read evidence with the exact installed-image binding, prepare and independently review the two-minute Event Horizon candidate and rollback plan, then announce its watched boot only after installation/readback gates pass. The new ROM enumeration invalidates prior device36 loader admissions.
