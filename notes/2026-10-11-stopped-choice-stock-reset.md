# Distinct stock reset after stopped-choice recovery

2026-10-11, feature/2026-10-11@installable-firmware. Root owns hardware,
commits and verified pushes. This is a closed successor, not a physical result.

[verified: source inspection] `tools/fm1_stopped_choice_stock_reset.py` uses
unchanged reviewed one-request mechanics from `fm1_fixed_loader_reset.py`
dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116,
backup bridge79bbe99c and native reader28317ee5. Its completed-restore dependency
is the distinct new `fm1_stopped_choice_stock_restore.py`; the source pin remains
None and the factory rejects before campaign IO while it is closed.

The schema1 kind is `fm1-stopped-choice-fixed-loader-stock-reset`; state is
`stopped-choice-fixed-loader-stock-restored-no-later-commands`. A new direct
receipt and `.stopped-choice-stock-core-reset.consumed` marker preserve old
origins. The prepared event is `stopped_choice_stock_reset_prepared`; the native
intent/completion events retain the reviewed reset kernel's schema. The exact
FC0C argument1 CDB is `fc0c00000001ffffffffffffffffffff`, IN16, no upload,
flash/read probe, retry or automatic identity request.

The factory requires the completed new restore validator, full stock baseline
96006a51, original targetdf6c963e, 30 sectors and directory-last order. It freezes
all returned positive and negative evidence. Exact factory instances and a
one-use opener permit gate SG discovery/open only after durable consumption.
Receipt and marker admission use lexists so broken symlinks are occupied.
A detach or ambiguous reply retains consumption and makes no boot claim.
Physical normal enumeration and identity must be checked separately.

[verified: syntax only] Sourcec0a75545faa6d14a2ff03d706ad9257c60bbcfec9061e6590bc2b3e73edb9995
and tests8e433ea49c22c29b24d780ab267f23ca33ec60de04f61d122d3d1c2cfef7412d
parse. Focused tests reuse the actual pinned protocol/syscall mock and cover
one-request framing, lost replies, durable-intent failures, connection changes,
copy/permit rejection and negative evidence, adding closure before IO and broken
symlink admission. Hera16 and independent review are pending. Genuine completed
new backup/restore composition is a later separate gate; no physical execution
has occurred through this new adapter.
