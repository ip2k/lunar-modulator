# Adapted demo sequence and app-startup validation

This is a host-side diagnostic receipt for the scene-label compatibility adaptation at base `c5a15c1723692bca450cc8a5fc0990d154f01d1c` (branch `feature/2026-10-14@demo-scene-label-adaptation`). The source adapter changed only four scene display labels; `tests/test_native_demo_scene_label_adaptation.py` reverses those substitutions and verifies exact original bytes, then packs and imports the adapted Event Horizon and Packet Bloom files through native sequence staging with canonical SET equality and zero refusal/drop/eviction/fault counters.

## Exact test overlay and invocation

The test source tree was the adapted Hera scratch checkout at `c5a15c1723692bca450cc8a5fc0990d154f01d1c`, overlaid with the authoritative current test files below. The C harness was unchanged from the root commit. No production source or demo asset was changed by this rerun.

- `tests/test_native_demo_app_startup.py`: `f48cd0d445d02a8937ea4f7706680cddd7b03392a390e3d2128188ef0bf05ec9`
- `tests/test_native_demo_scene_label_adaptation.py`: `a7bab7e1417a9fb16afb2194c7697a1718581f6dfccfcca7e173c648962b75f2`
- `tests/native/demo_app_startup.c`: `4141aebe6b1733c0025bec6d6b1fc8255ca629ba3b78e877298f153580bc5a96`
- `tests/test_native_image_catalogue.py`: from the adapted base; its 30 parametrized cases were included.

Executed in the pinned Hera container with network disabled, `docker-batch.slice`, 4 CPUs, 4 GiB memory and swap, and `/tmp/check-venv/bin/python`:

```sh
pytest -s -q -p no:cacheprovider tests/test_native_demo_app_startup.py tests/test_native_image_catalogue.py tests/test_native_demo_scene_label_adaptation.py
```

The command exited 0. The source parametrizations are 8 startup projects + 30 catalogue cases + 4 adaptation cases = 42 test cases. Compiler warnings were emitted; no test failed. Container image digest: `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.

## Startup results

Every project packed and fit the actual eight-track sequence staging capacity: `seq_bytes=31944`, `seq_capacity=32768`, `seq_tracks=8`. These app-startup probes use the host arena model with a 192,000-byte pool and do not prove pi32v2 target RAM behavior or physical playback.

| Project | Source SHA-256 | Packed SHA-256 | Result |
|---|---|---|---|
| Afterglow Relay (legacy) | `56098c13c658450c4013f91583cf04dafa6062b30c1c240446401a4201741a62` | `b26fccb44bbf044fc0054991eaefc311c641748099385f624a16ca7b1ec78624` | Pass, report 0, 9 active units, no allocation failures, peak 169244 bytes |
| Event Horizon (legacy) | `5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897` | `0ca335f967cbb469d29132406c0d7ff86972a7cce418dcbdbbbff79668cda56f` | Expected refusal, report 5, max request 65744, cleanup to zero live allocations |
| Packet Bloom (legacy) | `7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349` | `230c98a06a101ce1675ccbeadc934fb44886ac51287b91acdf5eee3fc4187512` | Pass, report 0, 9 active units, no allocation failures, peak 169244 bytes |
| Neon Transit (legacy) | `e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251` | `cb180adf8d7f7b2e8b1cd8c14daaf309446fbf0bea58b4abc8682c9f10b661f2` | Expected refusal, report 5, max request 65744, cleanup to zero live allocations |
| Afterglow Relay Showcase | `53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f` | `4992a4cdb17163b40426b54f3bcfd478abf0d7b35572ed3b856ec8b02b081988` | Expected refusal, report 5, max request 65744, cleanup to zero live allocations |
| Event Horizon Showcase (adapted) | `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f` | `ecb00a5363695e3275891bcb1fa0ab44d9b23d7108c1b9ddac35230d81f24a32` | Pass, report 0, 6 active units, no allocation failures, peak 90912 bytes |
| Packet Bloom Showcase (adapted) | `853be1d05bd206d9fce928e5d36944d932491a9b9c69cf79d96e6f78392700e7` | `3c87e56e8880d0119912f9230580ea4630e1e06a63a14c8182c328deaa6986c8` | Expected refusal, report 5, max request 79344, cleanup to zero live allocations |
| Satellite Hearts | `090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6` | `04de81e9459baeb1e45fab771ac09fed1ceef69a2563cabd521692a42fbc1278` | Expected refusal, report 5, max request 207728, cleanup to zero live allocations |

## Limits and next step

The adapted Event Horizon sequence is retained and starts in the host app probe. Adapted Packet Bloom sequence staging is lossless, but full app startup refuses candidate engine coexistence in the fixed pool. Its largest observed allocation request was 79,344 bytes; the harness does not identify which request failed. Keep that failure visible; do not raise the pool or call it startup-accepted. Other unchanged demos retain their prior host startup outcomes. Owner musical approval, pi32v2 allocation proof, full firmware pack/link and physical playback/save-reload acceptance remain separate gates. Catalogue dispositions/default are unchanged and no project is promoted by this receipt.
