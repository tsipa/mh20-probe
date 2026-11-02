# 150 ohm 1%, 0.25 W axial DIN0207

References: R1 (PROBE), R2 (READY). The DIN0207 envelope comes from the footprint; compare with the purchased part.

[Component-side drawing](drawings/resistor.svg)

## Dimensions

| Parameter | Value |
|---|---|
| nominal_body_mm | [6.3, 2.5] |
| formed_lead_pitch_mm | 7.62 |
| carrier_pad_mm | 1.8 |
| carrier_drill_mm | 0.9 |

## Pinout

| Pin | Function |
|---|---|
| 1 | GPIO25 for R1 / GPIO33 for R2 |
| 2 | Relay LED anode |

## Notes

No polarity. Bend the leads to 7.62 mm pitch. 150 ohm gives at least 7.5 mA LED current (GPIO HIGH 2.64 V, VF 1.5 V, -1% tolerance) and about 14 mA typical at 3.3 V, above the 5 mA datasheet timing condition of the AQY212EH. Even with VF = 0 the current stays below 23 mA and the dissipation below 0.08 W.

## Ratings

| Parameter | Value |
|---|---|
| resistance_ohm | 150 |
| tolerance_percent | 1 |
| power_w | 0.25 |

## Sources

The carrier DIN0207 footprint defines the envelope and lead pitch.

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
