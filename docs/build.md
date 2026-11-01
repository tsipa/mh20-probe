# Build and upload

## Arduino IDE

Open [firmware/probe_rx/probe_rx.ino](../firmware/probe_rx/probe_rx.ino).
Select **ESP32 Dev Module**, with **esp32 by Espressif Systems 3.3.12**.
These settings are for the classic ESP32-WROOM. ESP32-C3 and S3 boards need different settings.

Required libraries:

| Library | Tested version |
|---|---:|
| Adafruit GFX Library | 1.13.0 |
| Adafruit ST7735 and ST7789 Library | 1.12.0 |
| Adafruit BusIO | 1.17.4 |

The sketch configures CC1101 directly through SPI; no separate CC1101 library is needed. UART is **115200 baud**. Replace COM4 in the examples with your board's serial port.

## Arduino CLI / PowerShell

From the repository root, with arduino-cli in PATH:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Install
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Port COM4
```

For a CLI outside PATH, add `-ArduinoCli .\tools\arduino-cli.exe`. The first command installs the specified versions and builds. The second builds and uploads. Close any serial monitor before uploading. Output files go to `build/esp32/`, which Git ignores.

The build script has not yet been checked with a physical upload.

## Wi-Fi updates

The sketch includes a 4 MB partition layout with two 1920 KiB application slots. Install it over USB first. Later, upload `build/esp32/probe_rx.ino.bin` through the [service page](wifi-update.md).

## Firmware images

Prebuilt firmware images are not distributed. Build the firmware from source using the commands above.

## Host tests

Use Python 3.12 and [requirements-dev.txt](../requirements-dev.txt):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\test.py
```

Pixel comparison tests need the Adafruit GFX 1.13.0 source. The runner searches normal Arduino library locations; alternatively pass `--gfx .\libraries\Adafruit_GFX_Library`.

Add `--assets` to regenerate the images. Tests run without connected hardware and do not flash the board. Reports go to `build/tests/`.

See [testing](validation.md) for what the tests cover and what still needs checking.
