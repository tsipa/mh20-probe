# MH20 receiver carrier PCB (P4)

Carrier board for the receiver: an ESP32 DevKitC, an Ebyte E07 CC1101 433 MHz radio, a 1.3 in ST7789 LCD, a 24 V to 5 V buck module and two AQY212EH PhotoMOS relays that switch the machine's PROBE and READY inputs.

P4 replaces P3 (110 x 100 mm, isolated DC/DC module, ESP32 on the back side). P4 is designed and checked but not fabricated yet.

## Board

- 98 x 70 mm, 2 layers, 1.6 mm, four M3 corner holes (H1-H4).
- All parts on the top side, all through-hole and soldered by hand. The modules are soldered through male pin headers directly into the carrier; there are no sockets, because the machine vibrates.
- Routed by hand (routes are in `p4/spec.json`), one via, no copper pours. Track widths: signal 0.4 mm, power 0.8 mm, isolated outputs 0.6 mm.

## Layout (top view)

| Ref | Part | Position |
|---|---|---|
| J2 | LCD ER-TFTM013-1 | Left, rotated 180 degrees, header at the bottom. `firmware/probe_rx/DisplayPanel.h` uses rotation 0 for this placement |
| A1 | ESP32 DevKitC V4, 38 pins, rows 25.40 mm apart | Centre; pin 1 top left, WROOM antenna over the top edge (no copper below it), USB connector pointing down |
| JP1 | 1x2 header + jumper cap | Below the ESP32 |
| J3 | Ebyte E07-M1101D-SMA | Top right, SMA jack over the top edge |
| R1, K1 | PROBE output | Right middle |
| R2, K2 | READY output | Right middle, below K1 |
| U1 | DD4012SA 5 V buck | Bottom right |
| J1 | 6-pole screw terminal | Right edge, wire entry off the board, pin 1 at the bottom |

The USB plug area below the ESP32 (12 x 25 mm) is kept free of tall parts.

## Connections

| Connector | Pins |
|---|---|
| J1 machine, 5.08 mm | 1 = 24V_IN, 2 = 0V/GND, 3 = READY_A, 4 = READY_B, 5 = PROBE_A, 6 = PROBE_B |
| J2 LCD | 1 = GND, 2 = 3V3, 3 = SCK/GPIO14, 4 = MOSI/GPIO13, 5 = RST/GPIO27, 6 = DC/GPIO32, 7 = BLK/3V3 |
| J3 radio | 1 = GND, 2 = 3V3, 3 = GDO0/GPIO26, 4 = CSN/GPIO5, 5 = SCK/GPIO18, 6 = MOSI/GPIO23, 7 = MISO/GPIO19, 8 = GDO2 not connected |
| JP1 | 1 = 5V_REG (U1 OUT), 2 = 5V_DEV (ESP32 5V pin) |

The full netlist is `p4/netlist.json`.

## Power

24V_IN (J1.1) feeds U1 IN. U1 OUT (5V_REG) goes through JP1 to the ESP32 5V pin (5V_DEV). The ESP32 board's own regulator supplies 3V3 to the LCD and the radio. **Remove JP1 before connecting USB.**

U1 is a 3-pin 7805-pinout buck module (IN, GND, OUT at 2.54 mm), input 4.75-40 V; the silkscreen limits the supply to 36 V. It is **not isolated**: machine 0 V (J1.2) is logic GND, so a PC on the USB port is also tied to machine 0 V. Only the PhotoMOS outputs are isolated.

## Relay outputs

K1 closes PROBE_A/B while GPIO25 is HIGH; K2 closes READY_A/B while GPIO33 is HIGH. Each GPIO drives its relay LED through a 150 ohm resistor; the LED cathodes return to GND. The outputs are floating and bidirectional, so either pin of a pair may go to the positive side. Firmware sets both GPIOs LOW before enabling them as outputs. READY is closed while the probe link is valid; PROBE is closed only while the linked probe is free, so touch or link loss opens it. GPIO state during reset is not guaranteed; this is not a safety circuit. Machine-side wiring: [docs/machine-interface.md](../../docs/machine-interface.md).

LED current with 150 ohm 1%: at least (2.64 V - 1.5 V) / 151.5 ohm = 7.5 mA (minimum GPIO HIGH, maximum VF), about 14 mA typical at 3.3 V with VF 1.14 V. Even with VF = 0 the current stays below 23 mA and the resistor dissipation below 0.08 W.

