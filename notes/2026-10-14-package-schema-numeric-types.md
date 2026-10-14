# Strict numeric package schemas

Independent continuous-tuple review identified Python's `True == 1` comparison
as an input-validation gap. [verified: source] The offline packager now requires
`type(value) is int` for the build tuple, catalogue and provenance schema fields
and the build request version, in addition to checking the supported value.

Negative tests supply boolean, floating-point, string and null values. The
tuple/catalogue tests use matching digests; retained provenance/request tests
rebind earlier receipt hash crosslinks so refusal must come from the numeric
schema check. Valid integer schema 1 remains accepted by existing tests.

Mac pure-policy checks passed; retained artifact cases skipped because their
private Hera fixtures are absent locally. Full retained-fixture verification
on Hera is pending at this checkpoint. No firmware admission or device command
is changed by this validation fix.
