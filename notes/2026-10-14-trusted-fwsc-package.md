# Trusted offline FWSC package model

This change adds an in-memory composition path for a named fm1-092-d7000
candidate. It consumes an immutable build tuple and its complete artifacts,
checks the exact externally supplied SHA-256 trust anchor, validates the
controller receipts and every referenced catalogue/generated input, then
reuses the reviewed FM-1_092 nested replacement model and independently
reopens the outer FWSC checksums. It does not write a package file, invoke a
writer, or admit an install.

The public legacy model remains pinned to the historical Shapes8/Event-Horizon
app. The new adapter passes a separately trusted tuple's app digest explicitly
to an internal parameterized model path. Both existing FM-1_500 composer
examples now use that explicit parameter instead of temporarily mutating the
shared model's global pin; focused tests check the historical default stays
unchanged.

## Exact retained tuple exercised

The positive test used the private Hera build tuple at
/home/claude/mvave-fm1/combined-nor-target-20261014/out/companion-set.
Its tuple SHA-256 is
2005957ad3dfbb5e34030717c6f0045cb3c96265a24641b8c370f1c39d835a23.
The tuple selects fm1-092-d7000 / expanded-d7000, diagnostic runtime,
application identity FM-1_990, and recovery identity FM-1_000.

The tuple binds an 845,732-byte app with SHA-256
ba46bf0a4d1bda4d604223c658b141b4a9068e37f65afddd998af04d5296cfc8
and ELF SHA-256
bb69fad7cf662dce19dbf8b265657717d3606404134a1bb68f7635cc8ef48b61.
The build provenance SHA is
761df61c73c630dfa1a61a23ca9b21bdc92ff48279ff80e656bbe0fb809dacaa;
the catalogue manifest SHA is
af1462fc04d6a6614c4b2d5b417e43c2670361095ea1484a8b7b03e2e5fd0429.
The manifest's 167 objects were rehashed from the declared catalogue root.
Prepared profile raw bytes are separately checked against the tuple, while the
prepared profile's embedded digest is checked against the exact source profile
bytes. These are different digest conventions and are intentionally checked
as a chain rather than equated.

The original retained public FM-1_092 FWSC and complete unpacked reference tree
are used only as inputs to the existing bounded model. The package path checks
that decoded protected content matches the reference model and independently
validates outer header, entry-list, and payload CRCs. The final package is
returned to the caller as bytes in memory; file_written is false.

## Validation

Focused Hera tests:

  pytest -q -p no:cacheprovider --basetemp=/tmp/trusted-package-test tests/test_trusted_fwsc_package.py tests/test_package500_d7000_candidate.py tests/test_package500_continuous_d7000_candidate.py
  16 passed

Python byte-compilation and git diff --check also passed.

The package and report keep hardware admission, hardware testing,
installability, updater acceptance, and release admission false. The tuple
digest is only a cryptographic binding: a caller must receive its expected
digest from a separately trusted policy. The adapter does not establish that
policy itself.

## Limits and next gates

This is structural offline evidence for the pinned model inputs. It does not
prove stock updater acceptance, real loader relocation, physical flash
behavior, power-loss recovery, settings migration, on-device startup, runtime
behavior, or musical acceptance. The target tuple did not contain a source FWSC
or an install-admitted package. Do not distribute or install returned bytes
based on these tests. A separately reviewed package-delivery policy and the
owner's remaining transport/recovery and device acceptance gates are still
required.
