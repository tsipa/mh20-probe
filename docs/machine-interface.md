# Machine interface: SINUMERIK 828D

## Reserved ESP32 outputs

| GPIO | Signal | HIGH, 3.3 V | LOW |
|---:|---|---|---|
| 33 | READY | Validated probe messages, including contact | No valid link, search, error or startup |
| 25 | PROBE_LOOP_ENABLE | Close probe loop: link valid and probe free | Open loop: contact **or** link absent |

**GPIO25 HIGH means a free probe with a validated link.** It controls an external isolated output; it is not a machine contact by itself. GPIO33 remains HIGH during contact because the probe is still communicating.

The output logic is in [MachineOutputs.h](../firmware/probe_rx/MachineOutputs.h). Outputs are initialized before the display/radio. Contact outputs update immediately after an accepted frame, while the display runs on another core. After 65 ms without accepted messages, READY drops and the loop opens. The loop remains open during frequency search.

| Receiver state | READY | External probe loop | Logical trip |
|---|---:|---|---:|
| No probe / no valid messages / startup / search | 0 | Open | 1 |
| Valid probe, free | 1 | Closed | 0 |
| Contact | 1 | Open | 1 |

## 24 V output stage

ESP32 GPIO and CC1101 operate at 3.3 V. **Do not connect machine 24 V directly.** Machine power needs a converter and a separate output interface.

The planned circuit uses two fast DC PhotoMOS **Form A / normally open** outputs: one for the probe loop and one for READY. Choose parts to suit the machine's input circuit: polarity, current, voltage, leakage, on resistance and switching threshold. Check both switching delays; the prototype target is up to 0.5 ms. A slow relay module adds delay and mechanical bounce.

A Form A contact closes only while powered and enabled, so power loss opens the loop and is interpreted as a trip. Drive the PhotoMOS LED with current limiting and a suitable driver. The circuit and part numbers are not finalized. See [power.md](power.md) for isolated 24 V → 5 V power.

The probe contact must close only when GPIO25 enables its driver. Add external pull-downs of roughly 10 kΩ on driver inputs GPIO25/33: ESP32 pins may be high impedance during boot. Configure the machine input so that opening the loop means triggered. Any required opposite polarity must be resolved in the output stage and machine configuration.

Connecting the dry contact to +24 V or 0 V depends on the machine's input circuit. Use the machine's electrical drawings and the exact PPU/input module model to choose the terminals and NPN/PNP wiring.

## Readiness in SINUMERIK 828D

Connect contact detection to the fast measurement input specified by the machine builder. READY is a separate input for PLC/probing-cycle logic. Substituting an ordinary PLC input for the intended measurement input can reduce measurement repeatability.

Before a probing move, activate the probe and wait until READY=1 and the stylus is free. Loss of READY during measurement should cause a stop/error according to the machine program. This interlock must be implemented in the specific PLC or probing cycle; the receiver firmware does not modify the 828D PLC.

A triggered probe input usually interrupts a measurement move. **Ordinary G0/G1 moves may ignore it.** Preventing movement during probing without readiness requires a separate READY interlock. The interlock should apply to probing moves, allowing normal machining with the probe switched off.

## Power loss

With the polarity described above, an open probe wire or loss of power to the normally open output produces a trip.

Host C++/WebAssembly tests cover startup, acquisition, contact, release, missing messages and timer rollover: [validation.md](validation.md). Physical outputs and the 24 V connection remain untested.
