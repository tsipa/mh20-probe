"""Exercise the exact firmware RSSI gate, including noise and loss of SPI data."""
from pathlib import Path
import json
import wasmtime

root = Path(__file__).resolve().parents[1]/'build/tests'
engine = wasmtime.Engine()
store = wasmtime.Store(engine)
instance = wasmtime.Instance(store, wasmtime.Module.from_file(engine, str(root/'rf_presence.wasm')), [])
e = instance.exports(store)

def call(name, *args):
    return e[name](store, *args)

def raw(dbm):
    return (round(dbm*2) + 148) % 256

for byte, expected in [(0, -148), (127, -21), (128, -276), (255, -149)]:
    assert call('convert', byte) == expected
call('reset')
assert not call('valid')
for _ in range(10):
    assert not call('feed', raw(-105))
assert call('valid')
# One noise spike must not assert RF presence, nor accumulate across gaps.
for _ in range(4):
    assert not call('feed', raw(-70))
    assert not call('feed', raw(-100))
assert not call('feed', raw(-90))
assert call('feed', raw(-90))
# Between thresholds, keep presence; a brief fade must not release it.
for _ in range(5):
    assert call('feed', raw(-92))
for _ in range(3):
    assert call('feed', raw(-94))
assert call('feed', raw(-92))
for _ in range(3):
    assert call('feed', raw(-94))
assert not call('feed', raw(-94))
# Retuning or a failed SPI read clears presence and makes the reading unknown.
assert not call('feed', raw(-65))
assert call('feed', raw(-65))
call('reset')
assert not call('valid')
assert not call('feed', raw(-65))
result = {'passed': True, 'tested': ['signed RSSI conversion and half-dB resolution',
    'quiet background', 'isolated noise spikes', 'two-sample acquisition',
    'hysteresis and interrupted fades', 'four-sample loss', 'retune/SPI failure reset'],
    'on_dbm': -90, 'off_dbm': -94,
    'hardware_calibrated': False}
(root/'rf-presence-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('PASS: exact C++ RSSI conversion, acquisition, hysteresis, loss and reset.')
