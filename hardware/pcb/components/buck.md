# DD4012SA 5 V step-down module

References: U1. 3-pin SIP buck module in the 7805 pinout.

[Component-side drawing](drawings/buck.svg)

## Dimensions

| Parameter | Value |
|---|---|
| package | 3-pin SIP, 7805 pinout |
| pin_pitch_mm | 2.54 |
| envelope_mm | [12, 14] |
| envelope_height_mm | 20 |
| carrier_pad_mm | 1.8 |
| carrier_drill_mm | 1.0 |

## Pinout

| Pin | Function |
|---|---|
| 1 | IN / 24V_IN (square pad) |
| 2 | GND |
| 3 | OUT / 5V_REG |

## Notes

Order the 5 V output version. Input 4.75-40 V; the carrier silkscreen limits the supply to 36 V. The module is not isolated: machine 0 V and logic GND are one net. OUT feeds the ESP32 5V pin through JP1; remove JP1 before connecting USB.

The 12 x 14 mm envelope is centred on pin 2 and used for the body clearance check. Any 7805-pinout 5 V module with an input rating of at least 30 V and a body inside the envelope fits.

Carrier pad positions and nets are in [components.json](components.json).
