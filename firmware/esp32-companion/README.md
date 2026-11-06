# ESP32 Companion

![Solarman Hub](../../docs/images/solarman-hub.png)

**Solarman Hub is an independent hobby project. It is not affiliated with SOFAR (SofarSolar).**

ESP32 Companion helps you collect data from your Solarman V5 logger and prepare a decoding profile for the Hub. Its web interface is in English. You can use it as a local receiver that forwards reports, or switch to passive mode to capture Wi-Fi traffic for analysis.

Use a **classic ESP32 with 4 MB flash**. The firmware does not support ESP32-C3, S2 or S3. You do not need an ESP32 for normal Hub operation.

## Install or update

For the first USB installation, use `dist/factory.bin` at address `0x0`. For an OTA update through the Companion's web page, use `dist/firmware.bin`. A factory installation can erase settings; OTA keeps your Wi-Fi settings and saved profile.

On Linux, you can flash through Docker without installing Python on the host. Run these commands from the repository root:

```sh
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

Replace `/dev/ttyUSB0` with your board's device path. The first command checks the board; the second installs the firmware. Connect USB to the Docker host. If Docker runs in a VM, pass the USB device through to that VM first.

The [user guide](../../src/solarman_hub/guides/en.md) explains Wi-Fi setup, USB flashing on Windows and macOS, OTA updates, exports and recovery.

## Collect data and export a profile

In receiver mode, point your logger at the ESP32's IP address and TCP port `10000`. To keep cloud reporting, set the Companion's upstream server to the Hub or the manufacturer cloud. Without an upstream server, reports stay local.

After receiving a report, open **Profile builder and exports**. Choose the Sofar HYD G3 profile for a matching report, or use a raw-field template to investigate another format. A template does not identify what each value means: check the field locations, units and scaling against known readings before using it.

You can download a profile JSON, a Hub import bundle or the ESP32 settings. Exported settings omit passwords. Passive mode saves a short PCAP capture; download it before restarting the board. Wi-Fi packets may still be encrypted and require separate analysis on a computer.

## Build from source

Run these commands from the repository root:

```sh
python -m pip install platformio==6.2.0 esptool==5.6.0
python -m platformio run -d firmware/esp32-companion
python firmware/esp32-companion/tools/package.py
```

The build uses the versions in `platformio.ini` and embeds the Hub's built-in Sofar profile. Packaging creates the USB and OTA images together with their checksums. Compiler timestamps mean a rebuild may produce different checksums.

Configuration, authentication and OTA are in `main.cpp`; reception and exports are in `receiver.cpp`; passive capture is in `capture.cpp`. Native protocol tests share `v5_protocol.h` with the firmware. Keep Wi-Fi passwords and actual device identifiers out of source files and firmware images.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
