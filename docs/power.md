# Power from a 24 V supply

## Carrier supply (P4)

U1 is a **DD4012SA 5 V step-down module** (3 pins IN/GND/OUT, 7805 pinout, input 4.75–40 V). It feeds the ESP32 DevKit 5V pin through jumper JP1. The DevKit's onboard regulator supplies 3.3 V to the ESP32, CC1101 and display.

```mermaid
flowchart LR
    A["J1.1 24 V / J1.2 0 V"] --> B["U1 DD4012SA<br/>24 → 5 V buck"]
    B -- "5V_REG" --> C["JP1"]
    C -- "5V_DEV" --> D["ESP32 DevKit 5V"]
    D --> E["Onboard 3.3 V regulator"]
    E --> F["ESP32 + CC1101 + LCD"]
    F --> G["AQY212EH PhotoMOS outputs"]
```

| Net | Connects |
|---|---|
| 24V_IN | J1 pin 1, U1 IN |
| GND | J1 pin 2 (machine 0 V), U1 GND, ESP32, LCD, radio, PhotoMOS LED cathodes |
| 5V_REG | U1 OUT to JP1 |
| 5V_DEV | JP1 to ESP32 5V |

## Grounding and USB

The buck module is **not isolated**: machine 0 V is the logic GND. The only isolation is in the two AQY212EH PhotoMOS outputs; their contacts float relative to the receiver.

- **With JP1 fitted, do not connect USB to a PC while the board is on machine 24 V.** The PC ground would be tied to machine 0 V.
- To work on the bench, **remove JP1** and power the board from USB only.
- Reconnect JP1 before running from machine 24 V.

**Never apply 24 V to GPIO, CC1101, LCD or 3V3.** Current draw, module temperature and operation from the machine supply have not been measured. See [machine-interface.md](machine-interface.md) for the outputs.
