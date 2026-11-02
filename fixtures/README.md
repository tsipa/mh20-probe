# Recorded test signals

These are short, unmodified excerpts of SDR captures of the probe (**24.4 MB** in total). The full recordings are several gigabytes and are not included. The tests use the excerpts below.

| File | Source recording, interval in s | Content | Expected result |
|---|---|---|---|
| background.cs8 | background, 2.00–2.20 | Background, probe off | No valid messages, READY=0 |
| free.cs8 | touches, 2.00–2.20 | Probe active, free | FREE, no false CONTACT |
| contact-on.cs8 | touches, 5.20–5.65 | Touch | FREE → CONTACT |
| contact-off.cs8 | touches, 7.50–7.95 | Release | CONTACT → FREE |
| channel-hop.ci16 | sweep, 8.05–8.50 | Channel button held | FREE at ~433.721391 → ~433.746355 MHz |

A link-loss test joins a FREE excerpt to background and checks that the receiver clears the link and frequency about 65 ms after the last valid frame. It samples the state every 10 ms.

[manifest.json](manifest.json) records format, sample rate, center frequency, scale, original byte offset, duration, excerpt SHA-256 and full-recording SHA-256. IQ order is **I,Q**. CS8 is signed int8 at 8 million complex samples/s, center 434 MHz (HackRF). CI16 is little-endian signed int16 at 2 million complex samples/s, center 433.912004 MHz (SDR++ baseband WAV). Extraction performs no filtering, resampling or synthesis.

Contact labels match decoded frames to the touches made during recording. Mechanical contact timing was not measured separately. More recordings are needed to cover a wider range of interference.

`scripts/extract_fixtures.py --source-root <dir>` re-extracts the excerpts from the full recordings. Normal test runs do not need them.
