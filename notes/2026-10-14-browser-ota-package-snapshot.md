# OTA adapter package snapshot

[verified] The adapter previously passed a copy to the asynchronous verifier,
then hashed the caller-owned input after awaiting the verifier. Mutation during
that wait could make the package hash describe bytes other than those verified.
It now captures a plain Uint8Array before awaiting, passes a separate working
copy to the verifier, and hashes the captured snapshot. The logical image is
still copied and independently hashed before issuing an admission handle.

[verified] All 14 native OTA adapter Node tests passed. The added regression
pauses verification, mutates the caller's input, also mutates the verifier's
working copy, and checks that the handle retains the original package hash.
No ports or physical devices are used by this test. This change supplies no
package verifier and does not open browser package admission.

[verified limitation] Semantic tooling was checked: Rarefaction's TypeScript
root and Serena's active project both remain the primary Mac checkout,
`/Users/likwid/Developer/mvave-fm1-firmware`, rather than this integration
worktree. Serena reported only a C++ server. Shared selection was not changed
while other work is active; this bounded JavaScript edit used direct source
inspection and the existing adapter tests, not a claim of semantic coverage.
