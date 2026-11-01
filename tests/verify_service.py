"""Exercise Wi-Fi latching and update inhibition with real probe frames."""
from pathlib import Path
import wasmtime
engine=wasmtime.Engine(); store=wasmtime.Store(engine)
p=Path(__file__).resolve().parents[1]/'build/tests/service.wasm'
e=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(p)),[]).exports(store)
def call(name,*args): return e[name](store,*args)
def frame(start,contact=False):
    for offset in (0,1040,1560,3120 if contact else 3640):
        call('edge',1,(start+offset)%2**32)
        call('edge',0,(start+offset+260)%2**32)
for offset in (0,2**32-20000):
    for contact in (False,True):
        call('reset'); assert call('network')==1; assert call('outputs',offset)==4
        frame(offset+1000,contact); assert call('network')==1
        frame(offset+17250,contact); assert call('network')==0
        assert call('outputs',(offset+21500)%2**32)==(5 if contact else 3)
        assert call('outputs',(offset+120000)%2**32)==4
        assert call('recovery',0,1000000,0)==0
        assert call('network')==0  # Loss of the probe must not restore Wi-Fi.
        assert call('update')==0  # A stale web request cannot start an update.
call('reset'); assert call('network')==1; assert call('update')==1
frame(1000); frame(17250)
assert call('network')==1; assert call('outputs',21500)==4
assert call('update')==1  # Retrying after an upload failure remains in maintenance.
call('reset'); assert call('network')==1; assert call('outputs',0)==4
print('PASS: boot Wi-Fi, validated probe latch, loss, OTA lockout, retry and reboot.')

call('reset')
for start in (0,2**32-10000):
    assert call('recovery',0,(start+14999)%2**32,start)==0
    assert call('recovery',0,(start+15000)%2**32,start)==1
    assert call('recovery',1,(start+15000)%2**32,start)==0
print('PASS: recovery AP timeout, rollover and suppression after probe detection.')
