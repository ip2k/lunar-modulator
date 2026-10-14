# Linked application flash usage

The private diagnostic build summary now returns the validated linked image's
application budget and remaining bytes alongside its actual byte count. The
browser requires integer values, a bounded capacity and exact subtraction before
displaying used / capacity / free space. This measures the application region,
including selected compiled modules and embedded projects; it does not describe
free settings storage or prove RAM fit, hardware operation or installability.

Focused browser/client tests: 17 passed locally. Includes missing capacity,
over-capacity images, inconsistent free space, fractional and excessive limits.
Service tests and desktop/mobile visual verification are pending on Hera at this
checkpoint. The service fixture assertion verifies capacity and subtraction from
the actual returned application bytes.

Semantic navigation limits: Rarefaction selects the primary checkout and rejects
the active external worktree; Serena's shared primary connection only has C++
enabled and cannot inspect the service Python file. File inspection was used;
no shared project configuration was changed during concurrent work.