AQY212EH: 60 V load voltage, 0.55 A at 25 C, on resistance up to 2.5 ohm, off leakage up to 1 uA, turn-on up to 4 ms and turn-off up to 1 ms at IF = 5 mA, 25 C. 1 ms corresponds to 0.01 mm travel at 600 mm/min.

Isolated output nets (PROBE_A/B, READY_A/B) keep 3.0 mm to all other copper and 0.8 mm to each other. Exceptions are pad pairs inside K1/K2 and J1: the MKDS footprint has 2.6 mm pads at 5.08 mm pitch, so J1.2 (GND) to J1.3 (READY_A) is 2.48 mm. 24V_IN keeps 0.8 mm to logic signals and 5 mm from the radio.

## Mounting hardware

| Item | Carrier hole | Screw |
|---|---|---|
| Board H1-H4 | 3.2 mm, no copper within 4.0 mm | M3 |
| LCD (module holes 2.0 mm) | four 2.2 mm holes | M1.6 with insulating spacers |
| Radio | two 3.2 x 5.2 mm slots, cover the 28 mm and 30 mm module versions | M2.5 with insulating spacers |

Spacer height equals the standoff of the soldered header; measure it on the actual module.

## Part choices

- **DD4012SA buck (U1).** Three pins in the 7805 pinout, 12 x 14 mm, wide input range for a 24 V machine supply. The isolated DC/DC module was dropped for size and part count, since the machine-facing contacts are already isolated by the PhotoMOS relays. Any 7805-pinout 5 V module rated for at least 30 V input fits the footprint.
- **AQY212EH with 150 ohm (K1/K2, R1/R2).** DIP-4 PhotoMOS with a floating bidirectional 60 V output and low leakage, suitable for a 24 V machine input of either polarity. 150 ohm keeps the LED current above the 5 mA datasheet timing condition with margin; turn-on time drops with higher LED current. Do not substitute the surface-mount AQY212EHA.
- **Phoenix MKDS 1,5/6-5,08 (J1).** 6 poles, 5.08 mm pitch, 1.3 mm pins. Any 5.08 mm 6-pole terminal with the same pin size and body fits; KF301 types with 5.0 mm pitch do not.

## Files

| Path | Content |
|---|---|
| `p4/spec.json` | Placement, routes, vias, silkscreen (source) |
| `p4/netlist.json` | Nets, no-connect pins, net classes, footprints (source) |
| `receiver_carrier.kicad_sch`, `Carrier.kicad_sym`, `sym-lib-table` | Schematic and symbols; the first two are generated by `tools/schematic.py` |
| `receiver_carrier.kicad_pcb`, `.kicad_pro`, `.kicad_dru`, `fp-lib-table` | KiCad project, generated by `p4.py build` |
| `Carrier.pretty/` | Footprints, generated by `tools/footprints.py` |
| `bom.csv` | Bill of materials |
| `fab/` | Gerbers, Excellon drills (PTH and NPTH with slots), drill maps, job file |
| `print/` | 1:1 PDFs: front, mirrored back, combined print with 50 mm calibration bars; `receiver_carrier-schematic.pdf` |
| `preview/` | PNG previews (front assembly, back, F.Cu, B.Cu) |
| `check/` | Last check: `report.txt`, KiCad DRC, extra checks, geometry, schematic netlist |
| `sources/` | Datasheets and module drawings |
| [components/](components/README.md) | Dimensions, pinouts and drawings per part |
| [tools/](tools/README.md) | Build, check, export and render tools |

## Build and check

```
python -I hardware/pcb/tools/schematic.py
python -I hardware/pcb/tools/p4.py build  hardware/pcb/p4/spec.json --out hardware/pcb
python -I hardware/pcb/tools/p4.py check  hardware/pcb/p4/spec.json --out hardware/pcb
python -I hardware/pcb/tools/p4.py export hardware/pcb/p4/spec.json --out hardware/pcb
python -I hardware/pcb/tools/p4.py render hardware/pcb/p4/spec.json --out hardware/pcb
```

Last result (KiCad 10.0.8): DRC 0 items with schematic parity, extra checks 0 violations, schematic ERC 0. ERC uses passive pins and does not validate the module internals.

## Before soldering

Print `print/receiver_carrier-print-1to1.pdf` at 100% / actual size with page fitting disabled; the calibration bars must measure 50 mm. Lay the actual ESP32, LCD, radio, buck module and terminal on the print and check pin 1, header positions, support holes, SMA and USB clearance.
