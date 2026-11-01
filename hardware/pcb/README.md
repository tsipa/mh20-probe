# Module carrier

A 120 x 100 mm, two-layer carrier for the existing receiver modules. The display is centered on the front. The ESP32 is soldered directly to the back, with 19 pins per row, 2.54 mm pitch and 25.4 mm between rows. The six-way screw terminal faces the left edge.

![Module placement](preview/assembly-plan.png)

Open `receiver_carrier.kicad_pro` in KiCad 10. The project includes the schematic, routed PCB, local module symbols and footprints, and `bom.csv`. [Copper and placement drawing](preview/placement.svg) · [Schematic](preview/schematic/receiver_carrier.svg).

This is a prototype layout, not a fabrication release. Two Pololu 5420 ready-made output modules are selected. Their timing and leakage still require verification against the machine input. Display and radio body sizes are approximate; check the purchased modules and pin numbering before ordering a board.

## Parts

| Reference | Part | Purpose |
|---|---|---|
| A1 | Existing 38-pin ESP32 board | Receiver firmware, display, Wi-Fi |
| U1 | Hi-Link URB2405YMD-6WR3 | Isolated 24 V to 5 V supply |
| J2 | Existing seven-pin ST7789 display | Front-center display |
| J3 | Existing CC1101 module | Probe radio |
| EXT1, EXT2 | Two [Pololu 5420 isolated SPST modules](https://www.pololu.com/product/5420) | PROBE and READY dry contacts |
| J1 | Six-way 5.08 mm screw terminal | Machine wiring |
| J4, J5 | Five-pin and four-pin headers | Short wires to the output module |
| JP1 | Two-pin header and shunt | Disconnect the converter output for USB power |

There are no separate resistors, capacitors, transistor drivers or ferrite beads on the carrier. Input conditioning belongs inside the complete output module. Four 3.2 mm holes mount the carrier. The small output boards use short soldered wires and insulated support in the reserved area; they have no dedicated mounting holes.

## Machine connector

J1 runs from top to bottom in the front view:

| Pin | Signal |
|---|---|
| 1 | +24 V input |
| 2 | Machine 0 V |
| 3, 4 | PROBE contact A, B |
| 5, 6 | READY contact A, B |

Use an upstream fused 24 V supply. Machine 0 V and receiver GND are separate nets. The four contact wires are floating. The converter's component isolation rating does not establish an isolation rating for the assembled carrier. Connecting USB can introduce an external ground path.

Remove the JP1 shunt before powering the ESP32 through USB. Refit it for standalone 24 V operation.

## Module connections

Display header order: GND, VCC, SCL, SDA, RES, DC, BLK. VCC and BLK connect to 3.3 V. GPIO14 drives SCL, GPIO13 SDA, GPIO27 RES and GPIO32 DC. The footprint assumes a 2.54 mm header and an approximate 28 x 40 mm body; check both against the actual display.

CC1101 header: 1 GND, 2 3.3 V, 3 GDO0/GPIO26, 4 CSN/GPIO5, 5 SCK/GPIO18, 6 MOSI/GPIO23, 7 MISO/GPIO19, 8 unused. Confirm the module's physical pin numbering. Orient its antenna connector toward the lower edge. No carrier copper is routed in the marked antenna areas.

The two **Pololu 5420** boards sit behind the upper-left area on insulated support, clear of solder joints and display pins. Each board is about 20.3 x 8.1 x 3.3 mm; both fit within the existing 55 x 38 mm reserve. This carrier uses short soldered wires rather than a vendor-specific footprint.

Use the two-wire control connection shown by Pololu: join VIN and EN on each output board, then connect that pair to its control GPIO. Each GPIO supplies up to 10 mA when on. Connect both module GND pins to receiver GND. J4's +5 V and +3.3 V pins are unused in this arrangement. The modules' load terminals are symmetric and remain isolated from the control wiring.

| Module | VIN + EN | GND | Load terminal pair |
|---|---|---|---|
| EXT1, PROBE | J4 pin 3, GPIO25 | J4 pin 2 | J5 pins 1 and 2 |
| EXT2, READY | J4 pin 4, GPIO33 | J4 pin 2 | J5 pins 3 and 4 |

Both outputs are normally open MOSFET contacts, support DC switching, and have a 60 V absolute maximum load rating. No separate carrier input resistors or drivers are required. This selection replaces the provisional TLP222A-based module.

**Timing tradeoff:** Pololu specifies up to 1 ms turn-on and turn-off time. This does not meet the earlier 0.5 ms target. Budget up to 1 ms of additional PROBE output delay: at 100 mm/min that corresponds to 1.7 micrometres of travel, before radio and controller delays. This is a delay bound, not a repeatability specification. Verify delay, jitter and off-state leakage with the actual machine input before using it for measurements. The manufacturer does not publish an off-state leakage limit on the product specification page, so that remains a bench check.

Purchase: [Pololu 5420](https://www.pololu.com/product/5420), two pieces. The listed unit price is $4.95 before shipping and tax. Amazon or AliExpress stock for this exact part has not been confirmed.

## Power footprint

U1 uses the manufacturer's top-view pin drawing: 1 -Vin, 2 +Vin, 3 +Vout, 5 output GND; 4 is not populated and 6 is unused. The converter body is 25.4 x 25.4 mm. Check the label and pins on the supplied part before assembly.

Sources: [Hi-Link product page](https://www.hlktech.net/index.php?cateid=760&id=1299), [manufacturer datasheet](https://drive.google.com/file/d/1KfvgmW3_NbNLIYul3vVTS3nYDesQEoOc/view), [Espressif reference dimensions](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf).

## Checks and regeneration

KiCad ERC and PCB DRC pass with zero violations and zero unconnected items. The schematic netlist is compared with every connected PCB pad by `verify_connectivity.py`. These checks cover carrier connectivity and default KiCad clearances; the functional module symbols use passive pins, so ERC does not validate module voltage ratings, output timing, EMC or the machine interface. Those require checking the selected modules and testing the assembly.

Run `generate_carrier.py` using KiCad's bundled Python. It reads `design.json` and restores the saved track geometry from `routes.json`. That geometry belongs to this placement: changing pad positions requires rerouting and fresh checks. The initial tracks were produced locally with [Freerouting](https://github.com/freerouting/freerouting), then checked in KiCad. Run `render_placement.py` with Pillow to redraw the placement plan.

No fabrication Gerbers are included while the mechanical fit and machine-interface checks remain unresolved.
