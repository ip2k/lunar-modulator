# Strict numeric package schemas

Independent continuous-tuple review identified Python's `True == 1` comparison
as an input-validation gap. [verified: source] The offline packager now requires
`type(value) is int` for the build tuple, catalogue and provenance schema fields
and the build request version, in addition to checking the supported value.

Negative tests supply boolean, floating-point, string and null values. The
tuple/catalogue tests use matching digests; retained provenance/request tests
rebind earlier receipt hash crosslinks so refusal must come from the numeric
schema check. Valid integer schema 1 remains accepted by existing tests.

[verified] Mac pure-policy checks passed; retained artifact cases skipped because
their private Hera fixtures are absent locally. Hera then tested exact source
6360dd57262eb3b4bdbcf4f0a202f15aab573938 with the retained D7000 tuple, catalogue,
source FWSC and full stock reference mounted read-only: 20 passed, zero skipped,
exit zero. The pinned Python 3.12 image was
sha256:a2be656a55327f06b955781df241217e1da23a2fcef52040479dab8a8793e8fa.
The raw log is /home/claude/mvave-fm1/package-schema-check-20261014/pytest.log;
shared handoff lunar--package-schema-check-20261014.md records the isolated
worktree and limits. No firmware admission or device command changed. This
retained diagnostic verification does not establish fresh continuous-package
or hardware acceptance.
