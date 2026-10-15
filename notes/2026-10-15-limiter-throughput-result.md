# Limiter placement trial [verified]

Cold-boot owner acceptance failed: laggy scope display and distorted audio.
The matched limiter helper RAM-placement trial installed and read back target
`23150dca74404733e377a9c5c74ff883bfa2ef09d67b1f84c0650ccbd9474409`.
All 4096 final readback pages matched; 210 sectors changed, protected ranges
remained untouched and the directory was written last.

Across 109.223 device seconds, throughput was 498.576 blocks/s against a
492.191 baseline (+1.297%). Required throughput is 689.344 blocks/s. Underruns
remained 190.766/s. This change does not resolve the performance failure.
No active-note, song or listening acceptance is claimed for this passive trial.

The sole boot command had an ambiguous host acknowledgement. It was not retried.
Independent capture observed native USB108 and successful telemetry, followed by
timed recovery ROM109. Both capture children exited successfully. KA6 WAV is
180 seconds, six channels, 48 kHz, 32 bit; its SHA256 is
`5ee16cae63b7cdb3d86db93712a11bc57a7c3a213389a386ccc02e12f537e53a`.

Private artifacts remain in `scratch/c0-limiter-helper-result/` and on bench01
under `/home/claude/fm1-c0-limiter-helper-20f21059-20261015/rom107-c0-limiter-helper-cycle`.
That lifecycle is consumed and must never be relaunched.

Next: independently reviewed fixed-work flash/RAM execution diagnostic, with
fresh paired reads and a new one-use lifecycle. No clock adjustment is authorized
by this result; clock register words alone do not measure execution frequency.
