# Radio recording analysis

These Python modules analyze recorded radio signals:

- `auto_probe_dsp.py`: band-wide FFT candidates, automatic validation and retuning.
- `protocol_dsp.py`: four-pulse messages and the edge timing decoder.
- `contact_dsp.py`: streaming decimation; also retains earlier research detectors.
- `signal_meter.py`: digital channel power/noise estimates in dBFS.

Tests use `AutoProbeDetector` to process recorded IQ in 10 ms blocks and pass the measured edges to the firmware's C++ decoder. The Python FFT search works on recordings; the firmware searches using CC1101 RSSI. See [testing](../../docs/validation.md) for the differences.

On the ESP32, the CC1101 demodulates the signal and sends pulse levels to GDO0. The Python code is only used for recording analysis and tests.
