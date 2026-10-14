# Pico 2 W USB_KEY dongle build

[verified] On 2026-10-14, built the dongle for RP2040 Pico and RP2350 Pico 2 W using the repository CI SDK pin, Raspberry Pi Pico SDK 2.1.1 (bddd20f928ce76142793bef434d4f75f4af6e433), TinyUSB 86ad6e56c1700e85f1c5678607a762cfe3aa2f47, and picotool 2.1.1 (de8ae5ac334e1126993f72a5c67949712fd1e1a4). The SDK image was lunar-pico2w-sdk:2.1.1-picotool-2.1.1, image ID sha256:69464cb264521177f41294e3b649e0466b39b5c10ba9127427f9986fc5f23417. Both builds ran with network disabled in bounded docker-batch.slice containers (2 CPUs, 2 GiB memory and swap).

[verified] The CI recipe used Pico as the implicit board and failed for pico2_w because that board header intentionally has no PICO_DEFAULT_LED_PIN. The firmware now compiles direct LED operations only when the board defines that pin; otherwise those operations are no-ops. USB CDC diagnostics remain enabled. No Wi-Fi/CYW43 stack was added.

[verified] The resulting Pico 2 W UF2 is at /home/claude/.local/share/codex-coordination/artifacts/lunar-pico2w/20261014/final/pico2_w/build/usb_key_dongle.uf2, SHA-256 54b6157f1ff42c94834885ec9ccd37c4663365fdb2a71149f17d4bae0612e30c, size 69,120 bytes. picotool info -a identifies UF2 family rp2350-arm-s (UF2 family ID 0xe48bff57), target RP2350 ARM Secure, board pico2_w, boot2 boot2_w25q080, binary range [0x10000000, 0x1000857c), image-def metadata at 0x10000138, and ignored metadata at 0x10008568.

[verified] The Pico UF2 remains a separate artifact at /home/claude/.local/share/codex-coordination/artifacts/lunar-pico2w/20261014/final/pico/build/usb_key_dongle.uf2, SHA-256 d083796974ea63945946dd69fd7ac556b95c0a0eade942fb9efb13e0b264cb39, size 75,776 bytes. picotool info -a reports family rp2040, board pico, boot2 boot2_w25q080, and range [0x10000000, 0x1000939c).

[verified] CI now builds both board configurations with distinct build directories and artifacts; the original Pico artifact name remains usb_key_dongle-uf2, and Pico 2 W uses usb_key_dongle-pico2-w-rp2350-uf2.

[reported] The project wiring/design keeps USB_KEY drive signals on GP14/GP15, external pull-up controls GP16/GP19, mux GP17, button GP18 (dongle/firmware/config.h). This task did not validate that pinout electrically on a Pico 2 W or resolve the owner's GPIO/wiring question.

[verified] No Pico was flashed and no hardware behavior was tested by this worker. Root owns the physical bootloader/UF2 operation and subsequent review. The artifacts remain private coordination outputs and are not committed.
