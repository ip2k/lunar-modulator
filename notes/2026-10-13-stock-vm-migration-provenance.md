# Stock VM migration provenance

The local reference directory named `FM-1-RE-v15` is not proof that its storage
analysis describes V15 or the owner’s FM-1_092. Its README describes V13
analysis; `docs/io/09-storage.md` identifies the analyzed firmware as FM-1_009
[verified against current local reference files].

Treat record flags, CRC layout and storage functions from that document as
reported facts for the analyzed firmware, not verified FM-1_092 migration rules.
Do not implement a destructive migration from the directory name. Verify the
actual backup’s bank geometry and record structure first, retain a complete
bank export, and prove semantic migration plus byte-exact rollback. Expanded
layout approval does not waive these requirements. No hardware commands ran.
