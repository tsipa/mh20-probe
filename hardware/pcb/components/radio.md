# CC1101 / E07-M1101D-SMA reference, 28 and 30 mm versions

References: J3. Pin table matches the Ebyte documentation; compare the mounting holes of the actual module with the print.

[Component-side drawing](drawings/radio.svg)

## Dimensions

| Parameter | Value |
|---|---|
| pcb_width_mm | 15 |
| documented_pcb_lengths_mm | [28, 30] |
| header_pitch_mm | 2.54 |
| reference_header_edge_offset_mm | 1.6 |
| reference_holes_from_side_mm | 2.7 |
| reference_holes_from_sma_edge_mm | 10 |
| reference_module_hole_mm | 3.0 |
| carrier_pad_mm | 1.7 |
| carrier_drill_mm | 1.0 |
| carrier_slots_mm | [[64.5, 9.0, 3.2, 5.2], [74.1, 9.0, 3.2, 5.2]] |
| support_screw | M2.5 |

## Pinout

| Pin | Function |
|---|---|
| 1 | GND |
| 2 | VCC / 3V3 |
| 3 | GDO0 / GPIO26 |
| 4 | CSN / GPIO5 |
| 5 | SCK / GPIO18 |
| 6 | MOSI / GPIO23 |
| 7 | MISO / GDO1 / GPIO19 |
| 8 | GDO2 / unused |

## Notes

The Ebyte manual gives 1.8-3.6 V supply (3.3 V nominal), 3.3 V logic and 20 mA RX current. Use a 433 MHz antenna. Firmware uses VSPI and receives asynchronous data on GDO0.

The drawing uses the Ebyte 28 mm geometry with the SMA at the top and the header below, which is also the orientation on the carrier: top right, SMA jack over the top board edge, pin 1 at the left of the lower header row. Only the radio's own nets run under the module, and 24V_IN copper keeps 5 mm away. The two 3.2 x 5.2 mm slots take M2.5 screws and cover the hole positions of both the 30 mm (older manual) and 28 mm (newer outline) versions. `CC1101-Product-size-600x313.jpg` states 28 x 15 mm and 2.54 mm pitch, but its hole dimensions contradict its graphic, so it is not used for the hole positions.

The Ebyte manual was obtained from https://raw.githubusercontent.com/mcore1976/cc1101-tool/56517fe0a1d318472422d43ab637cc2696c0d5cf/E07-M1101D-SMA_Usermanual_EN_v1.30.pdf ; the 28 mm drawing is from https://www.cdebyte.com/Uploadfiles/Picture/2024-11-20/20241120175756205.jpg .

## Sources

- [rf-ebyte-manual.pdf](../sources/rf-ebyte-manual.pdf)
- [rf-ebyte-manual.txt](../sources/rf-ebyte-manual.txt)
- [rf-spec-0.jpg](../sources/rf-spec-0.jpg)
- [CC1101-Product-size-600x313.jpg](../sources/CC1101-Product-size-600x313.jpg)
- [radio-pinout.jpg](../sources/radio-pinout.jpg)

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
