# m&h 20.00 radio protocol

This protocol description is based on recordings of one probe and bench tests with an ESP32 + CC1101 receiver. It covers the **FREE and CONTACT messages** sent by an active probe. Addressing, CRC and control messages have not been decoded.

## Modulation and frame

The active stream contains two tone positions separated by approximately **4–4.4 kHz**. Short excursions to the lower tone form four pulses roughly **250–260 µs** wide. The receiver uses asynchronous 2-FSK and decodes pulse timing directly.

Pulse start time relative to the first pulse:

| Pulse | FREE, µs | CONTACT, µs |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 1040 | 1040 |
| 3 | 1560 | 1560 |
| 4 | **3640** | **3120** |

Frames repeat approximately every **16,250 µs**, or 61.54 messages/s. Contact moves the fourth pulse 520 µs earlier. Carrier position and average power change little, so ordinary spectrograms show contact poorly.

## Accepting a message

[ProbeDecoder.h](../firmware/probe_rx/ProbeDecoder.h) checks:

- Each pulse is 120–400 µs wide. Through the 25 kHz reference demodulator (40 µs steps) the recorded pulses measure 200–280 µs; the width also shifts with the carrier offset at the slicer, so the window stays wide. A pulse outside this window, a pulse that starts before the previous one has ended (missed falling edge), or an inactive level while no pulse is open (missed rising edge, for example a pulse shorter than the interrupt latency) discards every open frame. The receiver interrupt reports the line level, not the edge direction, so chatter at an edge arrives as a repeated level: an inactive level up to 40 µs after the falling edge, or an active level up to 40 µs after the rising edge, is treated as edge bounce and ignored, and the pulse keeps the time of its first edge.
- A frame is decided only after its FREE slot has closed, 3760 µs after the first pulse. It needs exactly one pulse in each of the 1040 and 1560 µs slots, exactly one in the CONTACT or the FREE slot (all ±120 µs) and no other pulse. Pulses in both slots, or any other extra pulse, discard the frame, so one noise pulse cannot turn a FREE frame into CONTACT. CONTACT is reported about 0.4 ms after the end of its fourth pulse.
- Initial link acquisition and every FREE frame require cadence with the previous valid frame: 1–3 × 16,250 µs, within ±300 µs.
- While the link is up, a CONTACT frame is accepted at once, even off-cadence, and becomes the new cadence reference. The probe sends such a frame as soon as it is touched, so contact is not reported a frame late and a one-frame touch is not lost.

Opening the probe loop is easy; closing it again needs a FREE frame on cadence. A link is lost after **65 ms without an accepted frame**. A single matching pulse group is not enough to lock onto the probe.

The receiver does not pair with the probe or transmit commands; the sketch never issues STX. Other modes used by the original receiver have not been investigated.

## Frequency and search

The receiver finds the signal by frequency, so it does not need the factory channel numbers. The SDR recording contains 14 stable frequencies with an approximately **24.963 kHz** step, sometimes two steps. Absolute frequency depends on HackRF, CC1101 and transmitter clock error.

The [ProbeSearch.h](../firmware/probe_rx/ProbeSearch.h) scheduler:

1. Initially tries 433.994200 MHz for 120 ms.
2. Scans 433–435 MHz in 20 kHz steps, dwelling 16 ms per frequency.
3. Checks up to four distinct signal peaks within ±30 kHz, in 2 kHz steps, 50 ms per point.
4. Locks only after valid messages. RSSI alone never asserts READY.
5. Drops the link after 65 ms; starts searching again 250 ms after the last accepted message.

The candidate threshold is −104 dBm. Range and accuracy depend on the antenna and module. The sketch assumes a 26 MHz CC1101 crystal: nominal receive bandwidth 58 kHz, configured symbol rate 3843/s, deviation ±2182 Hz, GDO0 asynchronous data with active LOW. These settings let the CC1101 recover the pulse signal; the firmware does not use its packet decoder.

## Display interpretation

**Red:** no validated messages, including search, RF interference or a missing CC1101. **Green:** valid FREE stream. **Blue:** CONTACT; a short accepted contact remains visible for 100 ms on the display only.

- RX: receiver tuning frequency. On red it can be the frequency currently being tested.
- RSSI: CC1101 power estimate in dBm, not externally calibrated.
- Noise(scan): lower quartile of RSSI from the last band scan. It is not measured in-channel noise; subtracting it from RSSI does not give an accurate channel SNR.
- Messages: accepted messages/s; Msg: total accepted frames.
- Lost: transitions from validated link to link loss; Touch: validated transitions into CONTACT.
- Age: time since the last accepted message; Ovf: edge queue overflow count.

Metrics refresh every 50 ms; color is checked every 5 ms. The display's visible response time has not been measured. Display work runs on core 0; reception and machine outputs run on core 1. Rendering uses a static 240×8 strip, **3840 bytes**, rather than allocating a full framebuffer on the heap.

## Limits

The decoder recognizes the pulse pattern and repetition rate, not an individual probe. Another probe transmitting the same pattern could be accepted. No address or CRC is checked.

A short mechanical contact can fall entirely between frames. Contacts shorter than a frame period are not guaranteed to be transmitted. Sensor debounce and internal delay are unknown. End-to-end latency from mechanical contact to the 828D input, and measurement repeatability, remain unmeasured.

[Button/power behavior](probe-behavior.md) · [Parameters JSON](../protocol/probe.json) · [Validation](validation.md)
