# Version/trailer evidence and runtime handover preparation

2026-10-09. Personal MIT stream `chore/2026-10-09@version-trailer-contract`,
stacked explicitly on PR #115 `5e309ea`; integrate after that stream.
No device traffic, container output or installation occurred.

## Concrete offline guard

`tools/jieli/inspect_version_contract.py` validates the strict stock V15
nested/component profile, then requires one matching NUL-terminated app
identity, observed UFW header fields `[4, 512]`, the exact 64-byte opaque
trailer hash, and its observed type/record/size profile. It emits a new JSON
report only and refuses report overwrite. Matching these fields establishes
an offline observation, never device acceptance. Neither a version override
nor a firmware-output option exists. The inert diagnostic remains unchanged.

Actual stock V15 passes [verified]: FWSC SHA-256
`db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a`,
markers `FM-1_015`, exactly one `FM-1_015\0` at app offset `0x4ea64`.
The flat inert diagnostic has no such literal or update service; it must not
be represented as an app that can supply a post-install identity response.
The outer marker identity is a container field, not a runtime service.

## Trailer comparison and exact remaining boundary

Compared locally saved original packages, not filenames as version evidence:

| File/provenance | Decoded marker identity | Physical bytes | Logical tail offset |
| --- | --- | ---: | ---: |
| `scratch/FM-1_updater.fwsc`, carved M-UPGRADE | `FM-1_014` | 704052 | `0xabde0` |
| `scratch/FM-1_v15_cdn.fwsc`, saved stock CDN | `FM-1_015` | 699956 | `0xaade0` |
| `scratch/baudgirl-2026-09-29/fw/V15.fwsc`, saved installer reference | `FM-1_015` | 699956 | `0xaade0` |
| `scratch/baudgirl-2026-09-29/fw/FM-1_092.fwsc`, saved installer | `FM-1_092` | 810548 | `0xc5de0` |

All four 64-byte `tail.bin` payloads are byte-identical [verified], SHA-256
`79d4bbc325be8b2f49492a9e8bf712e3cfe4e7c55e874dced1445ed65616843b`,
CRC `0x8936`, type 255, allocation 64, record unknown16/44-byte extra all
zero; the last 16 bytes contain `JLUFW` plus eleven zeros. Header unknown16
4 and unknown32 512 are identical [verified]. Their meanings remain unknown.
Different app/image contents sharing this payload is evidence against treating
it as an established digest of each whole application [inferred]; it does not
prove any particular authentication, compatibility or loader policy.
The safe offline contract is exact preservation, not a guessed tail repair.

V14 and V15 `script.ver` decode to
`AC791N-v0.01-cfg_tool-v0.10` [verified]. FM-1_092 keeps the same auxiliary
ciphertexts at shifted offsets and fails the existing strict origin-zero USR
CRC check; this stream does not accept it or add an origin fallback. Its tail
comparison is a bounded direct slice comparison, not successful inspection of
the entire 092 package. `blimit.bin` differs between V14/V15; its role remains
opaque and the replacement model preserves it byte-for-byte.

## Version acceptance evidence is version-specific

The marker transform is separately observable in saved containers: twenty
47-byte data slots plus a marker byte per 48-byte physical slot; identity byte
`i` is stored as ASCII value plus `i+1`, with remaining marker bytes `0x7d`.
AL-255's client and updater analysis independently describe the field and
post-reboot model/decimal-version parsing [reported:
[FM-1-RE OTA protocol](https://github.com/AL-255/FM-1-RE/blob/main/docs/io/11-ota-protocol.md),
local `reference/FM-1-RE/tools/fm1_ota.py`]. No transport was run here.

That protocol note's V13 investigation reports cfg-header no-op rejection and
a remaining OTA gate after changing identity and repairing CRCs. It also
reports successful stock version-10-to-8 downgrade in a saved log, which
does not establish recovery from an app without an update service. A new
version alone must not be described as proven sufficient. The V13
observations do not establish the V15 or owner's installed FM-1_092 decision
path. Other reported successful modified V15 installs remain source-specific
reports, not evidence that this 200-byte inert app is accepted or observable.

The inspected external browser repacker has a `cfgBump` option that changes
eq filename padding/CRC. This project does not adopt that change: cfg is an
explicit byte-preservation guard, so a loader policy requiring such a change
would require a separately reviewed contract rather than a silent bypass.

## Runtime preparation and next concrete experiment

Stock SPL static handover and mapping evidence is in
`notes/2026-10-09-stock-app-mapping.md`; the separately reviewed SPL note
records call/boot-info/watchdog details. Startup presently sets only SP and
does not dereference incoming r0. Its RAM reservation overlaps the loaded
SPL body and is a link-time budget, not verified private board RAM.

A next startup variant must preserve the inert target and independently own
SP **and SSP**, copy the six-word boot information before any initialization
that may destroy it (zero extensions, preserve its separately copied header
only under a verified consumer contract), and remain non-returning with no
calls into overwritten SPL RAM. Keep inherited XIP/cache/SFC configuration
until its exact required transition is established. CLI/SSP instruction
encodings and r0 call behavior need fresh vendor target disassembly, not
host clangd. The unresolved SPL callback, core/IRQ/exception ownership,
clock/power configuration and final watchdog state remain gates. An SSP
reservation alone does not establish a valid exception vector policy.

No existing output driver is evidence of safe LCD startup on this unit.
After exact clock/power/GPIO/SPI register checks against pinned WL82 SDK and
stock trace, the narrow observable variant should show a fixed screen and
never start audio, USB update or the sequencer. A device experiment must use
a reviewed exact candidate/write range and fresh backups. Full-image and
broken-app recovery remain untested, a specific risk under the owner's
staged policy, not a blanket ban inferred from offline work.

## Reproduce and handoff

```sh
python3 tools/jieli/inspect_version_contract.py /path/to/stock-v15.fwsc \
  --stock /path/to/guarded-stock-tree --json /path/to/new-report.json
```

Actual ignored report: `build/jieli-diagnostic/version-contract-report.json`.
Focused synthetic tests cover absent/mismatching/ambiguous app identity,
valid-CRC trailer-record changes, opaque-tail mismatch and metadata changes.
Opt-in actual-stock test confirms the literal offset/hash. Rarefaction's
original-root symbol query returned no new tool symbol; Serena reports only
C++ active and cannot navigate Python here. Bounded source inspection and
actual parser tests provided the evidence; neither semantic failure is
presented as a successful check.

Parent owns CI/review/integration. The version/trailer guard is complete for
observed stock V15 only; no device acceptance or distributable container
claim follows. Continue with exact startup/observable-output ownership and
the version-specific loader decision path before changing the output policy.

## Change log

- 2026-10-09: Compared saved trailer/marker profiles, implemented JSON-only
  evidence guard, corrected version acceptance scope, persisted handover plan.
