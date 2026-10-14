# Two-project custom image: real target link

[verified, offline target link] A real container worker built an ordered pair
of `legacy-example-packet-bloom` and
`replacement-showcase-candidate-event-horizon`, startup index 1, from source
`a2463d83abcaba939884972a24932f1e6af6cb8f`. With all thirteen production sound
engines and all effects/MIDI/modulation modules selected, the linker refused
the image: XIP overflow 1,248 bytes. No successful artifact receipt was produced.

The same request with only Plate deselected linked successfully, preserving
both authored projects and every module they reference. This is a custom
selection case, not a change to the default thirteen-engine image or its
effect selection. The native project chooser is not in this source baseline.

| Evidence | Value |
| --- | --- |
| Selected modules | 54, including all thirteen sound engines |
| Application bytes / budget | 867,564 / 868,836 |
| Remaining application bytes | 1,272 |
| App SHA-256 | `7ee7e719b8b77e150fc507e8887de5b47842c7fa8da36216ed3e8ca6864a594a` |
| ELF SHA-256 | `ea397fb034e3fb322d401d67f9e74d048371066b296e00525362f00d16e20632` |
| Request SHA-256 | `b52d9e846f67abe4dd187754e25f558543d7c8dcd8bd9a79c791ce5d5077a561` |
| Prepared profile SHA-256 | `91a6d1ca4600eb248f7c9d7fb9ce0a1cc073e32b94ca84cba5fc51309c2263b2` |
| Image receipt SHA-256 | `ca7d720d7ad4968f6ac4e4d4298056040c8a405ef689b9868bcfe1327b0b1c80` |
| Packed project bytes | 7,801 + 4,345 = 12,146 |

Private Hera artifacts: `/home/claude/mvave-fm1/two-project-real-build-20261014/`.
Exact source archive, worker and custom request are in `input/`; failed full
selection in `build-v3.log`; successful custom link in `build-no-plate.log`;
`app.bin` and `image.json` in `result/`. Coordinator copied both outputs into
ignored `build/two-project-check/result/` and independently checked artifact
hash, byte count/budget, ordered project IDs, startup index, module count,
Plate exclusion and false admission flags. The remote request now describes
the successful case; the full-selection request is retained locally as ignored
`build/two-project-check/request.json`.

Execution: immutable image
`lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
read-only fixed catalogue/toolchain/source mounts, network disabled, UID/GID
1001, dropped capabilities, 4 CPUs, 8 GiB memory and memory+swap, 512 PIDs,
3 GiB scratch tmpfs and `docker-batch.slice`. Catalogue:
`all13-fullsong-link-comparison-v1/catalogue-z`; toolchain:
`sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`.

The controller verified expanded-D9000 layout, completed key audit, selected
content/profile identity, and fresh compact SAVE codec replacement. SAVE remains
disarmed. Runtime is the bounded 20-second diagnostic. The receipt leaves
installability, hardware admission/testing, native RAM/playback and full-song
default acceptance false. No device commands or writes occurred. This proves
a custom multiple-project link, not on-device selection, playback, persistence,
browser installation or public release.

Next: link the cold-boot selector against this exact configuration and the
one-project default; verify per-project startup/allocation and full-song playback;
complete persistent rescue, migration/rollback and physical acceptance.
