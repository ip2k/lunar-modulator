# Optional private native fixture and required CI

Required CI run [38266651469](https://github.com/ip2k/lunar-modulator/actions/runs/38266651469)
on eb79d33982423f392d5b394d6ad5b1be998a1943 failed the macOS and Ubuntu
Python jobs with 71 `KeyError: LUNAR_TRACE_NATIVE` errors each. The other 11
jobs passed. These tests need private pinned native ELF/app/build-manifest
files; publishing those artifacts is not an appropriate CI fix. [verified]

The shared native fixture now skips when the build path is omitted and
private fixtures have not been required. `LUNAR_REQUIRE_PRIVATE_FIXTURES=1`
keeps missing files fatal. An explicitly empty path, invalid required flag
or nonexistent build fails as well. Artifact byte reads, exact plan pins,
ELF geometry and corruption rejection are unchanged. Five selection cases
exercise these boundaries. [verified: source and modeled test execution]

Hera ran both affected modules against source archive ec2fd439 and fixture
source bca98417 using pinned image 7e32dd6d. The clean configuration passed
111 cases and skipped exactly the 71 prior CI error nodes. With exact native
files mounted read-only, all 182 unique cases passed in 30 parallel chunks,
zero skips/failures/errors; one smoke test also passed. The 33 containers had no
network, device passthrough or privilege, with 2 CPU/2 GiB RAM constraints.
Inspection and removal receipts plus a final empty label query are retained.
[verified: XML, invocation, inspection, removal and cleanup receipts]

Ignored evidence: `build/native-fixture-ci-v1/`, summary archive SHA256
`12aeed98a67c1dc8c899e8e1f86db5db5a9c9f1996718dfa1490672e90dd74fb`
(266 regular members), root-runtime-check.json. Hera directory:
`/home/claude/mvave-fm1/native-fixture-ci-v1-20261012`.
Independent review `independent-review.md` (SHA256
`7491dbe822ad229bbf00b4ec337f50c2c0ba46308aa187fc58837a56b1ae7c73`)
and `independent-check.json` (SHA256
`6d5ebecf05b9a600025de8942b41377f1ba9af341b5a6068c617ae4cb0861db0`)
accepted the source boundary, exact fixture hashes, all XML results, container
isolation and cleanup receipts. [verified: independent retained-evidence review]

These are fixture-selection/native transport models; no hardware opener,
CPU emulation or physical acceptance is claimed. Required whole-repository
CI must still pass on the new exact pushed head before integration.

Semantic tools remain selected on the shared primary checkout, where this
worktree's fixture is absent. Bounded queries could not find it; file
inspection was used without retargeting another active session. [verified]
