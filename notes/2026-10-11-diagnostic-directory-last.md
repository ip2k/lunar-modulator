# Diagnostic directory sector is written last

The raw diagnostic emitter's data-before-directory receipt must correspond to
actual flash operation order. The original transaction loop processed all
writable sectors in ascending address order; the application directory at
`0x4000` would therefore be first when multiple sectors changed [verified:
prior source read at `fc8e3414bef97041611bbf7463f0b277d4141185`].

`tools/fm1_flash_transaction.py` now accepts an optional keyword-only
`commit_sector` during offline transaction creation [verified: source]. It
requires an exact integer, sector alignment and membership in the authorized
ranges before creating files. The immutable plan records both `commit_sector`
and the complete derived `sector_order`; its digest seals both. The durable
journal also carries the order. Loading rejects a different or incomplete
sealed order, or journal/plan disagreement. A historical schema-1 plan with
neither field retains its original ascending order, and the default new plan
has an explicit null commit sector and ascending order.

Install and restore use that validated order. Every other authorized sector
is processed and verified before the designated commit sector [verified:
source control flow]. This is not atomic installation or permission to boot
an intermediate image; interrupted data writes may invalidate the old
application. It makes the documented final-directory step true without
changing the existing readback and recovery decisions.

`tools/fm1_bound_diagnostic.py` supplies `prepare_transaction(...)`, which fixes
the scope and chooses `raw.APP_BASE` (`0x4000`) as the commit sector. Its
actual-file policy loader rejects a diagnostic plan without that explicit
choice before touching a transport. The validation receipt reports the
sealed sector order and directory sector. The old Reader and D8000 scratch
writer allowlists were not changed [verified: authored-file scope].

Existing startup, fresh full-array equality, durable pre-mutation intent,
sector blank/program readback, final complete-array comparison and ambiguous
failure handling remain in place. Resume still reads the actual complete
array first and repairs differing authorized sectors; it does not trust a
journal progress cursor. Directory-last ordering applies equally to restore.

Focused tests cover invalid commit alignment/type/range before file creation,
sealed plan/journal order, install/restore directory-last commands, and
interruption before the first data command, after data verification, before
the directory command and after a directory command returns. Those eight
install/restore interruption cases deliberately change a previously verified
data sector before resume and require fresh complete-array readback and its
repair. Default and historical plan ordering are also checked, as are
re-sealed inconsistent plans and bound-policy rejection before transport.

This author checked Python syntax via AST parsing and `git diff --check`;
root owns the focused Hera tests, review, commit and push. No device opener,
hardware IO or physical acceptance occurred in this lane. Full hardware
acceptance still needs the actual diagnostic display, recovery entry and
byte-exact bounded restoration receipts.

## Root verification on Hera

All 156 focused checks passed in 16 parallel containers on Hera, with no skips,
failures, errors or OOM kills [verified: 16 JUnit, exit and inspect receipts].
The actual private original loader was supplied for the fixed-candidate pin
regression. Modules: loader profile, RAM recovery upload, UBOOT reads, flash
transaction, bound diagnostic, UBOOT restore and recovery campaign. Every
container was removed after receipt capture. No physical commands occurred.

The frozen archive is based on `bdbf2d397226e9dbc5711d411f916af6d00ab0da`
plus the six explicit source overlays below. SDK and physical-adapter work was
excluded. This is focused verification, not current whole-repository CI or
hardware acceptance. Private evidence is on Hera in
`/home/claude/mvave-fm1/fixed-loader-directory-20261011/`; the local summary
is `build/fixed-loader-directory-hera/`.

| Evidence | SHA256 |
| --- | --- |
| Source archive | `526e6e436378b168d5696d10fcde9f1c420d2b0ea74893d406257ddb1e3abc68` |
| 16-chunk plan | `53031ea5328e354604e082ed667679f0f047098b54e68e773d52d151bd54a5ac` |
| Container image | `7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d` |
| Aggregate receipt | `9d1e10056c8c25b592ed90f42c557e210d47bb2ba956f751dfb6d4e283beabfb` |
| tools/jieli/loader_config_profile.py | `9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8` |
| tests/test_loader_config_profile.py | `d9efd427a762b3719c615de1b49d2846ad7bffa094fc4e17b225ea6af23fd53f` |
| tools/fm1_flash_transaction.py | `d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908` |
| tools/fm1_bound_diagnostic.py | `25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36` |
| tests/test_flash_transaction.py | `528200a0455b90af509c3ae4a8b43a78ad52581eb5107f5d1d2abca6edfe0005` |
| tests/test_bound_diagnostic.py | `4f9532d7bb450eaee30204c09a18b69c1e6afb9f1a507cab877e2e27f8ce354a` |
