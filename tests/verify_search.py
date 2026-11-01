"""Exercise the firmware frequency search with a virtual receive filter.

Checks scan coverage and link-only lock; this does not emulate CC1101 demodulation.
"""
from pathlib import Path
import json
import wasmtime

ROOT=Path(__file__).resolve().parents[1]/'build/tests'
engine=wasmtime.Engine();store=wasmtime.Store(engine)
instance=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(ROOT/'search.wasm')),[])
e=instance.exports(store)

def call(name,*args):return e[name](store,*args)

def run(target=None, interferer=None, offset=0, previous=433994200, duration=10):
    call('reset',offset,previous)
    tuned=call('frequency');tuned_at=0;last_message=0;locked=None;coverage=set()
    for t in range(0,int(duration*1e6),1000):
        phase=call('phase');coverage.add(tuned)
        rssi=-220
        if target and abs(target-tuned)<=20000:rssi=-140
        if interferer and abs(interferer-tuned)<=20000:rssi=-90
        # A message decoder can lock only near the target's FSK midpoint.
        link=bool(target and abs(target-tuned)<=1000 and t-tuned_at>=40000)
        if link:last_message=(t+offset)%2**32
        changed=call('feed',(t+offset)%2**32,int(link),last_message,int(t-tuned_at>=10000),rssi)
        if changed:tuned=call('frequency');tuned_at=t
        if call('phase')==3:
            locked=t/1e6;break
    return {'target_hz':target,'interferer_hz':interferer,'lock_seconds':locked,
            'tuned_hz':tuned,'checked_band':bool(call('checked')),
            'rf_energy':bool(call('rf')),'visited_count':len(coverage),
            'noise_half_dbm':call('noiseHalfDbm') if call('noiseValid') else None}


results=[]
quiet=run(duration=4)
assert quiet['lock_seconds'] is None and quiet['checked_band'] and not quiet['rf_energy'],quiet
assert quiet['noise_half_dbm']==-220,quiet
results.append(quiet)
for target in [433001200,433219200,433993400,434777300,434997900]:
    for offset in [0,2**32-500000]:
        r=run(target,offset=offset)
        assert r['lock_seconds'] is not None and r['lock_seconds']<4,r
        assert abs(r['tuned_hz']-target)<=1000,r
        r['timer_wrap']=bool(offset);results.append(r)
cw=run(interferer=433500000,duration=6)
assert cw['lock_seconds'] is None and cw['rf_energy'],cw
results.append(cw)
beside=run(434121100,interferer=433500000,duration=8)
assert beside['lock_seconds'] is not None,beside
assert beside['noise_half_dbm']==-220,beside
results.append(beside)
# An absent link must leave Locked and restart searching after 250 ms.
call('reset',0,433994200);call('feed',40000,1,40000,1,-140)
assert call('phase')==3
call('feed',300000,0,40000,1,-220)
assert call('phase')==1 and call('frequency')==433000000
result={'passed':True,'cases':results,'loss_restarts_search':True,
        'scope':'Exact C++ scan scheduler with virtual RSSI and message lock; this test does not validate physical acquisition across the band.'}
(ROOT/'search-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
print('PASS: full-band acquisition, interference rejection, quiet band, link loss and timer rollover.')
