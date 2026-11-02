"""Check actual C++ output policy with the firmware pulse decoder, including RF loss."""
import json
from pathlib import Path
import wasmtime

ROOT=Path(__file__).resolve().parents[1]/'build/tests'
engine=wasmtime.Engine();store=wasmtime.Store(engine)
e=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(ROOT/'outputs.wasm')),[]).exports(store)
def call(name,*args):return e[name](store,*args)
def u32(n):return n%2**32
def frame(start,contact=False):
    for offset in (0,1040,1560,3120 if contact else 3640):
        call('edge',1,u32(start+offset))
        call('edge',0,u32(start+offset+260))

# Bit 0 READY; bit 1 probe loop closed (Form A energized); bit 2 logical trip.
for link,contact,expected in ((0,0,4),(0,1,4),(1,0,3),(1,1,5)):
    assert call('levels',link,contact)==expected
for offset in (0,2**32-20000):
    call('reset');assert call('outputs',offset)==4
    frame(offset+1000);assert call('outputs',u32(offset+5000))==4
    frame(offset+17250);assert call('outputs',u32(offset+21500))==3
    frame(offset+33500,True);assert call('outputs',u32(offset+37500))==5
    frame(offset+49750);assert call('outputs',u32(offset+54000))==3
    assert call('outputs',u32(offset+120000))==4
# Output guard: LOW is forced after 13 ticks of 5 ms (60-65 ms) without a loop refresh,
# held while stale, and released by the next refresh.
call('guardRefresh')
assert [call('guardTick') for _ in range(13)]==[0]*12+[1]
assert all(call('guardTick') for _ in range(1000))
call('guardRefresh');assert call('guardTick')==0
# Start-up check: outputs are enabled only once the interrupt has counted two ticks
# since a refresh, not merely because the timer was allocated.
call('guardRefresh');assert not call('guardRunning')
call('guardTick');assert not call('guardRunning')
call('guardTick');assert call('guardRunning')
result={'passed':True,'output_guard':'forced LOW after 60-65 ms without loop refresh; outputs enabled only after the guard is seen counting','truth_table':{'no_probe':'READY=0 LOOP=OPEN TRIP=1','free':'READY=1 LOOP=CLOSED TRIP=0','contact':'READY=1 LOOP=OPEN TRIP=1'},'boot_first_frame_loss_and_timer_rollover':True,'scope':'Exact C++ policy and pulse decoder, not physical GPIO/24V interface validation.'}
(ROOT/'outputs-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS: boot, acquisition, contact, release, RF loss, timer rollover and output guard.')
