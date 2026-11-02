# Panasonic AQY212EH

References: K1 (PROBE), K2 (READY). DIP-4 through-hole; the surface-mount AQY212EHA does not fit.

[Component-side drawing](drawings/aqy212eh.svg)

## Dimensions

| Parameter | Value |
|---|---|
| body_mm | [6.4, 4.78] |
| package | DIP4 / THT |
| pin_pitch_mm | 2.54 |
| row_spacing_mm | 7.62 |
| carrier_drill_mm | 1.0 |
| carrier_pad_mm | 1.8 |

## Pinout

| Pin | Function |
|---|---|
| 1 | LED anode (+) |
| 2 | LED cathode (-) / GND |
| 3 | Floating output B |
| 4 | Floating output A |

## Notes

Pins 3/4 form a floating, bidirectional normally open output. Pin 1 is the square pad. Each LED is driven from a GPIO through a 150 ohm 1% resistor: at least 7.5 mA at GPIO HIGH = 2.64 V and VF = 1.5 V (151.5 ohm), about 14 mA typical at 3.3 V (VF 1.14 V at 5 mA).

Maximum switching times at IF = 5 mA and 25 C are 4 ms on and 1 ms off; turn-on gets faster with higher LED current. The load current rating falls with temperature. On the carrier the output nets keep 3.0 mm to all other copper except at the relay's own pads and the J1 pads.

## Ratings

| Parameter | Value |
|---|---|
| absolute_load_voltage_v | 60 |
| recommended_load_voltage_v | 48 |
| continuous_load_current_a_25c | 0.55 |
| on_resistance_max_ohm | 2.5 |
| off_leakage_max_ua | 1 |
| recommended_led_current_ma | [5, 30] |
| turn_on_max_ms_at_5ma_25c | 4 |
| turn_off_max_ms_at_5ma_25c | 1 |

## Sources

- [AQY212EH.pdf](../sources/AQY212EH.pdf)
- [AQY212EH.txt](../sources/AQY212EH.txt)

Carrier pad positions and nets are in [components.json](components.json). The SVG is a simplified reference; the manufacturer drawing is authoritative.
