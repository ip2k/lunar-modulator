# musl math and string subset

[verified: source] Unmodified sources from the official musl repository,
https://git.musl-libc.org/git/musl, commit
`b1efda5b91735e33635376ca11c9b497a1c66e39`.
`inventory.json` pins every imported file. Retain COPYRIGHT and each source's
individual Sun, FreeBSD, Arm or MIT notice. This is a 66-unit portable subset,
not a port of musl's Linux libc or operating-system services.

## Decision

The native catalogue needs math and memory functions without JieLi archives.
Picolibc was evaluated from its official source at
`199839dcfd3f96ea2c72f44166ffa4972e7b4767`; its embedded focus is useful, but its
configuration/header machinery requires a new architecture port. For this
bounded integration, musl's generic sources compiled with a small header
adapter and no target assembly. This selection does not establish performance
on pi32v2; some single-precision routines use software double arithmetic.

The first-party `firmware/native/libc_compat/` adapter keeps endian constants
consistent with compiler macros, supplies internal string prototypes/aliases,
and separates toolchain gamma accessors and host math declarations from musl
internal kernels. The pi32 build maps musl __fpclassify to the toolchain
header's __fpclassifyd name. The original implementations remain unchanged.
Toolchain standard declarations are still used: no claim of independently
ported standard headers is made. No vendor archive is linked.

## Verification and limits

[verified] Sixty-two sources compiled on pi32v2 r3/mfprev1 with -Oz in sixteen
Hera containers. Their combined relocatable object has only fourteen compiler
arithmetic helper references remaining. It is not an executable device image.
Earlier missing-header/declaration failures are retained in private receipts.

[verified] Sixteen ASan/UBSan host shards compared 16,384 numerical rows against
host libm, with additional zero, infinity, NaN, subnormal and maximum-float
cases. Memory copy/move/set checks cover lengths through 512, sixteen source
and destination offsets, overlap and whole-buffer write canaries. Host objects
are renamed after compilation to avoid resolving the reference calls to the
candidate itself. Tolerances: float relative 4e-6, double relative 4e-13, with
small absolute floors; this is not exhaustive ULP, rounding-mode or exception
flag verification. The current memory test does not guard every logical source
end against over-read. Hardware ABI, timing and full-catalogue audio acceptance
remain necessary. Receipts: build/native-musl-evaluation-20261012 and matching
Hera directory. No FM1 command was issued for this campaign.

[verified: 2026-10-13] The subset now includes the float classifier and ASCII
atoi/isdigit/isspace sources. Sixteen target shards and sixteen ASan/UBSan host
shards passed after adapting locale declarations/macros. The _l ASCII predicate
entry points ignore an opaque argument; this is not a locale service. The native
application uses the ordinary predicates. Classifier checks span every float
exponent, both signs and selected mantissas; atoi checks remain within the
standard's representable result domain. Signed-zero tests now reject opposite
signs before applying a tolerance. Individual source bytes remain unchanged.
