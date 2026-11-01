# Testing

## Working prototype

Reception, contact detection and all three display states (red, green and blue) work on the bench prototype.

A 45-second UART log contains **864 accepted messages, 23 contacts, 1 link loss and 0 edge queue overflows**. CC1101 returned VERSION 0x14. The single link loss has not been investigated. Longer tests are needed to assess reliability.

Logs: [receiver-check.json](../evidence/working/receiver-check.json), [UART log](../evidence/working/uart.log), [upload status](../evidence/working/arduino-upload-status.json).

## Automated tests

Run `python scripts/test.py`. The tests compile the firmware headers to WebAssembly with Zig/Clang and run them in Wasmtime.

| Test | Coverage |
|---|---|
| Outputs + decoder | Startup, two-frame acquisition, contact, release, 65 ms link loss and micros() rollover |
| Wi-Fi service | Startup, two-frame probe detection, Wi-Fi latch across signal loss, OTA inhibition, retry and reset |
| Frequency search | Full band, candidates, refusing CW lock, weaker probe beside stronger interference, loss/rescan and timer rollover |
| RSSI | Signed conversion, thresholds, isolated spikes, hysteresis and reset after retuning/SPI failure |
| Display | Adafruit_GFX.cpp and DisplayRaster.h: pixel comparison with full-frame rendering, removal of old text, bounds, 8+2 strip split, no malloc |
| Recorded IQ | Background, FREE, CONTACT entry, FREE release, two frequencies and message disappearance; measured signal edges are also checked by the C++ ProbeDecoder |

The [test recordings](../fixtures/README.md) include source details and checksums. Tests check state changes and tuning accuracy, without requiring an exact message count.

Recorded signals are processed in Python. The C++ frequency search is tested separately with simulated RSSI and messages. These tests do not reproduce the CC1101 radio hardware; finding the probe across the whole band still needs a bench test.

## Full-recording tests

Reports in [evidence/software](../evidence/software/) cover full SDR++ WAV with 2014 frames/14 frequencies, three-contact and held-contact recordings, 98 seconds of background without messages, CW rejection and finding a real probe beside interference.

Some saved reports still list hardware checks as pending. Reception and display operation have since been tested on the bench. New test results go to `build/tests/`.

## Still to test

- Service network startup, Wi-Fi shutdown on probe detection, browser uploads and interrupted OTA updates.
- CC1101 acquisition across the frequency sweep and recovery after retuning.
- Range with a matched antenna and performance in interference.
- Minimum accepted contact, latency and measurement repeatability.
- Machine 24 V power, temperature, PhotoMOS, pull-downs and 828D connection.

Bench tests used USB power. The 24 V machine interface has not been assembled or tested.
