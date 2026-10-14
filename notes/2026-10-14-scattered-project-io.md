# Scattered project IO adapter

The candidate layout separates the second 48 KiB project slot around the
20 KiB rescue stage. `firmware/native/extent_io.h` supplies a bounded logical IO
adapter without building in addresses or granting physical access. Extents and
protected ranges are explicit, aligned policy inputs; overlap, overflow and
out-of-range operations are refused before backend IO. Failed initialization
disables the adapter. Callers must avoid aliased initialization inputs and supply
the device page constraints and project format validator.

[verified] Hera ran `tests/test_native_extent_io.py` and
`tests/test_native_rollback_cutpoints.py`: four tests passed in the pinned
`lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
container with networking disabled, two CPUs, 2 GiB memory, 3 GiB memory plus
swap, and `docker-batch.slice`. The C adapter test used ASan/UBSan and strict
compiler warnings. Independent read-only review found no arithmetic/bounds
defect under the initialized-state invariant.

[verified] The C test connects these callbacks and a caller-owned validator to
the real `project_store.h`. Two maximum-size synthetic bodies were committed
into logical 48 KiB slots, including a body crossing physical extents. Reads and
programs split at the gap; all protected-byte sentinels stayed intact. Injected
partial erase and partial program failures retained the previous committed
generation. A second-extent read error terminated the operation. Geometry tests
cover overlap, physical overflow, protected overlap and invalid logical ranges.

Limits: this is a host mapping/journal test, with a synthetic format validator,
not real project decoding, pi32v2 compilation or flash durability proof. No
runtime save service binds the adapter to hardware. Storage ownership, opaque
stock-data migration, rescue staging, target behavior and exact-stock rollback
remain separate admission gates. The candidate addresses appear only in the
mock test. No device commands or writes occurred.
