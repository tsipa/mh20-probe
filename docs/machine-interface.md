# Machine interface: SINUMERIK 828D

## ESP32 outputs

| GPIO | Signal | HIGH, 3.3 V | LOW |
|---:|---|---|---|
| 33 | READY | Validated probe messages, including contact | No valid link, search, error or startup |
| 25 | PROBE_LOOP_ENABLE | Close probe loop: link valid and probe free | Open loop: contact **or** link absent |

**GPIO25 HIGH means a free probe with a validated link.** It drives the PhotoMOS K1; it is not a machine contact by itself. GPIO33 remains HIGH during contact because the probe is still communicating.

The output logic is in [MachineOutputs.h](../firmware/probe_rx/MachineOutputs.h). Both outputs are forced LOW by a global constructor before Arduino start-up and again as the first action of `setup()`, before the serial port, display and radio start. Contact outputs update as soon as a frame is decided, about 0.4 ms after the CONTACT pulse, while the display runs on another core. After 65 ms without accepted messages, READY drops and the loop opens. The loop remains open during frequency search.

Two independent mechanisms cover a stalled main loop. A hardware-timer interrupt forces both outputs LOW if the main loop has not re-evaluated them for 60–65 ms; the loop drives them again when it resumes. At startup the outputs stay LOW unless this interrupt is seen running; if it is not, they stay LOW until restart, and in place of the probe state the display shows FAULT / OUTPUT GUARD FAULT on red and the serial status line reads OUTPUT_GUARD_FAULT. While the outputs may be active, the ESP32 task watchdog resets the chip if the loop stalls for 2 s; by then the interrupt has already forced both outputs LOW.

A reset does not open the loop by itself. Only power-on leaves the GPIOs high impedance. A panic or software restart (watchdog, exception, abort, stack overflow, firmware restart) resets only the CPU: GPIO25 and GPIO33 keep their last level through the panic report, the bootloader and start-up until the firmware forces them LOW again, a fraction of a second later. After a task-watchdog reset this is safe because the timer interrupt has already opened the loop. Firmware restarts requested from the service page or UART happen only while both outputs are already LOW. After an exception, abort, stack overflow or interrupt-watchdog reset while the probe is free, the loop stays closed and READY stays HIGH for that time, so a touch is not signalled. This firmware does not close that gap. GPIO25 and GPIO33 are static levels; no output carries an enable signal that toggles while the loop is commanded closed and stops when the CPU halts. A pull-down alone does not help, because the pin stays actively driven HIGH through the reset, and a driver that conducts only while it receives a periodically refreshed enable signal would never turn on with this firmware. Closing the gap needs both a firmware change that generates such a signal and a matching driver (for example AC-coupled or charge-pump); neither exists in this firmware or on the carrier. Check reset behavior on hardware.

| Receiver state | READY | External probe loop | Logical trip |
|---|---:|---|---:|
| No probe / no valid messages / startup / search | 0 | Open | 1 |
| Valid probe, free | 1 | Closed | 0 |
| Contact | 1 | Open | 1 |

While service Wi-Fi is active, the output GPIOs stay low. After a probe is detected, Wi-Fi shuts down before the outputs can become active. During a firmware upload, both outputs remain low until restart. See [Wi-Fi updates](wifi-update.md).

## 24 V output stage

ESP32 GPIO and CC1101 operate at 3.3 V. **Do not connect machine 24 V to them.**

The carrier has two AQY212EH DIP4 PhotoMOS relays, **Form A / normally open**, each driven directly from its GPIO through a 150 ohm 1% resistor. K1 is the probe loop, K2 is READY. See [the carrier documentation](../hardware/pcb/README.md).

| J1 pin | Signal |
|---:|---|
| 1 | 24 V in |
| 2 | 0 V (machine 0 V = logic GND) |
| 3 / 4 | READY output (READY_A / READY_B), K2, GPIO33 |
| 5 / 6 | PROBE output (PROBE_A / PROBE_B), K1, GPIO25 |

The PhotoMOS outputs are bidirectional, so A/B polarity does not matter. They are the only isolated part of the board: the 5 V buck is not isolated (see [power.md](power.md)).

A Form A contact closes only while powered and driven, so power loss opens the loop and is interpreted as a trip. Maximum specified turn-on/turn-off at 5 mA and 25 C are 4 ms/1 ms. Check that the relay suits the machine input: polarity, current, voltage, leakage and switching threshold.

The probe contact must close only when GPIO25 drives K1. The carrier has no separate driver or pull-down resistor. Verify startup and reset behavior on hardware: the pins are high impedance after power-on but keep their last level through a crash restart (see above). Configure the machine input so that opening the loop means triggered. Any required opposite polarity must be resolved in the output stage and machine configuration.

Connecting the dry contact to +24 V or 0 V depends on the machine's input circuit. Use the machine's electrical drawings and the exact PPU/input module model to choose the terminals and NPN/PNP wiring.

## Readiness in SINUMERIK 828D

Connect contact detection to the fast measurement input specified by the machine builder. READY is a separate input for PLC/probing-cycle logic. Substituting an ordinary PLC input for the intended measurement input can reduce measurement repeatability.

Before a probing move, activate the probe and wait until READY=1 and the stylus is free. Loss of READY during measurement should cause a stop/error according to the machine program. This interlock must be implemented in the specific PLC or probing cycle; the receiver firmware does not modify the 828D PLC.

A triggered probe input usually interrupts a measurement move. **Ordinary G0/G1 moves may ignore it.** Preventing movement during probing without readiness requires a separate READY interlock. The interlock should apply to probing moves, allowing normal machining with the probe switched off.

## Power loss

With the polarity described above, an open probe wire or loss of power to the normally open output produces a trip.

Host C++/WebAssembly tests cover startup, acquisition, contact, release, missing messages and timer rollover: [validation.md](validation.md). Physical outputs and the 24 V connection remain untested.
