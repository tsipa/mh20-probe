# ER-TFTM013-1 mechanical reference / ST7789-compatible 240x240 display

References: J2. Dimensions and hole positions from the manufacturer outline; compare with the actual display.

[Component-side drawing](drawings/lcd.svg)

## Dimensions

| Parameter | Value |
|---|---|
| pcb_mm | [27.78, 39.22] |
| pcb_thickness_mm | 1.2 |
| header_pitch_mm | 2.54 |
| header_pin1_from_side_mm | 6.27 |
| header_from_near_edge_mm | 1.5 |
| module_holes_mm | 2.0 |
| hole_center_spacing_mm | [22.78, 34.22] |
| hole_edge_offsets_mm | [2.5, 2.5] |
| header_plastic_mm | 2.5 |
| long_header_pin_mm | 6.0 |
| carrier_pad_mm | 1.7 |
| carrier_drill_mm | 1.0 |
| carrier_hole_drill_mm | 2.2 |
| carrier_holes_mm | [[6.0, 11.5], [28.78, 11.5], [6.0, 45.72], [28.78, 45.72]] |
| support_screw | M1.6 |

## Pinout

| Pin | Function |
|---|---|
| 1 | GND |
| 2 | VCC / 3V3 |
| 3 | SCL / SPI SCK / GPIO14 |
| 4 | SDA / SPI MOSI / GPIO13 |
| 5 | RES / GPIO27 |
| 6 | DC / GPIO32 |
| 7 | BLK / 3V3 |

## Notes

The module has no CS pin; SCL/SDA are SPI clock and data. Firmware uses SPI mode 3, 1 MHz for initialisation, 20 MHz for drawing and rotation 0 for the carrier placement.

The drawing shows the header at the top. On the carrier the display sits on the left, rotated 180 degrees, with the header at the bottom. The module holes are 2.0 mm, the carrier holes 2.2 mm; use M1.6 screws with insulating spacers. The drawing gives 2.5 mm header plastic and 6.0 +/- 0.2 mm long pins; choose the spacer height from the actual soldered header.

## Sources

- [er-tftm013-1_outline.webp](../sources/er-tftm013-1_outline.webp)

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
