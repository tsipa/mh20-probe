# ESP32 DevKitC-style 38-pin board

References: A1. 38 pins, rows 25.4 mm apart; compare body, antenna and USB position with the actual board.

[Component-side drawing](drawings/esp32.svg)

## Dimensions

| Parameter | Value |
|---|---|
| header_count | 38 |
| header_pitch_mm | 2.54 |
| row_spacing_mm | 25.4 |
| end_pin_span_mm | 45.72 |
| reference_pcb_mm | [27.94, 48.26] |
| reference_antenna_extension_mm | 6.04 |
| carrier_body_outline_mm | [27.94, 54.31] |
| carrier_pad_mm | 1.7 |
| carrier_drill_mm | 1.0 |

## Pinout

| Pin | Function |
|---|---|
| 1 | 3V3 |
| 2 | EN |
| 3 | GPIO36 / VP |
| 4 | GPIO39 / VN |
| 5 | GPIO34 |
| 6 | GPIO35 |
| 7 | GPIO32 |
| 8 | GPIO33 |
| 9 | GPIO25 |
| 10 | GPIO26 |
| 11 | GPIO27 |
| 12 | GPIO14 |
| 13 | GPIO12 |
| 14 | GND |
| 15 | GPIO13 |
| 16 | GPIO9 / D2 |
| 17 | GPIO10 / D3 |
| 18 | GPIO11 / CMD |
| 19 | 5V |
| 20 | GND |
| 21 | GPIO23 |
| 22 | GPIO22 |
| 23 | GPIO1 / TX0 |
| 24 | GPIO3 / RX0 |
| 25 | GPIO21 |
| 26 | GND |
| 27 | GPIO19 |
| 28 | GPIO18 |
| 29 | GPIO5 |
| 30 | GPIO17 |
| 31 | GPIO16 |
| 32 | GPIO4 |
| 33 | GPIO0 |
| 34 | GPIO2 |
| 35 | GPIO15 |
| 36 | GPIO8 / D1 |
| 37 | GPIO7 / D0 |
| 38 | GPIO6 / CLK |

## Carrier use

| Pin | Net |
|---|---|
| 1 | 3V3 (LCD, radio) |
| 7 | LCD_DC |
| 8 | READY_EN (R2, K2) |
| 9 | PROBE_EN (R1, K1) |
| 10 | RF_DATA (radio GDO0) |
| 11 | LCD_RST |
| 12 | LCD_SCK |
| 14, 20, 26 | GND |
| 15 | LCD_MOSI |
| 19 | 5V_DEV (from JP1) |
| 21 | RF_MOSI |
| 27 | RF_MISO |
| 28 | RF_SCK |
| 29 | RF_CSN |

All other pins are not connected. GPIO6-11 belong to the module flash; GPIO36/39 are input-only.

On the carrier the board sits in the centre of the top side with pin 1 at the top left, the WROOM antenna over the top board edge (no copper below it) and the USB connector pointing down. The 5V pin is fed from the buck module through JP1; remove JP1 before connecting USB. The GND pins 14, 20 and 26 are connected on the module, so the footprint declares them as a KiCad jumper pad group and the carrier has no copper between them.

The Espressif drawing gives a 48.26 mm PCB with a 6.04 mm antenna extension; the carrier body outline is 27.94 x 54.31 mm. Header pin 9 is GPIO25; the dimension drawing shows an apparently duplicated GPIO35 label there.

## Sources

- [esp32-devkitc-v4.pdf](../sources/esp32-devkitc-v4.pdf)
- [esp32-devkitc-v4.txt](../sources/esp32-devkitc-v4.txt)

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
