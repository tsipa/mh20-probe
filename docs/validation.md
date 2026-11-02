# Testing status

| Part | Tested | Where | Result |
|---|---|---|---|
| Reception, contact detection, display (P3-era firmware) | Yes | Breadboard prototype, USB power | Works |
| P4 firmware changes (first CONTACT frame, output guard, task watchdog) | Host tests only | `scripts/test.py` | Pass; not yet compiled with arduino-cli or run on hardware |
| P4 carrier PCB | Design checks only | KiCad DRC (with schematic parity) and ERC | Clean; not fabricated or assembled |
| 24 V supply, PhotoMOS outputs, SINUMERIK 828D inputs | No | | Not verified on the machine |

## Bench prototype

A 45-second UART log from the breadboard prototype contains **864 accepted messages, 23 contacts, 1 link loss and 0 edge queue overflows**. CC1101 returned VERSION 0x14. All three display states (red, green, blue) were seen. The single link loss was not investigated; longer runs are needed to judge reliability.

Files: [receiver-check.json](../evidence/working/receiver-check.json), [UART log](../evidence/working/uart.log), [upload status](../evidence/working/arduino-upload-status.json).

## Host tests

Run `python scripts/test.py`. The firmware headers are compiled to WebAssembly with Zig/Clang and run in Wasmtime; no hardware is needed. Reports go to `build/tests/`.

| Test | Coverage |
|---|---|
| Outputs + decoder | Startup, two-frame acquisition, off-cadence first CONTACT frame, release, 65 ms link loss, output guard and micros() rollover |
| Wi-Fi service | Startup, two-frame probe detection, Wi-Fi latch across signal loss, OTA inhibition, retry and reset |
| Wi-Fi settings | UART commands and line framing, SSID/password limits, invalid saved settings, recovery timeout and display labels |
| Frequency search | Full band, candidates, refusing CW lock, weaker probe beside stronger interference, loss/rescan and timer rollover |
| RSSI | Signed conversion, thresholds, isolated spikes, hysteresis and reset after retuning/SPI failure |
| Display | Pixel comparison against Adafruit_GFX, removal of old text, bounds, strip split, no malloc |
| Recorded IQ | Background, FREE, CONTACT entry, FREE release, two frequencies and message loss, also replayed through the C++ decoder |

The [test recordings](../fixtures/README.md) are real SDR captures. Recorded signals are demodulated in Python; the C++ frequency search is tested with simulated RSSI. The tests do not model the CC1101 itself.

## Not tested yet

- P4 firmware compiled and running on an ESP32.
- Output guard and watchdog behavior on hardware, including reset behavior of the output pins.
- The P4 carrier: assembly, fit of the modules, DD4012SA supply from machine 24 V, temperature.
- PhotoMOS outputs and the SINUMERIK 828D connection.
- Service network, Wi-Fi shutdown on probe detection, browser uploads and interrupted OTA updates.
- CC1101 acquisition across the whole sweep, range with a matched antenna, interference.
- Minimum accepted contact, end-to-end latency and measurement repeatability.
