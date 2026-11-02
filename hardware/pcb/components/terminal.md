# Phoenix MKDS 1,5/6-5,08 (1706303), 6-pole 5.08 mm screw terminal

References: J1. Phoenix 1706303. Alternatives must match pitch, pin size and body envelope; the dimensions below are those of the Phoenix part.

[Component-side drawing](drawings/terminal.svg)

## Dimensions

| Parameter | Value |
|---|---|
| positions | 6 |
| pitch_mm | 5.08 |
| body_mm | [30.48, 9.8] |
| body_height_mm | 13.8 |
| installed_height_mm | 14 |
| lead_length_mm | 3.5 |
| carrier_pad_mm | 2.6 |
| carrier_drill_mm | 1.3 |

## Pinout

| Pin | Function |
|---|---|
| 1 | 24V_IN |
| 2 | 0V / GND |
| 3 | READY_A |
| 4 | READY_B |
| 5 | PROBE_A |
| 6 | PROBE_B |

## Notes

Six-position 5.08 mm screw terminal, 30.48 x 9.8 mm body. On the carrier it sits on the right edge with the wire entries facing off the board; pin 1 is at the bottom. The carrier uses the KiCad library footprint `TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal`.

Pin 2 (0 V) is logic GND; the buck module is not isolated. The pads are 2.6 mm at 5.08 mm pitch, so the gap between J1.2 (GND) and J1.3 (READY_A) is 2.48 mm, the only place where an isolated output is closer than 3.0 mm to other copper. KF301-type terminals have 5.0 mm pitch and do not fit; ratings of the Phoenix part do not carry over to other brands.

## Sources

- [terminal-mkds6.pdf](../sources/terminal-mkds6.pdf)
- [terminal-mkds6.txt](../sources/terminal-mkds6.txt)

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
