# Wiring

The prototype uses a classic ESP32-WROOM DevKit, a 433 MHz CC1101 module and a seven-pin, ST7789-compatible IPS 240×240 display. The display works in **hardware SPI MODE3**. The diagram shows signal connections. Header positions vary between DevKit boards.

![Wiring diagram](images/wiring.png)

[Vector SVG](images/wiring.svg) · [Machine-readable wiring](../hardware/wiring.json)

## CC1101

Pin numbers follow the module photo below.

| Module pin | CC1101 signal | ESP32 |
|---:|---|---|
| 1 | GND | GND |
| 2 | VCC | 3V3 |
| 3 | GDO0 | GPIO26 |
| 4 | CSN | GPIO5 |
| 5 | SCK | GPIO18 |
| 6 | MOSI | GPIO23 |
| 7 | MISO / GDO1 | GPIO19 |
| 8 | GDO2 | Leave disconnected |

In the picture's orientation, the top row is **2, 4, 6, 8** and the bottom row is **1, 3, 5, 7**. Looking from the opposite side mirrors this arrangement.

![Original module pinout reference](images/cc1101-pinout-reference.jpg)

The CC1101 uses VSPI and provides asynchronous demodulated data on GDO0. Use an antenna intended for 433 MHz; an ordinary Wi-Fi antenna is not matched to this band.

## Display

| LCD pin | ESP32 |
|---|---|
| GND | GND |
| VCC | 3V3 |
| BLK / BL | 3V3 |
| SCL / SCK | GPIO14 |
| SDA / MOSI | GPIO13 |
| RES | GPIO27 |
| DC | GPIO32 |

SCL/SDA on this module are **SPI signals**, despite their I²C-like names. This seven-pin module has no CS pin. It uses a separate HSPI bus: 1 MHz initialization, 20 MHz drawing, rotation 2. If long wires cause pixel corruption, DRAW_HZ can be reduced to 10 MHz. 20 MHz works on the prototype.

All three devices share local GND and 3.3 V. Place supply decoupling close to the CC1101. See [power.md](power.md) for the proposed 24 V supply.

## Reserved machine outputs

| GPIO | Signal |
|---:|---|
| 33 | READY |
| 25 | PROBE_LOOP_ENABLE |

These are 3.3 V control signals for an external interface. See [machine-interface.md](machine-interface.md) for PhotoMOS contacts, polarity and the machine connection.
