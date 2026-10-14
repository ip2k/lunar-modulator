# Fresh native ROM recovery reads

[verified] On 2026-10-13 Pacific, passive enumeration found the owner bench
connection at USB path 1-1, bus 1, device 36, VID/PID 4c4a:8057. The existing
reviewed native ROM adapter and its three pinned dependencies matched staged
source hashes. No earlier device-36 consumption marker existed. A new passive
observation was recorded immediately before successful preflight and execution.

[verified] The pinned fixed RAM loader completed the exact 8,757-operation
INQUIRY/upload/jump/read inventory. Both durable full-flash backups are
1,048,576 bytes and independently hash to
`770fd5f275110f017329dda30315343d766ff4a6c6beaa62f5a0060c629dc561`,
the previously installed Trio controls image. All completion indices were
checked in order, with no status, residual or sense errors. There were zero
flash erase/program operations, zero resets and no retries.

The exact campaign SHA256 is
`cf0a82de9a874326ded97c100bf694cbaa3b09cb24c8a568368a53526601bdc4`;
adapter SHA256 is
`ad32f89f7502e99fa54862478553d0f9cac981d5546653dad17604b23270e2c6`.
The physical enumeration is now consumed and running the RAM read loader;
do not replay the ROM upload or reuse an older installation/boot admission.

Private campaign, command log and vendor-derived flash bytes are retained in
ignored `build/native-returned-rom-036-20261013/` and on bench01 under
`/home/claude/fm1-fresh-rom-20261012-source/native-returned-rom-036/`.
These reads establish fresh chip/ROM and installed-byte evidence, not a fresh
normal-app identity reply, physical full-image rollback, settings migration or
thirteen-engine hardware acceptance. No firmware change or boot was attempted.
