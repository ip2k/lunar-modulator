# Exact SDK trace Linux transport successor

Parent authorized a distinct minimal SG transport after independent acceptance
of the frozen reader `f4dc8706b0db9844c3b0913fe39ea3b502dfe1e89af5e4ec75ada11ae84df018`.
Implementation awaits that review. No hardware action is performed by this
subtask. Existing SG, backup, reset, install and firmware source stays frozen.

The planned transport reuses only the reviewed MIT mapping function from
`fm1_fixed_loader_backup.py` (`79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`)
and SGHeader framing from `fm1_uboot_read.py`
(`28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57`).
Their factories are never called and neither command inventory is changed.
Actual reader/boot source pins must be accepted before activation.

An envelope supplies exact native ELF/application/manifest files, a fresh quiet
initial-ROM snapshot, and a private new receipt path; an independently registered
canonical boot-lineage object is passed separately. Exact-byte private loading
of the reader preserves its own instance registry. Preparation does not discover
or open a device. A runner-only one-use permit allows opening only after the
reader writes its consumed marker, plan, campaign and read-prepared journal.
Every ioctl follows a separate durable fixed submit intent.

One direct character descriptor is opened with O_NOFOLLOW/O_CLOEXEC/O_NONBLOCK,
held with nonblocking exclusive flock. Full same-port USB/sysfs mapping and
fstat identity are checked before every fixed SG_IO 0x2285 request. Only INQUIRY36
and the two exact native FD07 requests repeated once are admitted, with IN
framing, empty OUT, bounded buffers and 3000ms timeout; no reset/upload/NOR or
retry. A completion is returned before the outer reader's post-I/O binding check
so actual status/sense/residual/length evidence survives a rejection. A separate
fsynced native journal records actual ioctl exceptions and errno. Advisory
flock cannot exclude unrelated tools; the required quiet-state assertion and
external owner discipline remain necessary.

All syscalls will be modeled in new tests, including pointer framing/status,
short/residual/sense failures, changed mapping, timeout, malformed operations,
copy/replay, opening/lock/ioctl/close failure and durable consumption ordering.
Tests belong on Hera in 16 isolated chunks with the same pinned image and
constraints as the reader. Runtime model success will not establish ROM RAM
retention, new-range physical acceptance or CPU cause.
