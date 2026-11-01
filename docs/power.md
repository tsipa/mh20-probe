# Power from a 24 V supply

## Planned receiver supply

Use an **isolated, regulated 24 V → 5 V DC-DC converter connected to the ESP32 DevKit 5V/VIN input**. The regulator on the DevKit supplies 3.3 V to the ESP32, CC1101 and display.

Choose at least **5 V / 1 A** output capacity. Check that the converter can handle the machine supply's voltage range and transients.

```mermaid
flowchart LR
    A["Machine 24 V"] --> B["Isolated DC-DC<br/>24 → 5 V, ≥1 A"]
    B --> C["ESP32 DevKit 5V/VIN"]
    C --> D["Onboard 3.3 V regulator"]
    D --> E["ESP32 + CC1101 + LCD"]
    E --> F["PhotoMOS outputs to machine"]
```

The converter's output ground connects to the ESP32, CC1101 and display. Connecting it to machine 0 V removes the power isolation. The PhotoMOS output contacts belong to the machine side. USB connected to a grounded computer can also create an external ground path.

Before applying USB power and external 5 V together, check the specific DevKit schematic: boards differ in their protection against reverse power. Until checked, disconnect external 5 V when programming through powered USB.

## Direct 24 V → 3.3 V

An **isolated, regulated 24 V → 3.3 V converter** can supply the 3V3 rail if the specific DevKit supports external power on that rail. This bypasses the onboard regulator. Converter regulation, startup transients, ESP32 current peaks and USB compatibility then need to be checked directly. An unregulated isolated converter is unsuitable.

For the DevKit, use a regulated 5 V supply into VIN. For a custom PCB, isolated 5 V followed by a dedicated 3.3 V regulator is a practical option. Size the regulator for peak current and verify ripple. Current draw, regulator temperature and operation from the machine supply still need testing.

**Never apply 24 V to GPIO, CC1101, LCD or 3V3.** See [machine-interface.md](machine-interface.md) for outputs.
