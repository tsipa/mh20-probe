# Recorded test signals

The repository contains **24.4 MB** of unchanged ADC samples. The full recordings are several gigabytes and are stored separately. The tests use the short excerpts listed below.

| File | Source / interval, s | Expected result |
|---|---|---|
| background.cs8 | background, 2.00–2.20 | No valid messages, READY=0 |
| free.cs8 | touches, 2.00–2.20 | FREE, no false CONTACT |
| contact-on.cs8 | touches, 5.20–5.65 | FREE → CONTACT |
| contact-off.cs8 | touches, 7.50–7.95 | CONTACT → FREE |
| channel-hop.ci16 | SDR++ WAV, 8.05–8.50 | FREE at ~433.721391 → ~433.746355 MHz |

A link-loss test joins a FREE recording to background noise and checks that the receiver clears the link and frequency about 65 ms after the last valid frame. It samples the state every 10 ms.

[manifest.json](manifest.json) records format, sample rate, center frequency, scale, original byte offset, duration, excerpt SHA-256 and full-source SHA-256. IQ order is **I,Q**. CS8 is signed int8 at 8 million complex samples/s, center 434 MHz. CI16 is little-endian signed int16 at 2 million complex samples/s, center 433.912004 MHz. Extraction performs no filtering, resampling or synthesis.

Contact labels match decoded frames to the touches made during recording. Mechanical contact timing was not measured separately. More recordings are needed to test a wider range of interference.

Full recordings are stored separately. Re-extract from a saved archive:

```powershell
python scripts/extract_fixtures.py --source-root .\hackrf-mh
```

Normal test runs do not require that archive.
