# Cynthion power monitor routed build on Aeon

The r1.4 power-monitor prototype routed successfully from source commit
`b9ff8de7376a7a5c541e4ebbd7161e2911cf2783` (tree
`78e95d1f263ffc97e627f4d82d6bb5cedee147de`). The working source checkout was
read-only in the build container. The build command was:

```sh
SOURCE_COMMIT=b9ff8de7376a7a5c541e4ebbd7161e2911cf2783 \
  /venv/bin/python -m tools.cynthion_usb_key.power_monitor \
  --build-dir /out/build
```

The exact tool image was `lunar-modulator-manual:ubuntu-24.04`, image ID
`sha256:d065eaf170070135564c88bd4273f30784278b35c9355d36a0a96bd6ba20cc8c`.
The official YosysHQ OSS CAD Suite Linux x64 asset from release `2026-10-16`
was installed inside that container, SHA-256
`95aead487287adf8fbbe965799e88e2ccb12a544f3d0a27b27f80bfc7c892911`
([release](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-10-16)).
The tool versions were Yosys `0.70+145` (`a31d95ea0`), nextpnr-ecp5
`0.11.1-63-g44a6c739`, and Project Trellis/ecppack `1.4-86-ga31ff70`.
Python dependencies came from the checked-in
`gateware/requirements-test.txt`: Cynthion `0.2.5`, Amaranth `0.5.10`,
LUNA USB `0.2.3`, and Apollo FPGA `1.1.1`.

The build container ran under `docker-batch.slice`, capped at four CPUs and
8 GiB memory with equal configured swap (no extra swap in the effective
cgroup), and labeled `lan.project=lunar-modulator` and
`lan.session=cynthion-monitor-aeon-route-20261016`. It had network access only
while fetching the official toolchain and pinned Python dependencies; network
was disconnected before routing. The resulting `.tim` report passes the
60 MHz USB clock at 171.61 MHz and the 120 MHz clock at 209.29 MHz.

The routed netlist has no direct target D+/D− GPIO ports, so no target USB GPIO
output-enable cells are present. The ULPI connection to the USB3343 remains a
separate PHY interface and uses the existing fail-closed, non-driving PHY
configuration. The four VBUS output cells are constant, non-tristated outputs:
CONTROL=1, TARGET-C=0, AUX=0, and TARGET-A discharge=0. These are routed-netlist
facts; they do not establish external PHY behavior or any physical current
measurement.

The bitstream is 119,280 bytes, SHA-256
`635b7b1376db0d97656932df57ff3fc331379876f21c2509f9803928b122e378`.
The complete route evidence JSON, bitstream, routed configuration, netlist,
timing report, and build reports are preserved on Aeon at
`/home/claude/.local/share/codex-builds/lunar/cynthion-power-monitor-20261016/route-output/`.
The manifest is `route-evidence.json`; it records hashes for all generated
files and source/toolchain pins. The build script's own receipt reports
`hardware_programmed: false`; no programming API, device discovery, USB, or
hardware command was used.

The bounded offline test command ran against the real installed Amaranth,
LUNA, and Cynthion dependencies in that same container:

```sh
/venv/bin/python -B -m pytest -q -p no:cacheprovider -o addopts= \
  tests/test_ulpi_safe_phy.py tests/test_cynthion_usb_key*.py \
  tests/test_cynthion_power_monitor.py
```

Result: 42 passed, 69 existing Amaranth/LUNA deprecation and unused-
elaboratable warnings. Those checks preceded the additional full register-wrapper transaction test,
which subsequently resolved the responder fixture error; see
`notes/2026-10-16-cynthion-power-monitor.md`. Neither simulation nor routing
proves physical PAC measurements. The bitstream remains an offline artifact only;
root owns any later review or load decision.
