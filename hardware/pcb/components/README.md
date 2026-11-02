# Component reference

Datasheets, module drawings, pinout images and extracted specification text are in [../sources](../sources). The pages below list dimensions, pin functions and carrier pad and drill sizes. [components.json](components.json) holds the same data plus the carrier pad coordinates and nets (spec coordinates: origin at the board top-left corner, y down) and SHA-256 checksums of the source files.

| Reference | Component | Page |
|---|---|---|
| A1 | ESP32 DevKitC V4, 38 pins, rows 25.4 mm apart | [ESP32](esp32.md) |
| J2 | ER-TFTM013-1 1.3 in 240x240 LCD, 7 pins | [Display](lcd.md) |
| J3 | Ebyte E07-M1101D-SMA CC1101 433 MHz radio | [Radio](radio.md) |
| K1, K2 | AQY212EH PhotoMOS relay, DIP-4 | [PhotoMOS](aqy212eh.md) |
| U1 | DD4012SA 5 V step-down module, 7805 pinout | [Buck module](buck.md) |
| J1 | Phoenix MKDS 1,5/6-5,08, 6 poles, 5.08 mm | [Terminal](terminal.md) |
| R1, R2 | 150 ohm 1% 0.25 W axial | [Resistors](resistor.md) |

The SVG drawings are simplified component-side views derived from the sources; the manufacturer drawings are authoritative.

All modules are soldered through male 2.54 mm headers, without sockets. Support screws: LCD M1.6 through the module's 2.0 mm holes, radio M2.5 through the carrier slots, board M3. Choose the spacer height after measuring the soldered header standoff.
