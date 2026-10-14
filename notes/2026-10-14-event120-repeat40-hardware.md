# Event Horizon repeat boot from device 40

The owner approved Event Horizon Showcase as the default full-song project and was available to watch this repeat test. This note records the bounded diagnostic, not release or continuous full-song acceptance.

- [verified] The reviewed reader at `b0db316372ca65e92b20a097480e2a8f81c1d995` completed 8,757 fixed commands with zero flash and reset operations. Two complete 1,048,576-byte reads both hash to `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`, the expected installed target.
- [verified] Read manifest SHA-256: `87eb0ff98d242b173cca8e89431fbaf11d69aa3c93140f34a1ff2a7a9d745497`; commands SHA-256: `cd624444ea3f0cc9b063464b0010621b335f534c0e8fb99d889ec2301f06d325`.
- [verified] A fresh passive snapshot retained the same device-40 USB/SG identities. The initial coordinator comparison stopped before producing a boot campaign because Python tuples and decoded JSON lists compare differently; canonical JSON comparison confirmed identical values. This was not a device command or boot retry.
- [verified] Boot preparation replayed the complete read bundle and pinned sources. One `FC0C` argument-1 request (`fc0c00000001ffffffffffffffffffff`) was submitted at Unix time `1792004286.109491`. Completion was ambiguous: host 7, residual 16, info 1. The adapter consumed authorization first and did not retry.
- [verified] Passive enumeration afterward showed device 41, `1209:0001`, matching the native application USB identity. This is USB activity evidence, not screen, controls, audio, or recovery acceptance.

Private evidence remains at `/home/claude/fm1-device40-event120-repeat-20261014` on bench01. A local ignored archive is `build/event120-repeat40-private.tar`; refresh after passive monitoring finishes. No vendor image, flash dump or private receipt is committed. Owner observations and final recovery enumeration are pending at this checkpoint. Do not reuse the consumed campaign; any future request requires a separately reviewed fresh connection/evidence policy.
